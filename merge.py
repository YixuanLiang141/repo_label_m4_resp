import pandas as pd

def merge_sort_rename(csv1: str, csv2: str, output_file: str):

    df1 = pd.read_csv(csv1)
    df2 = pd.read_csv(csv2)

    # 检查列名和顺序是否完全一致
    if list(df1.columns) != list(df2.columns):
        raise ValueError("两个文件的列名或顺序不一致，拒绝合并")

    merged_df = pd.concat([df1, df2], ignore_index=True)

    merged_df.sort_values(by=['subject_id', 'charttime'], inplace=True)

    mapping = {50816: 'fio2', 50821: 'pao2', 223835: 'fio2', 220224: 'pao2'}
    merged_df["itemid"] = merged_df["itemid"].map(mapping).fillna(merged_df["itemid"])
    merged_df.rename(columns={'itemid': 'item'}, inplace=True)
    merged_df = merged_df.drop_duplicates(keep='first')

    merged_df.to_csv(output_file, index=False)

    print(f"合并完成，共 {len(merged_df)} 行，保存到: {output_file}")

if __name__ == "__main__":
    merge_sort_rename('./chartresp.csv', './labresp.csv', './resp.csv')