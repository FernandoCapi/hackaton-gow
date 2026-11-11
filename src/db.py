import pandas as pd
from sqlalchemy import create_engine, text

import config


def engine():
    return create_engine(config.DATABASE_URL)


def read_sql(query: str) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(query), conn)


def load_dataset() -> pd.DataFrame:
    return read_sql(config.DATASET_SQL.read_text(encoding="utf-8"))
