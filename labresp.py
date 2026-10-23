import pandas as pd

def filter_large_csv_by_stay_ids(input_file, output_file, key_col, chunksize=100_000):
    valid_ids = [50816, 50821, 52033]

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

    df = df[["subject_id", "specimen_id", "charttime", "itemid", "value"]]

    df.to_csv(output_file, index=False)
    print(f"输出文件保存至：{output_file}")

def filter_arterial_blood_gas(
    input_path="input.csv",
    output_path="output.csv"
):
    df = pd.read_csv(input_path)

    # 记录 value 为 "ART." 的行对应的 specimen_id
    arterial_specimen_ids = set(
        df.loc[df["value"] == "ART.", "specimen_id"].dropna()
    )

    # 删除 itemid == 50821 且 specimen_id 不在动脉血标本集合中的行
    mask = (df["itemid"] == 50821) & (
        ~df["specimen_id"].isin(arterial_specimen_ids)
    )
    df = df.loc[~mask].copy()

    # 删除所有 itemid == 52033 的行
    df = df.loc[df["itemid"] != 52033].copy()

    df = df[["subject_id", "charttime", "itemid", "value"]]

    df.to_csv(output_path, index=False)

    print(f"动脉血标本数量: {len(arterial_specimen_ids)}")
    print(f"处理后记录数: {len(df)}")

    return df

def drop_rows_with_empty_column(csv_file, column, output_file=None, remove_non_numeric=False):
    df = pd.read_csv(csv_file)
    initial_rows = len(df)
    
    # 删除缺失值
    df_clean = df.dropna(subset=[column])
    
    # 如果启用删除非数字行
    if remove_non_numeric:
        # 尝试将列转换为数值，无法转换的会变成NaN
        df_clean[column] = pd.to_numeric(df_clean[column], errors='coerce')
        # 删除新产生的NaN行（即原来的非数字行）
        df_clean = df_clean.dropna(subset=[column])
    
    cleaned_rows = len(df_clean)

    # 判断是否需要写入
    if cleaned_rows == initial_rows and (output_file is None or output_file == csv_file):
        print(f"未发现需要删除的行，无需写入文件。")
        return df_clean

    # 写入结果
    output_path = output_file if output_file else csv_file
    df_clean.to_csv(output_path, index=False)
    
    # 统计信息
    missing_removed = initial_rows - len(df.dropna(subset=[column]))
    non_numeric_removed = len(df.dropna(subset=[column])) - cleaned_rows if remove_non_numeric else 0
    
    if remove_non_numeric:
        print(f"已删除 {missing_removed} 行 {column} 为空的数据和 {non_numeric_removed} 行非数字数据，结果保存至 {output_path}")
    else:
        print(f"已删除 {missing_removed} 行 {column} 为空的数据，结果保存至 {output_path}")
    
    return df_clean

def process_fio2(
    input_path="input.csv",
    output_path="output.csv"
):
    df = pd.read_csv(input_path)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    mask = df["itemid"] == 50816
    values = df.loc[mask, "value"]

    # 0.2 到 1 之间：乘以 100
    df.loc[mask & df["value"].gt(0.2) & df["value"].le(1), "value"] *= 100

    # 保留 20 到 100 之间的原始值
    valid_mask = (
        (df["itemid"] != 50816)
        | (
            df["value"].ge(20)
            & df["value"].le(100)
        )
    )
    df = df.loc[valid_mask].copy()

    df.to_csv(output_path, index=False)

    print(f"处理后记录数: {len(df)}")
    print(f"保留的 itemid=50816 记录数: {(df['itemid'] == 50816).sum()}")

    return df

if __name__ == "__main__":

    filter_large_csv_by_stay_ids('../../hosp/labevents.csv', './labresp.csv', 'itemid')
    remove_columns_from_csv('./labresp.csv', './labresp.csv')
    filter_arterial_blood_gas('./labresp.csv', './labresp.csv')
    drop_rows_with_empty_column('./labresp.csv', 'value', './labresp.csv', True)
    process_fio2('./labresp.csv', './labresp.csv')