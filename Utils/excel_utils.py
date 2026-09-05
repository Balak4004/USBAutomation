

import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

TEST_CASE_FILE = os.path.join(BASE_DIR, "Data", "table_validation_cases.xlsx")
MISMATCH_FILE = os.path.join(BASE_DIR, "Data", "mismatch_results.xlsx")

SHEET_NAME = "test_cases"

def read_test_cases():
    df = pd.read_excel(TEST_CASE_FILE, sheet_name=SHEET_NAME)
    df["status"] = df["status"].astype("object")
    return df

def update_status(df):
    df.to_excel(TEST_CASE_FILE, sheet_name=SHEET_NAME, index=False)

def write_mismatch(sheet_name, df):
    mode = "a" if os.path.exists(MISMATCH_FILE) else "w"
    with pd.ExcelWriter(MISMATCH_FILE, engine="openpyxl", mode=mode) as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
