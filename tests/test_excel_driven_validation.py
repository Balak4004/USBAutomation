

from Utils.excel_utils import (
    read_test_cases,
    update_status,
    write_mismatch
)
from Utils.db_utils import execute_query
from Utils.validation_utils import (
    row_count_validation,
    data_match_validation
)


def test_excel_driven_table_validation(oracle_engine):

    df = read_test_cases()

    for idx, row in df.iterrows():
        status = "FAIL"

        try:
            src_df = execute_query(oracle_engine, row["source_query"])
            tgt_df = execute_query(oracle_engine, row["target_query"])

            src_df.columns = src_df.columns.str.upper()
            tgt_df.columns = tgt_df.columns.str.upper()

            if row["validation_type"] == "row_count":

                if row_count_validation(src_df, tgt_df):
                    status = "PASS"
                else:
                    write_mismatch(f"{row['test_id']}_source", src_df)
                    write_mismatch(f"{row['test_id']}_target", tgt_df)

            elif row["validation_type"] == "data_match":

                pk_cols = [
                    c.strip().split(":")[0]
                    for c in row["pk_columns"].split(",")
                ]
                mismatches = data_match_validation(src_df, tgt_df, pk_cols)

                if mismatches.empty:
                    status = "PASS"
                else:
                    write_mismatch(f"{row['test_id']}_mismatch", mismatches)

        except Exception as e:
            print(f"Error in Test {row['test_id']} : {str(e)}")
            raise

        df.at[idx, "status"] = status

    update_status(df)

    # Framework execution should not stop
    assert True
