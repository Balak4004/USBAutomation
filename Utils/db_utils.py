
import pandas as pd

def row_count_validation(src_df, tgt_df):
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

import oracledb
from sqlalchemy import create_engine

oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_21_20")


# ---------- ORACLE SOURCE ----------
def get_oracle_engine():
    username = "hr"
    password = "hr"
    host = "localhost"
    port = "1521"
    service = "xe"

    connection_string = (
        f"oracle+oracledb://{username}:{password}@{host}:{port}/?service_name={service}"
    )

    engine = create_engine(connection_string)
    return engine


# ---------- MYSQL TARGET ----------
def get_mysql_engine():
    username = "root"
    password = "admin%402024"
    host = "localhost"
    port = "3306"
    database = "retaildwh"

    connection_string = (
        f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}"
    )

    engine = create_engine(connection_string)
    return engine


def execute_query(engine, query):
    return pd.read_sql(query, engine)

'''
# ---------- ORACLE ----------
def get_oracle_engine():
    return create_engine(
        "oracle+oracledb://hr:hr@localhost:1521/?service_name=xe"
    )

# ---------- MYSQL ----------
def get_mysql_engine():
    return create_engine(
        "mysql+mysqlconnector://root:admin%402024@localhost:3306/retaildwh"
    )

def execute_query(engine, query):
    return pd.read_sql(query, engine)
'''