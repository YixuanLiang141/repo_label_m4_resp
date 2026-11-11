import numpy as np
import pandas as pd

def calculate_pafi(input_path, vent_path, output_path):
    """Match PaO2 to FiO2, annotate invasive ventilation, and save the result.

    Input respiratory columns: subject_id, charttime, item, value.
    Input ventilation columns: subject_id, starttime, endtime.
    FiO2 must use the percentage scale (e.g. 40, not 0.40).
    Exact-time FiO2 takes precedence; otherwise use its latest timestamp
    within the preceding four hours, including the four-hour boundary.
    Preserve every PaO2 row, including rows without a matching FiO2.
    """
    resp = pd.read_csv(input_path, dtype={"subject_id": "string"})
    intervals = pd.read_csv(vent_path, dtype={"subject_id": "string"})

    for name, frame, required in (
        ("Respiratory", resp, {"subject_id", "charttime", "item", "value"}),
        ("Ventilation", intervals, {"subject_id", "starttime", "endtime"}),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{name} CSV is missing columns: {sorted(missing)}")

    resp = resp.loc[
        resp["item"].isin(["pao2", "fio2"]),
        ["subject_id", "charttime", "item", "value"],
    ].copy()
    intervals = intervals[["subject_id", "starttime", "endtime"]].copy()
    resp["charttime"] = pd.to_datetime(resp["charttime"], errors="raise").astype(
        "datetime64[ns]"
    )
    resp["value"] = pd.to_numeric(resp["value"], errors="raise")
    for column in ("starttime", "endtime"):
        intervals[column] = pd.to_datetime(
            intervals[column], errors="raise"
        ).astype("datetime64[ns]")

    if resp.isna().any().any() or intervals.isna().any().any():
        raise ValueError("Required input fields must not contain missing values.")
    if not np.isfinite(resp["value"].to_numpy()).all():
        raise ValueError("Respiratory values must be finite numbers.")
    if (resp.loc[resp["item"].eq("fio2"), "value"] <= 0).any():
        raise ValueError("FiO2 must be positive.")
    if intervals["endtime"].lt(intervals["starttime"]).any():
        raise ValueError("Ventilation endtime must not precede starttime.")

    columns = [
        "subject_id", "charttime", "pao2", "fio2_charttime", "fio2",
        "pao2fio2ratio", "vent",
    ]
    pao = resp.loc[resp["item"].eq("pao2")].rename(columns={"value": "pao2"})
    fio = resp.loc[resp["item"].eq("fio2")].rename(
        columns={"charttime": "fio2_charttime", "value": "fio2"}
    )
    if pao.empty:
        result = pd.DataFrame(columns=columns)
        result.to_csv(output_path, index=False)
        return result

    # Rank values within each timestamp without removing duplicate PaO2 rows.
    pao = pao.sort_values(
        ["subject_id", "charttime", "pao2"],
        ascending=[True, True, False], kind="stable",
    ).reset_index(drop=True)
    pao_group = pao.groupby(["subject_id", "charttime"], sort=False)
    pao["_pao_rank"] = pao_group.cumcount()
    pao["_pao_count"] = pao_group["pao2"].transform("size")
    pao["_row_order"] = np.arange(len(pao))

    fio = fio.sort_values(
        ["subject_id", "fio2_charttime", "fio2"],
        ascending=[True, True, False], kind="stable",
    ).reset_index(drop=True)
    fio_group = fio.groupby(["subject_id", "fio2_charttime"], sort=False)
    fio["_fio_rank"] = fio_group.cumcount()
    fio["_fio_count"] = fio_group["fio2"].transform("size")

    if fio.empty:
        matched = pao.copy()
        matched["fio2_charttime"] = pd.NaT
        matched["fio2"] = np.nan
    else:
        # Select a timestamp first so all FiO2 values at that timestamp remain eligible.
        fio_times = fio.loc[
            fio["_fio_rank"].eq(0),
            ["subject_id", "fio2_charttime", "_fio_count"],
        ]
        matched = pd.merge_asof(
            pao.sort_values("charttime", kind="stable"),
            fio_times.sort_values("fio2_charttime", kind="stable"),
            by="subject_id", left_on="charttime", right_on="fio2_charttime",
            direction="backward", tolerance=pd.Timedelta(hours=4),
            allow_exact_matches=True,
        )

        # Multiple values on both sides require equal counts for rank pairing.
        unequal = (
            matched["_pao_count"].gt(1)
            & matched["_fio_count"].gt(1)
            & matched["_pao_count"].ne(matched["_fio_count"])
        )
        if unequal.any():
            details = matched.loc[
                unequal,
                ["subject_id", "charttime", "fio2_charttime", "_pao_count", "_fio_count"],
            ].drop_duplicates()
            raise ValueError(
                "Unequal PaO2/FiO2 counts where both sides have multiple values; "
                f"manual review required for {len(details)} timestamp(s). "
                f"First 10:\n{details.head(10).to_string(index=False)}"
            )

        # One PaO2 uses the highest FiO2; one FiO2 is reused for every PaO2.
        # Equal multi-value groups pair high-to-high and low-to-low.
        matched["_fio_rank"] = np.where(
            matched["_pao_count"].gt(1) & matched["_fio_count"].gt(1),
            matched["_pao_rank"], 0,
        )
        matched = matched.merge(
            fio[["subject_id", "fio2_charttime", "_fio_rank", "fio2"]],
            on=["subject_id", "fio2_charttime", "_fio_rank"],
            how="left", validate="many_to_one",
        )

    # Convert percentage FiO2 to a fraction when calculating the P/F ratio.
    matched["pao2fio2ratio"] = matched["pao2"] / (matched["fio2"] / 100)

    if intervals.empty:
        matched["vent"] = np.int8(0)
    else:
        # Cumulative end times make interval membership robust to overlapping intervals.
        intervals = intervals.sort_values(
            ["subject_id", "starttime", "endtime"], kind="stable"
        )
        intervals["_vent_end"] = intervals.groupby("subject_id")["endtime"].cummax()
        intervals = intervals.drop_duplicates(
            ["subject_id", "starttime"], keep="last"
        )
        matched = pd.merge_asof(
            matched.sort_values("charttime", kind="stable"),
            intervals[["subject_id", "starttime", "_vent_end"]].sort_values(
                "starttime", kind="stable"
            ),
            by="subject_id", left_on="charttime", right_on="starttime",
            direction="backward", allow_exact_matches=True,
        )
        # Both starttime and endtime are inclusive, matching the original SQL.
        matched["vent"] = matched["charttime"].le(matched["_vent_end"]).astype("int8")

    result = matched.sort_values("_row_order", kind="stable")[columns].reset_index(
        drop=True
    )
    result.to_csv(output_path, index=False)
    print(f"Saved {len(result)} PaO2 records to {output_path}")
    return result


if __name__ == "__main__":
    calculate_pafi('resp.csv', 'vent_time.csv', 'pafi.csv')
