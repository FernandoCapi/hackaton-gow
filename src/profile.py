"""Schema overview of every table: rows, columns, types, nulls, distinct values, samples.

    python -m src.profile            # prints markdown
    python -m src.profile --save     # also writes docs/perfil-banco.md
"""
import sys

import config
from src.db import read_sql

TABLES_SQL = """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name
"""

COLUMNS_SQL = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = '{schema}' AND table_name = '{table}'
ORDER BY ordinal_position
"""

FOREIGN_KEYS_SQL = """
SELECT
    tc.table_name   AS from_table,
    kcu.column_name AS from_column,
    ccu.table_name  AS to_table,
    ccu.column_name AS to_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY 1, 2
"""


def profile_table(schema: str, table: str) -> str:
    qualified = f'"{schema}"."{table}"'
    rows = int(read_sql(f"SELECT COUNT(*) AS n FROM {qualified}")["n"][0])
    columns = read_sql(COLUMNS_SQL.format(schema=schema, table=table))

    lines = [f"## {schema}.{table} ({rows:,} linhas)", ""]
    lines.append("| coluna | tipo | nulos % | distintos | exemplos |")
    lines.append("|---|---|---|---|---|")
    for column, dtype in columns.itertuples(index=False):
        quoted = f'"{column}"'
        stats = read_sql(
            f"SELECT COUNT(*) - COUNT({quoted}) AS nulls, "
            f"COUNT(DISTINCT {quoted}) AS distinct_values FROM {qualified}"
        )
        samples = read_sql(
            f"SELECT DISTINCT {quoted}::text AS v FROM {qualified} "
            f"WHERE {quoted} IS NOT NULL LIMIT 3"
        )["v"].tolist()
        null_pct = 100 * int(stats["nulls"][0]) / rows if rows else 0
        examples = ", ".join(str(v)[:30] for v in samples).replace("|", "/")
        lines.append(
            f"| {column} | {dtype} | {null_pct:.1f} | "
            f"{int(stats['distinct_values'][0]):,} | {examples} |"
        )
    return "\n".join(lines)


def build() -> str:
    tables = read_sql(TABLES_SQL)
    sections = ["# Perfil do banco", ""]
    sections += [profile_table(s, t) + "\n" for s, t in tables.itertuples(index=False)]

    foreign_keys = read_sql(FOREIGN_KEYS_SQL)
    sections.append("## Relacionamentos (chaves estrangeiras)\n")
    if foreign_keys.empty:
        sections.append("Nenhuma FK declarada: inferir pelos nomes das colunas.")
    else:
        sections += [
            f"- {r.from_table}.{r.from_column} → {r.to_table}.{r.to_column}"
            for r in foreign_keys.itertuples(index=False)
        ]
    return "\n".join(sections) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    report = build()
    print(report)
    if "--save" in sys.argv:
        output = config.ROOT / "docs" / "perfil-banco.md"
        output.write_text(report, encoding="utf-8")
        print(f"Salvo em {output}")
