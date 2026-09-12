
import os
from datetime import datetime

import pandas as pd
import pytest
import oracledb
from sqlalchemy import create_engine


# ============================================================
# ORACLE CLIENT
# ============================================================

oracledb.init_oracle_client(
    lib_dir=r"C:\oracle\instantclient_21_20"
)


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

EXCEL_PATH = os.path.join(
    PROJECT_ROOT,
    "Data",
    "count_validation_cases.xlsx"
)

OUTPUT_FOLDER = os.path.join(
    PROJECT_ROOT,
    "CountComparisonResults"
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)

SERIAL_TO_RUN = [1,2]


# ============================================================
# ORACLE CONNECTION
# ============================================================

@pytest.fixture(scope="session")
def oracle_engine():

    username = "hr"
    password = "hr"
    host = "localhost"
    port = "1521"
    service = "xe"

    connection_string = (
        f"oracle+oracledb://"
        f"{username}:{password}@"
        f"{host}:{port}/"
        f"?service_name={service}"
    )

    engine = create_engine(
        connection_string
    )

    yield engine

    engine.dispose()


# ============================================================
# MYSQL CONNECTION
# ============================================================

@pytest.fixture(scope="session")
def mysql_engine():

    username = "root"
    password = "admin%402024"
    host = "localhost"
    port = "3306"
    database = "retaildwh"

    connection_string = (
        f"mysql+mysqlconnector://"
        f"{username}:{password}@"
        f"{host}:{port}/{database}"
    )

    engine = create_engine(
        connection_string
    )

    yield engine

    engine.dispose()


# ============================================================
# GET COUNT
# ============================================================

def get_count(
    query: str,
    engine
) -> int:

    result = pd.read_sql(
        query,
        engine
    )

    return int(
        result.iloc[0, 0]
    )


# ============================================================
# GET PRIMARY / JOIN KEYS
# ============================================================

def get_keys(
    query: str,
    engine
) -> pd.DataFrame:

    return pd.read_sql(
        query,
        engine
    )


# ============================================================
# COMPARE COUNTS
# ============================================================

def compare_count(
    source_count: int,
    target_count: int
) -> dict:

    difference = (
        source_count
        -
        target_count
    )

    status = (
        "Matched"
        if source_count == target_count
        else "Mismatched"
    )

    return {
        "SourceRowCount":
            source_count,

        "TargetRowCount":
            target_count,

        "CountDifference":
            difference,

        "Status":
            status
    }


# ============================================================
# COMPARE PRIMARY / JOIN KEYS
# ============================================================

def compare_keys(
    source_key_df: pd.DataFrame,
    target_key_df: pd.DataFrame
) -> dict:

    # --------------------------------------------------------
    # Check number of key columns
    # --------------------------------------------------------

    if (
        len(source_key_df.columns)
        !=
        len(target_key_df.columns)
    ):

        raise ValueError(
            "Source and Target key column "
            "counts do not match. "
            f"Oracle={len(source_key_df.columns)}, "
            f"MySQL={len(target_key_df.columns)}"
        )


    # --------------------------------------------------------
    # Rename key columns to common names
    # --------------------------------------------------------

    source_key_columns = list(
        source_key_df.columns
    )

    target_key_columns = list(
        target_key_df.columns
    )

    source_key_df = source_key_df.copy()

    target_key_df = target_key_df.copy()

    common_key_columns = []

    for i in range(
        len(source_key_columns)
    ):

        common_name = f"KEY_{i}"

        source_key_df.rename(
            columns={
                source_key_columns[i]:
                    common_name
            },
            inplace=True
        )

        target_key_df.rename(
            columns={
                target_key_columns[i]:
                    common_name
            },
            inplace=True
        )

        common_key_columns.append(
            common_name
        )


    # --------------------------------------------------------
    # Remove duplicate keys
    # --------------------------------------------------------

    source_key_df = (
        source_key_df.drop_duplicates()
    )

    target_key_df = (
        target_key_df.drop_duplicates()
    )


    # --------------------------------------------------------
    # Compare Source and Target keys
    # --------------------------------------------------------

    merged_keys = pd.merge(
        source_key_df,
        target_key_df,
        on=common_key_columns,
        how="outer",
        indicator=True
    )


    # --------------------------------------------------------
    # Source Only
    # --------------------------------------------------------

    source_only = merged_keys[
        merged_keys["_merge"]
        ==
        "left_only"
    ].copy()


    # --------------------------------------------------------
    # Target Only
    # --------------------------------------------------------

    target_only = merged_keys[
        merged_keys["_merge"]
        ==
        "right_only"
    ].copy()


    # --------------------------------------------------------
    # Create Difference DataFrame
    # --------------------------------------------------------

    key_differences = []


    # --------------------------------------------------------
    # Source Only Keys
    # --------------------------------------------------------

    for _, row in source_only.iterrows():

        key_values = {
            source_key_columns[i]:
            row[common_key_columns[i]]
            for i in range(
                len(common_key_columns)
            )
        }

        key_differences.append({

            "DifferenceType":
                "Source Only",

            **key_values

        })


    # --------------------------------------------------------
    # Target Only Keys
    # --------------------------------------------------------

    for _, row in target_only.iterrows():

        key_values = {
            target_key_columns[i]:
            row[common_key_columns[i]]
            for i in range(
                len(common_key_columns)
            )
        }

        key_differences.append({

            "DifferenceType":
                "Target Only",

            **key_values

        })


    mismatch_df = pd.DataFrame(
        key_differences
    )


    # --------------------------------------------------------
    # Return Key Comparison Result
    # --------------------------------------------------------

    return {

        "SourceOnlyKeyCount":
            len(source_only),

        "TargetOnlyKeyCount":
            len(target_only),

        "MismatchDataFrame":
            mismatch_df
    }


