

import pytest
from Utils.db_utils import get_oracle_engine, get_mysql_engine

@pytest.fixture(scope="session")
def oracle_engine():
    return get_oracle_engine()

@pytest.fixture(scope="session")
def mysql_engine():
    return get_mysql_engine()
