
import os
from datetime import datetime

import pandas as pd
import pytest
import oracledb
from sqlalchemy import create_engine
oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_21_20")

# ============================================================
# CONFIGURATION
# ============================================================

# Project root
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

# Excel configuration file
EXCEL_PATH = (r"E:\USB Automation project\ETLAutomationUsingExcelUSB\Data\table_validation_cases - Copy.xlsx"
)

# Output folder
OUTPUT_FOLDER = os.path.join(
    PROJECT_ROOT,
    "ComparisonResults"
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)

# ------------------------------------------------------------
# Set SerialNo to a specific number to run one mapping.
# Example:
# SERIAL_TO_RUN = 53
# Run all:
# SERIAL_TO_RUN = None
# ------------------------------------------------------------

SERIAL_TO_RUN = [1,2]

# PYTEST FIXTURES

@pytest.fixture(scope="session")
def oracle_engine():
    username = "hr"
    password = "hr"
    host = "localhost"
    port = "1521"
    service = "xe"

    connection_string = (
        f"oracle+oracledb://{username}:{password}@{host}:{port}/?service_name={service}"
    )

    engine = create_engine(connection_string)
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def mysql_engine():
    username = "root"
    password = "admin%402024"
    host = "localhost"
    port = "3306"
    database = "retaildwh"

    connection_string = (
        f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}"
    )

    engine = create_engine(connection_string)
    yield engine
    engine.dispose()

# FETCH DATABASE DATA
def fetch_dataframe(
    query: str,
    engine
) -> pd.DataFrame:
    # Execute SQL query using Pandas
    return pd.read_sql(
        query,
        engine
    )


# ORACLE VS MYSQL COMPARISON

def compare_source_target(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    source_join_keys: list[str],
    target_join_keys: list[str],
    table: str
) -> dict:
    """
    Compare Oracle source against MySQL target.
    Returns:
        SourceRowCount
        TargetRowCount
        SourceMinusTargetCount
        TargetMinusSourceCount
        ColumnMismatchCount
        Status
    """

    # Validate join keys
    missing_source_keys = [
        key
        for key in source_join_keys
        if key not in source_df.columns
    ]

    missing_target_keys = [
        key
        for key in target_join_keys
        if key not in target_df.columns
    ]

    if missing_source_keys:
        raise ValueError(
            f"{table}: Join keys missing from "
            f"Oracle source: {missing_source_keys}"
        )

    if missing_target_keys:
        raise ValueError(
            f"{table}: Join keys missing from "
            f"MySQL target: {missing_target_keys}"
        )

    # Row counts
    source_count = len(source_df)
    target_count = len(target_df)

    # --------------------------------------------------------
    # Validate column count
    # --------------------------------------------------------

    if len(source_df.columns) != len(target_df.columns):
        raise ValueError(
            f"{table}: Source and Target column counts do not match. "
            f"Oracle={len(source_df.columns)}, "
            f"MySQL={len(target_df.columns)}"
        )

    # --------------------------------------------------------
    # Create temporary positional column names
    # --------------------------------------------------------
    source_columns = list(source_df.columns)
    target_columns = list(target_df.columns)

    source_compare_df = source_df.copy()
    target_compare_df = target_df.copy()

    for i in range(len(source_columns)):
        source_column = source_columns[i]
        target_column = target_columns[i]

        # Do not rename join keys because they are needed for the merge
        if i < len(source_join_keys):
            continue
        compare_column = f"CMP_{i}"

        source_compare_df.rename(
            columns={source_column: compare_column },
            inplace=True
        )

        target_compare_df.rename(
            columns={target_column: compare_column },
            inplace=True
        )

    # Source vs Target - Full Outer Join
    merged_df = pd.merge(
        source_compare_df,
        target_compare_df,
        left_on=source_join_keys,
        right_on=target_join_keys,
        how="outer",
        indicator=True,
        suffixes=("_source", "_target")
    )

    # Source-only rows
    source_minus_target = merged_df[
        merged_df["_merge"] == "left_only" ]

    # Target-only rows
    target_minus_source = merged_df[
        merged_df["_merge"] == "right_only" ]

    source_minus_target_count = len(source_minus_target)
    target_minus_source_count = len(target_minus_source)

    # Rows present in both Source and Target
    matched_rows = merged_df[
        merged_df["_merge"] == "both" ]
    column_mismatches = []
    seen_keys = set()

    # --------------------------------------------------------
    # Column-level comparison
    for i in range(len(source_df.columns)):
        # Skip join key columns
        if i < len(source_join_keys):
            continue
        source_column = source_columns[i]
        target_column = target_columns[i]

        compare_column = f"CMP_{i}"

        source_value = matched_rows[f"{compare_column}_source"]
        target_value = matched_rows[f"{compare_column}_target"]

        mismatches = matched_rows[
            source_value != target_value
            ]

        # Store mismatch details
        # ----------------------------------------------------
        for _, row in mismatches.iterrows():
            key_tuple = (
                    tuple(
                        row[key]
                        for key in source_join_keys
                    )
                    +
                    (source_column,)
            )

            if key_tuple in seen_keys:
                continue
            seen_keys.add(key_tuple)

            column_mismatches.append({
                **{
                    key: row[key]
                    for key in source_join_keys
                },
                "Column": source_column,
                "SourceValue": row[f"{compare_column}_source"],
                "TargetValue": row[f"{compare_column}_target"],
                "Reason": "Value mismatch"
                })

    # --------------------------------------------------------
    # Create mismatch DataFrame
    mismatch_df = pd.DataFrame(
        column_mismatches )

    column_mismatch_count = len(
        mismatch_df )

    # --------------------------------------------------------
    # Save column mismatches
    if not mismatch_df.empty:
        mismatch_df.to_csv(
            os.path.join(
                OUTPUT_FOLDER,
                f"{table}_column_mismatches.csv"
            ),
            index=False
        )

    # --------------------------------------------------------
    # Overall status
    status = (
        "Matched"
        if (
            source_minus_target_count == 0
            and target_minus_source_count == 0
            and column_mismatch_count == 0
        )
        else
        "Mismatched"
    )

    return {
        "SourceRowCount":
            source_count,
        "TargetRowCount":
            target_count,
        "SourceMinusTargetCount":
            source_minus_target_count,
        "TargetMinusSourceCount":
            target_minus_source_count,

        "ColumnMismatchCount":
            column_mismatch_count,
        "Status":
            status
    }


