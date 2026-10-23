import pandas as pd

def filter_large_csv_by_stay_ids(input_file, output_file, key_col, chunksize=100_000):
    valid_ids = [224688, 224689, 224690, 224687, 224685, 224684, 224686, 224696,
                 220339, 224700, 223835, 223849, 229314, 223848, 224691]

    reader = pd.read_csv(input_file, chunksize=chunksize)
    first_chunk = True

    total_rows_kept = 0
    for i, chunk in enumerate(reader):
        filtered_chunk = chunk[chunk[key_col].isin(valid_ids)]
        total_rows_kept += len(filtered_chunk)

        if first_chunk:
            filtered_chunk.to_csv(output_file, index=False, mode='w')
            first_chunk = False
        else:
            filtered_chunk.to_csv(output_file, index=False, mode='a', header=False)

        print(f"✔ 已处理第 {i+1} 块，保留 {len(filtered_chunk)} 行")

def remove_columns_from_csv(data_file, output_file):

    df = pd.read_csv(data_file)

    df = df[["subject_id", "charttime", "itemid", "value"]]

    df.to_csv(output_file, index=False)
    print(f"输出文件保存至：{output_file}")

def process_fio2_and_peep(
    input_path="input.csv",
    output_path="output.csv"
):
    df = pd.read_csv(input_path)

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

if __name__ == "__main__":

    filter_large_csv_by_stay_ids('../../icu/chartevents.csv', './vent_set.csv', 'itemid')
    remove_columns_from_csv('./vent_set.csv', './vent_set.csv')
    process_fio2_and_peep('./vent_set.csv', './vent_set.csv')