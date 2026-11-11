import pandas as pd

def filter_large_csv_by_stay_ids(input_file, output_file, key_col, chunksize=100_000):
    valid_ids = [223849, 229314, 226732]

    reader = pd.read_csv(input_file, chunksize=chunksize)
    first_chunk = True

    total_rows_kept = 0
    for i, chunk in enumerate(reader):
        filtered_chunk = chunk[chunk[key_col].isin(valid_ids)]
        total_rows_kept += len(filtered_chunk)

        if first_chunk:
            filtered_chunk = filtered_chunk[["subject_id", "charttime", "itemid", "value"]]
            filtered_chunk.to_csv(output_file, index=False, mode='w')
            first_chunk = False
        else:
            filtered_chunk = filtered_chunk[["subject_id", "charttime", "itemid", "value"]]
            filtered_chunk.to_csv(output_file, index=False, mode='a', header=False)

        print(f"✔ 已处理第 {i+1} 块，保留 {len(filtered_chunk)} 行")

def classify_invasive_vent(input_path, output_path):
    # 223849: invasive
    invasive_modes = {
        "(S) CMV",
        "APRV",
        "APRV/Biphasic+ApnPress",
        "APRV/Biphasic+ApnVol",
        "APV (cmv)",
        "Apnea Ventilation",
        "CMV",
        "CMV/ASSIST",
        "CMV/ASSIST/AutoFlow",
        "CMV/AutoFlow",
        "CPAP/PPS",
        "CPAP/PSV",
        "CPAP/PSV+Apn TCPL",
        "CPAP/PSV+ApnPres",
        "CPAP/PSV+ApnVol",
        "MMV",
        "MMV/AutoFlow",
        "MMV/PSV",
        "MMV/PSV/AutoFlow",
        "P-CMV",
        "PCV+",
        "PCV+/PSV",
        "PCV+Assist",
        "PRES/AC",
        "PRVC/AC",
        "PRVC/SIMV",
        "PSV/SBT",
        "SIMV",
        "SIMV/AutoFlow",
        "SIMV/PRES",
        "SIMV/PSV",
        "SIMV/PSV/AutoFlow",
        "SIMV/VOL",
        "SYNCHRON MASTER",
        "SYNCHRON SLAVE",
        "VOL/AC",
    }

    # 229314: Hamilton invasive
    invasive_modes_hamilton = {
        "APRV",
        "APV (cmv)",
        "(S) CMV",
        "P-CMV",
        "SIMV",
        "APV (simv)",
        "P-SIMV",
        "VS",
        "ASV",
    }

    # 229314: Hamilton non-invasive
    noninvasive_modes_hamilton = {
        "DuoPaP",
        "NIV",
        "NIV-ST",
    }

    # 226732：O2 deliv non-invasive
    noninvasive_devices = {
        "Bipap mask ",
        "CPAP mask ",
        "High flow nasal cannula",
        "Non-rebreather",
        "Face tent",
        "Aerosol-cool",
        "Venti mask ",
        "Medium conc mask ",
        "Ultrasonic neb",
        "Vapomist",
        "Oxymizer",
        "High flow neb",
        "Nasal cannula",
        "None",
    }
    df = pd.read_csv(input_path)

    itemid = pd.to_numeric(df["itemid"], errors="coerce")
    value = df["value"]

    is_invasive = (
        (itemid.eq(226732) & value.eq("Endotracheal tube"))
        | (itemid.eq(223849) & value.isin(invasive_modes))
        | (itemid.eq(229314) & value.isin(invasive_modes_hamilton))
    ).fillna(False)

    is_noninvasive = (
        (itemid.eq(226732) & value.isin(noninvasive_devices))
        | (itemid.eq(229314) & value.isin(noninvasive_modes_hamilton))
    ).fillna(False)

    # Ignore Tracheostomy tube、Trach mask 、Ambient and other unidentified values
    classified = df.loc[
        is_invasive | is_noninvasive,
        ["subject_id", "charttime"],
    ].copy()

    classified["vent"] = is_invasive.loc[classified.index].astype("int8")

    # vent = 1 if an invasive record exists at specific time
    df_vent = (
        classified
        .groupby(
            ["subject_id", "charttime"],
            as_index=False,
            sort=False,
            dropna=False,
        )["vent"]
        .max()
    )

    df_vent.to_csv(output_path, index=False)

