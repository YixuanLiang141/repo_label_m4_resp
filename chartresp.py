import pandas as pd

def filter_large_csv_by_stay_ids(input_file, output_file, key_col, chunksize=100_000):
    valid_ids = [223835, 220224]

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

def process_fio2_and_pao2(
    input_path="input.csv",
    output_path="output.csv"
):
    df = pd.read_csv(input_path)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    mask = df["itemid"] == 223835

    # 0.2 到 1 之间：乘以 100
    df.loc[mask & df["value"].gt(0.2) & df["value"].le(1), "value"] *= 100

    # 保留 20 到 100 之间的原始值
    valid_mask = (
        (df["itemid"] != 223835)
        | (
            df["value"].ge(20)
            & df["value"].le(100)
        )
    )
    df = df.loc[valid_mask]

    # Remove out-of-bound pao2
    valid_mask = (df["value"].le(1000) & df["value"].ge(0))
    df = df.loc[valid_mask]

    df.to_csv(output_path, index=False)

    print(f"处理后记录数: {len(df)}")

    return df

if __name__ == "__main__":

    filter_large_csv_by_stay_ids('../../icu/chartevents.csv', './chartresp.csv', 'itemid')
    remove_columns_from_csv('./chartresp.csv', './chartresp.csv')
    process_fio2_and_pao2('./chartresp.csv', './chartresp.csv')