# ============================================================
# MAIN COUNT VALIDATION
# ============================================================

def test_oracle_to_mysql_count(
    oracle_engine,
    mysql_engine
):

    # --------------------------------------------------------
    # Read Excel
    # --------------------------------------------------------

    mapping_df = pd.read_excel(
        EXCEL_PATH
    )


    # --------------------------------------------------------
    # Required Excel columns
    # --------------------------------------------------------

    required_columns = {
        "SerialNo",
        "SourceTable",
        "TargetTable",
        "SourceCountQuery",
        "TargetCountQuery",
        "SourceKeyQuery",
        "TargetKeyQuery"
    }

    missing_columns = (
        required_columns
        -
        set(mapping_df.columns)
    )

    if missing_columns:

        pytest.fail(
            "Missing columns in Excel: "
            f"{missing_columns}"
        )


    # --------------------------------------------------------
    # Filter SerialNo
    # --------------------------------------------------------

    if SERIAL_TO_RUN is not None:

        mapping_df = mapping_df[
            mapping_df["SerialNo"].isin(
                SERIAL_TO_RUN
            )
        ]


    if mapping_df.empty:

        pytest.fail(
            f"No mapping found for SerialNo "
            f"{SERIAL_TO_RUN}"
        )


    results = []


    # ========================================================
    # COLLECT ALL KEY MISMATCHES
    # ========================================================

    all_key_mismatches = []


    # ========================================================
    # PROCESS EACH TABLE
    # ========================================================

    for _, row in mapping_df.iterrows():

        serial_no = row[
            "SerialNo"
        ]

        source_table = row[
            "SourceTable"
        ]

        target_table = row[
            "TargetTable"
        ]

        source_count_query = row[
            "SourceCountQuery"
        ]

        target_count_query = row[
            "TargetCountQuery"
        ]

        source_key_query = row[
            "SourceKeyQuery"
        ]

        target_key_query = row[
            "TargetKeyQuery"
        ]


        print(
            f"\n🔄 Count validation: "
            f"{source_table} → "
            f"{target_table} "
            f"(SerialNo: {serial_no})"
        )


        try:

            # ------------------------------------------------
            # Get Oracle count
            # ------------------------------------------------

            print(
                "   Reading Oracle count..."
            )

            source_count = get_count(
                source_count_query,
                oracle_engine
            )

            print(
                f"   Oracle count: "
                f"{source_count}"
            )


            # ------------------------------------------------
            # Get MySQL count
            # ------------------------------------------------

            print(
                "   Reading MySQL count..."
            )

            target_count = get_count(
                target_count_query,
                mysql_engine
            )

            print(
                f"   MySQL count: "
                f"{target_count}"
            )


            # ------------------------------------------------
            # Compare counts
            # ------------------------------------------------

            comparison = compare_count(
                source_count,
                target_count
            )

            print(
                f"   Difference: "
                f"{comparison['CountDifference']}"
            )

            print(
                f"   Count Status: "
                f"{comparison['Status']}"
            )


            # ------------------------------------------------
            # Default key comparison result
            # ------------------------------------------------

            key_comparison = {

                "SourceOnlyKeyCount": 0,

                "TargetOnlyKeyCount": 0,

                "MismatchDataFrame":
                    pd.DataFrame()
            }


            # ------------------------------------------------
            # Compare keys
            # ------------------------------------------------

            print(
                "   Reading Oracle keys..."
            )

            source_key_df = get_keys(
                source_key_query,
                oracle_engine
            )


            print(
                "   Reading MySQL keys..."
            )

            target_key_df = get_keys(
                target_key_query,
                mysql_engine
            )


            key_comparison = compare_keys(
                source_key_df=
                    source_key_df,

                target_key_df=
                    target_key_df
            )


            print(
                f"   Source Only keys: "
                f"{key_comparison['SourceOnlyKeyCount']}"
            )

            print(
                f"   Target Only keys: "
                f"{key_comparison['TargetOnlyKeyCount']}"
            )


            # ------------------------------------------------
            # Add table information to key mismatches
            # ------------------------------------------------

            mismatch_df = (
                key_comparison[
                    "MismatchDataFrame"
                ]
            )

            if not mismatch_df.empty:

                mismatch_df.insert(
                    0,
                    "SerialNo",
                    serial_no
                )

                mismatch_df.insert(
                    1,
                    "SourceTable",
                    source_table
                )

                mismatch_df.insert(
                    2,
                    "TargetTable",
                    target_table
                )

                all_key_mismatches.append(
                    mismatch_df
                )


            # ------------------------------------------------
            # Final status is based on COUNT only
            # ------------------------------------------------

            if comparison["CountDifference"] == 0:

                final_status = "Matched"

                if (
                    key_comparison[
                        "SourceOnlyKeyCount"
                    ] > 0

                    or

                    key_comparison[
                        "TargetOnlyKeyCount"
                    ] > 0
                ):

                    print(
                        "\033[91m"
                        "   ⚠ Count matched, but "
                        "Join Key values have mismatch."
                        "\033[0m"
                    )

            else:

                final_status = "Mismatched"


            # ------------------------------------------------
            # Add final result
            # ------------------------------------------------

            results.append({

                "SerialNo":
                    serial_no,

                "SourceTable":
                    source_table,

                "TargetTable":
                    target_table,

                "SourceRowCount":
                    comparison[
                        "SourceRowCount"
                    ],

                "TargetRowCount":
                    comparison[
                        "TargetRowCount"
                    ],

                "CountDifference":
                    comparison[
                        "CountDifference"
                    ],

                "SourceOnlyKeyCount":
                    key_comparison[
                        "SourceOnlyKeyCount"
                    ],

                "TargetOnlyKeyCount":
                    key_comparison[
                        "TargetOnlyKeyCount"
                    ],

                "Status":
                    final_status,

                "RunTimestamp":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            })


        except Exception as e:

            print(
                f"❌ Error comparing "
                f"{source_table}: {e}"
            )


            results.append({

                "SerialNo":
                    serial_no,

                "SourceTable":
                    source_table,

                "TargetTable":
                    target_table,

                "SourceRowCount":
                    None,

                "TargetRowCount":
                    None,

                "CountDifference":
                    None,

                "SourceOnlyKeyCount":
                    None,

                "TargetOnlyKeyCount":
                    None,

                "Status":
                    "ERROR",

                "Error":
                    str(e),

                "RunTimestamp":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            })


    # ========================================================
    # SAVE SUMMARY
    # ========================================================

    summary_path = os.path.join(
        OUTPUT_FOLDER,
        "count_validation_summary.csv"
    )

    result_df = pd.DataFrame(
        results
    )


    # --------------------------------------------------------
    # Keep only latest result for executed SerialNo
    # --------------------------------------------------------

    if os.path.exists(
        summary_path
    ):

        existing_df = pd.read_csv(
            summary_path
        )

        existing_df = existing_df[
            ~existing_df[
                "SerialNo"
            ].isin(
                result_df[
                    "SerialNo"
                ]
            )
        ]


        final_df = pd.concat(
            [
                existing_df,
                result_df
            ],
            ignore_index=True
        )

    else:

        final_df = result_df


    final_df.to_csv(
        summary_path,
        index=False
    )


    print(
        f"\n📄 Count summary saved: "
        f"{summary_path}"
    )


    # ========================================================
    # SAVE CONSOLIDATED KEY MISMATCHES
    # ========================================================

    key_mismatch_path = os.path.join(
        OUTPUT_FOLDER,
        "key_mismatches.csv"
    )


    # --------------------------------------------------------
    # Combine mismatches from all tables
    # --------------------------------------------------------

    if all_key_mismatches:

        current_key_mismatches = pd.concat(
            all_key_mismatches,
            ignore_index=True
        )

    else:

        current_key_mismatches = (
            pd.DataFrame()
        )


    # --------------------------------------------------------
    # Keep only latest key mismatch result
    # for executed SerialNo
    # --------------------------------------------------------

    if os.path.exists(
        key_mismatch_path
    ):

        existing_key_df = pd.read_csv(
            key_mismatch_path
        )

        existing_key_df = existing_key_df[
            ~existing_key_df[
                "SerialNo"
            ].isin(
                result_df[
                    "SerialNo"
                ]
            )
        ]


        final_key_df = pd.concat(
            [
                existing_key_df,
                current_key_mismatches
            ],
            ignore_index=True
        )

    else:

        final_key_df = (
            current_key_mismatches
        )


    # --------------------------------------------------------
    # Save only when key mismatches exist
    # --------------------------------------------------------

    if not final_key_df.empty:

        final_key_df.to_csv(
            key_mismatch_path,
            index=False
        )

        print(
            f"🔑 Key mismatch report saved: "
            f"{key_mismatch_path}"
        )

    else:

        # Remove old empty/stale report
        if os.path.exists(
            key_mismatch_path
        ):
            os.remove(
                key_mismatch_path
            )

        print(
            "🔑 No Join Key mismatches found."
        )


    # ========================================================
    # FAIL PYTEST IF COUNT VALIDATION FAILED
    # ========================================================

    failed_tables = [
        result["SourceTable"]
        for result in results
        if result.get("Status")
        !=
        "Matched"
    ]


    if failed_tables:

        pytest.fail(
            "Oracle → MySQL count validation "
            "failed for: "
            +
            ", ".join(
                failed_tables
            )
        )

