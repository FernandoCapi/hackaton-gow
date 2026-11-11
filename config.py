"""Single place to adapt the pipeline to the challenge. Nothing else names columns."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://hackaton:hackaton@localhost:5432/hackaton"
)

# Query that returns ONE row per entity to score, with the target column.
DATASET_SQL = ROOT / "sql" / "dataset.sql"

TARGET = "churned"
ID_COLUMN = "customer_id"

# Set to a date column to validate on the most recent rows (time split).
# None = random stratified split.
DATE_COLUMN = None

# "classification" (binary target) or "regression" (numeric target).
TASK = "classification"

# Columns to exclude from the model: identifiers, free text, and anything that is
# only known AFTER the outcome (leakage).
DROP_COLUMNS = []

TEST_SIZE = 0.25
RANDOM_STATE = 42

# How the business reads the target, used by the dashboard and the explanation.
ENTITY_LABEL = "cliente"
POSITIVE_LABEL = "cancelamento"

ARTIFACTS = ROOT / "artifacts"
