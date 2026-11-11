def process_vent(
    input_path="input.csv",
    output_path="output.csv"
):
    df = pd.read_csv(input_path)

    df = df[["subject_id", "charttime", "itemid", "value"]]

    mask = ((df["itemid"] == 223835) | (df["itemid"] == 220339) | (df["itemid"] == 224700))
    df1 = df[mask]
    df2 = df[~mask]
    df1["value"] = pd.to_numeric(df1["value"], errors="coerce")

    mask = df["itemid"] == 223835

    # 0.2 到 1 之间：乘以 100
    df1.loc[mask & df1["value"].gt(0.2) & df1["value"].le(1), "value"] *= 100

    # 保留 20 到 100 之间的原始值
    valid_mask = (
        (df1["itemid"] != 223835)
        | (
            df1["value"].ge(20)
            & df1["value"].le(100)
        )
    )
    df1 = df1.loc[valid_mask].copy()

    valid_mask = (
            ((df1["itemid"] != 220339) & (df1["itemid"] != 224700))
            | (df1["value"].ge(0) & df1["value"].le(100))
        )
    df1 = df1.loc[valid_mask].copy()

    merged_df = pd.concat([df1, df2], ignore_index=True)
    merged_df.to_csv(output_path, index=False)

    print(f"处理后记录数: {len(df)}")

    return df