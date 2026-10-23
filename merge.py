import pandas as pd

def merge_csv_if_columns_match(csv1: str, csv2: str, output_file: str):
    """
    合并两个列完全相同的 CSV 文件，并保存到新文件中。如果列不一致则拒绝合并。

    参数:
        csv1 (str): 第一个 CSV 文件路径
        csv2 (str): 第二个 CSV 文件路径
        output_file (str): 合并后的输出文件路径
    """
    df1 = pd.read_csv(csv1)
    df2 = pd.read_csv(csv2)

    # 检查列名和顺序是否完全一致
    if list(df1.columns) != list(df2.columns):
        raise ValueError("两个文件的列名或顺序不一致，拒绝合并")

    merged_df = pd.concat([df1, df2], ignore_index=True)
    merged_df.to_csv(output_file, index=False)
    print(f"合并完成，共 {len(merged_df)} 行，保存到: {output_file}")

def sort_csv_by_two_col(input_file, output_file, col1, col2):
    df = pd.read_csv(input_file)
    df.sort_values(by=[col1, col2], inplace=True)
    df.to_csv(output_file, index=False)

def rename(input_file, output_file):    
    df = pd.read_csv(input_file)
    mapping = {50816: 'fio2', 50821: 'pao2', 223835: 'fio2'}
    df["itemid"] = df["itemid"].map(mapping).fillna(df["itemid"])
    df.rename(columns={'itemid': 'item'}, inplace=True)
    df.to_csv(output_file, index=False)

if __name__ == "__main__":
    merge_csv_if_columns_match('./chartresp.csv', './labresp.csv', './resp.csv')
    sort_csv_by_two_col('./resp.csv', './resp.csv', 'subject_id', 'charttime')
    rename('./resp.csv', './resp.csv')