def merge_vent_intervals(vent_csv, icu_csv, output_csv):
    """
    Merge continuous vent records, ends at vent mode changes
    Periods with 0 length are removed

    Example:
    08:00  InvasiveVent
    08:01  InvasiveVent
    08:02  NonInvasiveVent
    08:03  InvasiveVent
    08:04  InvasiveVent

    InvasiveVent     08:00—08:02
    InvasiveVent     08:03—08:04
    """

    vent = pd.read_csv(vent_csv, dtype={"subject_id": "string"})
    icu = pd.read_csv(icu_csv, dtype={"subject_id": "string"})

    required_vent = {"subject_id", "charttime", "vent"}
    required_icu = {"subject_id", "intime", "outtime"}

    if not required_vent.issubset(vent.columns):
        raise ValueError(f"Missing vent columns: {required_vent - set(vent.columns)}")
    if not required_icu.issubset(icu.columns):
        raise ValueError(f"Missing ICU columns: {required_icu - set(icu.columns)}")

    vent = vent[["subject_id", "charttime", "vent"]].copy()
    icu = icu[["subject_id", "intime", "outtime"]].copy()

    vent["charttime"] = pd.to_datetime(vent["charttime"], errors="raise")
    vent["vent"] = pd.to_numeric(vent["vent"], errors="raise")
    icu["intime"] = pd.to_datetime(icu["intime"], errors="raise")
    icu["outtime"] = pd.to_datetime(icu["outtime"], errors="raise")

    if vent.isna().any().any() or icu.isna().any().any():
        raise ValueError("Required fields must not contain missing values.")
    if not vent["vent"].isin([0, 1]).all():
        raise ValueError("vent must contain only 0 or 1.")
    if (icu["outtime"] < icu["intime"]).any():
        raise ValueError("ICU outtime must not precede intime.")

    # Assign an internal identifier to each distinct ICU window.
    icu = (
        icu.drop_duplicates()
        .sort_values(["subject_id", "intime", "outtime"])
        .reset_index(drop=True)
    )
    icu["_icu_id"] = range(len(icu))

    # Reject overlapping ICU windows, including shared endpoints.
    previous_max_outtime = (
        icu.groupby("subject_id", sort=False)["outtime"]
        .transform(lambda s: s.cummax().shift())
    )
    if icu["intime"].le(previous_max_outtime).any():
        raise ValueError(
            "ICU windows overlap or share an endpoint for the same subject."
        )

    # Collapse duplicate timestamps; any positive observation takes precedence.
    vent = (
        vent.groupby(["subject_id", "charttime"], as_index=False)["vent"]
        .max()
    )

    # Keep only observations that fall within an ICU window.
    data = vent.merge(icu, on="subject_id", how="inner")
    data = data.loc[
        data["charttime"].ge(data["intime"])
        & data["charttime"].le(data["outtime"])
    ].copy()

    output_columns = ["subject_id", "intime", "outtime", "starttime", "endtime"]
    if data.empty:
        return pd.DataFrame(columns=output_columns)

    data = data.sort_values(
        ["subject_id", "_icu_id", "charttime"]
    ).reset_index(drop=True)

    grouped = data.groupby("_icu_id", sort=False)
    previous_time = grouped["charttime"].shift()
    previous_vent = grouped["vent"].shift()
    next_time = grouped["charttime"].shift(-1)

    gap_limit = pd.Timedelta(hours=14)

    # Start a new invasive interval after vent=0 or a gap of at least 14 hours.
    new_event = data["vent"].eq(1) & (
        previous_vent.ne(1)
        | data["charttime"].sub(previous_time).ge(gap_limit)
    )
    data["_event"] = (
        new_event.astype("int64")
        .groupby(data["_icu_id"])
        .cumsum()
    )

    # Extend to the next observation, including vent=0, only if the gap is <14h.
    extend = (
        next_time.notna()
        & next_time.sub(data["charttime"]).lt(gap_limit)
    )
    data["_endtime"] = data["charttime"].where(~extend, next_time)

    # All observations and their next timestamps belong to the same ICU window.
    result = (
        data.loc[data["vent"].eq(1)]
        .groupby(
            ["subject_id", "_icu_id", "intime", "outtime", "_event"],
            as_index=False,
        )
        .agg(
            starttime=("charttime", "min"),
            endtime=("_endtime", "max"),
            n_timepoints=("charttime", "nunique"),
        )
    )

    # Remove single-timestamp intervals after segmentation; do not reconnect them.
    result = result.loc[result["n_timepoints"].ge(2), output_columns].sort_values(["subject_id", "intime", "starttime"]).reset_index(drop=True)
    result.to_csv(output_csv, index=False)

    return result

if __name__ == "__main__":

    #filter_large_csv_by_stay_ids('../../icu/chartevents.csv', './vent_set.csv', 'itemid')
    #classify_invasive_vent('./vent_set.csv', 'vent.csv')
    merge_vent_intervals('vent.csv', '../repo_label_m4_public/icustays_merged.csv', 'vent_time.csv')