import pandas as pd

def calculate_sofa_respiration(
    respiration_path,
    output_path,
    admissions_path=None,
    aggregation_window=1,
    method="worst",
):
    """Calculate respiration SOFA scores from P/F ratios and ventilation flags."""

    if (
        isinstance(aggregation_window, bool)
        or not isinstance(aggregation_window, int)
        or aggregation_window < 1
    ):
        raise ValueError("aggregation_window must be a positive integer.")

    if method not in {"worst", "mean"}:
        raise ValueError("method must be 'worst' or 'mean'.")

    if admissions_path is None:
        raise ValueError("admissions_path is required for all window sizes.")

    admissions = pd.read_csv(
        admissions_path,
        usecols=["subject_id", "admission_number", "admittime", "starttime", "endtime"],
        dtype={"subject_id": "string", "admission_number": "Int64"},
    )

    for column in ("admittime", "starttime", "endtime"):
        admissions[column] = (
            pd.to_datetime(admissions[column], errors="raise")
            .dt.floor("h")
            .astype("datetime64[ns]")
        )

    if admissions.isna().any().any():
        raise ValueError("Admission identifiers and timestamps must not be missing.")

    if admissions["endtime"].lt(admissions["starttime"]).any():
        raise ValueError("Admission endtime must not precede starttime.")

    admissions = admissions.drop_duplicates().reset_index(drop=True)
    if admissions.duplicated(["subject_id", "admission_number"]).any():
        raise ValueError("Each subject/admission_number must identify one admission interval.")

    df = pd.read_csv(
        respiration_path,
        usecols=["subject_id", "charttime", "pao2fio2ratio", "vent"],
        dtype={"subject_id": "string"},
    )

    # Exclude unknown subjects and observations without a P/F ratio.
    df = df.loc[
        df["subject_id"].isin(admissions["subject_id"])
    ].copy()
    df["pao2fio2ratio"] = pd.to_numeric(
        df["pao2fio2ratio"], errors="raise"
    )
    df = df.dropna(subset=["pao2fio2ratio"]).copy()

    output_columns = ["subject_id", "admission_number", "charttime", "sofa_resp"]
    if df.empty:
        return pd.DataFrame(columns=output_columns)

    # Floor all observation timestamps to the hour.
    df["charttime"] = (
        pd.to_datetime(df["charttime"], errors="raise")
        .dt.floor("h")
        .astype("datetime64[ns]")
    )
    df["vent"] = pd.to_numeric(df["vent"], errors="raise")

    if df[["subject_id", "charttime"]].isna().any().any():
        raise ValueError("subject_id and charttime must not be missing.")

    # Match observations to admission intervals for every window size.
    # If hourly rounding creates a shared boundary, prefer the latest start.
    df = pd.merge_asof(
        df.sort_values("charttime", kind="stable"),
        admissions.sort_values("starttime", kind="stable"),
        by="subject_id",
        left_on="charttime",
        right_on="starttime",
        direction="backward",
        allow_exact_matches=True,
    )
    df = df.loc[df["charttime"].le(df["endtime"])].copy()

    if df.empty:
        return pd.DataFrame(columns=output_columns)

    if aggregation_window > 1:
        # Floor division also assigns observations before admission correctly.
        window = pd.Timedelta(hours=aggregation_window)
        window_number = (df["charttime"] - df["admittime"]) // window
        df["charttime"] = (
            df["admittime"]
            + pd.to_timedelta(
                window_number * aggregation_window,
                unit="h",
            )
        )

    # Require the low ratio and ventilation flag to occur on the same row.
    df["_vent_lt200"] = (
        df["pao2fio2ratio"].lt(200) & df["vent"].eq(1)
    ).fillna(False)
    df["_vent_lt100"] = (
        df["pao2fio2ratio"].lt(100) & df["vent"].eq(1)
    ).fillna(False)

    # Aggregate ratios and retain qualifying ventilation evidence per window.
    aggregation = "min" if method == "worst" else "mean"
    result = (
        df.groupby(
            ["subject_id", "admission_number", "charttime"],
            as_index=False,
        )
        .agg(
            ratio=("pao2fio2ratio", aggregation),
            vent_lt200=("_vent_lt200", "any"),
            vent_lt100=("_vent_lt100", "any"),
        )
    )

    # Use the aggregated ratio for eligibility and original rows for vent evidence.
    result["sofa_resp"] = 0
    result.loc[result["ratio"].lt(400), "sofa_resp"] = 1
    result.loc[result["ratio"].lt(300), "sofa_resp"] = 2
    result.loc[
        result["ratio"].lt(200) & result["vent_lt200"],
        "sofa_resp",
    ] = 3
    result.loc[
        result["ratio"].lt(100) & result["vent_lt100"],
        "sofa_resp",
    ] = 4

    # Omit normal windows and do not create windows without observations.
    output = (
        result.loc[result["sofa_resp"].gt(0), output_columns]
        .sort_values(["subject_id", "admission_number", "charttime"])
        .reset_index(drop=True)
    )
    output.to_csv(output_path, index=False)

    return output

if __name__ == "__main__":
    calculate_sofa_respiration('pafi.csv', 'sofa_resp_1_worst.csv',
                        '../repo_label_m4_public/admissions_merged.csv',
                        aggregation_window=1, method="worst")