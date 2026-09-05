
import pandas as pd

def row_count_validation(src_df, tgt_df):
    print(len(src_df))
    print(len(tgt_df))
    return len(src_df) == len(tgt_df)

def data_match_validation(src_df, tgt_df, pk_cols):
    merged = src_df.merge(
        tgt_df,
        on=pk_cols,
        how="outer",
        indicator=True,
        suffixes=("_src", "_tgt")
    )
    return merged[merged["_merge"] != "both"]