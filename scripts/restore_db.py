"""Restore the challenge database into the Docker Postgres.

    python scripts/restore_db.py <file-or-folder> [--db hackaton] [--keep]

Accepts a plain SQL dump (.sql, .sql.gz), a pg_dump custom/tar archive (.dump, .backup,
.tar) or a folder of CSV files (one table per file). The target database is DROPPED and
recreated unless --keep is passed.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMPS = ROOT / "dumps"
USER = "hackaton"

sys.path.insert(0, str(ROOT))


def in_container(*args, check=True):
    command = ["docker", "compose", "exec", "-T", "db", *args]
    return subprocess.run(command, cwd=ROOT, check=check)


def psql(database, sql):
    in_container("psql", "-U", USER, "-d", database, "-v", "ON_ERROR_STOP=1", "-c", sql)


def recreate(database):
    print(f"Recriando o banco '{database}' (conteudo anterior apagado)", flush=True)
    psql("postgres", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    psql("postgres", f'CREATE DATABASE "{database}"')


def staged(path):
    """Make the file visible inside the container, which mounts ./dumps at /dumps."""
    if DUMPS not in path.parents:
        DUMPS.mkdir(exist_ok=True)
        shutil.copy2(path, DUMPS / path.name)
        path = DUMPS / path.name
    return "/dumps/" + path.relative_to(DUMPS).as_posix()


def is_archive(path):
    if path.suffix.lower() == ".tar":
        return True
    with path.open("rb") as handle:
        return handle.read(5) == b"PGDMP"


def restore_file(path, database):
    target = staged(path)
    if is_archive(path):
        result = in_container(
            "pg_restore", "-U", USER, "-d", database, "--no-owner", "--no-privileges", target,
            check=False,
        )
    elif path.suffix.lower() == ".gz":
        result = in_container(
            "sh", "-c", f'gunzip -c "{target}" | psql -U {USER} -d "{database}"', check=False
        )
    else:
        result = in_container("psql", "-U", USER, "-d", database, "-f", target, check=False)
    if result.returncode != 0:
        print(f"Aviso: o restore terminou com codigo {result.returncode}; confira as mensagens acima.")


def restore_csv_folder(folder, database):
    import pandas as pd
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    import config

    url = make_url(config.DATABASE_URL).set(database=database)
    engine = create_engine(url)
    for csv in sorted(folder.glob("*.csv")):
        frame = pd.read_csv(csv, sep=None, engine="python")
        frame.to_sql(csv.stem.lower(), engine, index=False, if_exists="replace")
        print(f"{csv.name}: {len(frame)} linhas")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("--db", default="hackaton")
    parser.add_argument("--keep", action="store_true", help="nao recriar o banco antes")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.exists():
        sys.exit(f"Nao encontrado: {source}")

    if not args.keep:
        recreate(args.db)
    if source.is_dir():
        restore_csv_folder(source, args.db)
    else:
        restore_file(source, args.db)

    psql(
        args.db,
        "SELECT table_schema, COUNT(*) AS tabelas FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') "
        "GROUP BY 1 ORDER BY 1",
    )
    if args.db != "hackaton":
        print(f"Lembrete: ajuste DATABASE_URL no .env para o banco '{args.db}'.")


if __name__ == "__main__":
    main()