# ============================================================
# MAIN PYTEST TEST
# ============================================================

def test_oracle_to_mysql(
    oracle_engine,
    mysql_engine
):

    # Main Oracle -> MySQL ETL validation test.
    mapping_df = pd.read_excel(EXCEL_PATH)

    # Validate Excel structure
    # --------------------------------------------------------
    required_columns = {
        "SerialNo",
        "SourceTable",
        "TargetTable",
        "SourceQuery",
        "TargetQuery",
        "JoinKey"
    }

    missing_columns = (
        required_columns
        -
        set(mapping_df.columns)
    )
    if missing_columns:
        pytest.fail(
            "Missing columns in query_config.xlsx: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Filter SerialNo
    if SERIAL_TO_RUN is not None:
        mapping_df = mapping_df[
            mapping_df["SerialNo"].isin(
            SERIAL_TO_RUN )
        ]

    # No mapping found
    if mapping_df.empty:
        pytest.fail(
            f"No mapping found for SerialNo "
            f"{SERIAL_TO_RUN}"
        )
    results = []

    # ========================================================
    # PROCESS EACH TABLE
    for _, row in mapping_df.iterrows():
        serial_no = row["SerialNo"]
        table = row["SourceTable"]
        source_query = row["SourceQuery"]
        target_query = row["TargetQuery"]

        join_key_pairs = [
            key.strip()
            for key in str(
                row["JoinKey"]
            ).split(",")
            if key.strip()
        ]

        source_join_keys = [
            pair.split(":")[0].strip()
            for pair in join_key_pairs
        ]

        target_join_keys = [
            pair.split(":")[1].strip()
            for pair in join_key_pairs
        ]

        print(
            f"\n🔄 Comparing: "
            f"{table} "
            f"(SerialNo: {serial_no})"
        )

        try:

            # ------------------------------------------------
            # Fetch Oracle source

            print(  "   Reading Oracle source..." )
            source_df = fetch_dataframe(
                source_query,
                oracle_engine
            )
            print(f"Oracle rows: {len(source_df)}" )

            # Fetch MySQL target
            # ------------------------------------------------

            print( "   Reading MySQL target..." )

            target_df = fetch_dataframe(
                target_query,
                mysql_engine
            )
            print(f"   MySQL rows:{len(target_df)}")

            # ------------------------------------------------
            # Compare
            comparison = compare_source_target(
                source_df=source_df,
                target_df=target_df,
                source_join_keys=source_join_keys,
                target_join_keys=target_join_keys,
                table=table
            )

            # ------------------------------------------------
            # Print result
            print(
                f"   Oracle={comparison['SourceRowCount']}, "
                f"MySQL={comparison['TargetRowCount']}, "
                f"Oracle-Minus-MySQL="
                f"{comparison['SourceMinusTargetCount']}, "
                f"MySQL-Minus-Oracle="
                f"{comparison['TargetMinusSourceCount']}, "
                f"Column mismatches="
                f"{comparison['ColumnMismatchCount']}"
            )

            print(f"   Status: {comparison['Status']}")

            # Store result
            # ------------------------------------------------
            results.append({
                "SerialNo":
                    serial_no,
                "Table":
                    table,
                **comparison,
                "RunTimestamp":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            })

        except Exception as e:
            print(
                f"❌ Error comparing "
                f"{table}: {e}"
            )

            results.append({
                "SerialNo":serial_no,
                "Table":table,
                "SourceRowCount":None,
                "TargetRowCount":None,
                "SourceMinusTargetCount":None,
                "TargetMinusSourceCount":None,
                "ColumnMismatchCount":None,
                "Status":"ERROR",
                "Error":
                    str(e),
                "RunTimestamp":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            })

    # ========================================================
    # SAVE SUMMARY
    summary_path = os.path.join(
        OUTPUT_FOLDER,
        "comparison_summary.csv"
    )
    result_df = pd.DataFrame(
        results
    )

    # --------------------------------------------------------
    # Append to existing summary
    # --------------------------------------------------------

    if os.path.exists(summary_path):
        existing_df = pd.read_csv(summary_path)
        # Remove previous results for the SerialNo(s) being executed
        existing_df = existing_df[
            ~existing_df["SerialNo"].isin(
                result_df["SerialNo"]
            )
        ]

        # Add latest results
        final_df = pd.concat(
            [
                existing_df,
                result_df
            ],
            ignore_index=True
        )
    else:
        final_df = result_df

    # --------------------------------------------------------
    # Save summary
    final_df.to_csv(
        summary_path,
        index=False
    )

    print(
        f"\n📄 Summary saved: "
        f"{summary_path}"
    )

    # ========================================================
    # PYTEST ASSERTION

    failed_tables = [
        result["Table"]
        for result in results
        if result.get("Status")
        !=
        "Matched"
    ]

    if failed_tables:
        pytest.fail(
            "Oracle → MySQL validation failed "
            "for: "
            +
            ", ".join(
                failed_tables
            )
        )

