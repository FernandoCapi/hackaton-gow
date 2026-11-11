"""Fetch bureau data for the new orders, with retries and a local cache.

    python -m src.bureau            # fetch what is missing from the cache
    python -m src.bureau --check    # only report cache coverage

The API fails with 503 and is sometimes slow on purpose. Answers are deterministic per
client, so every successful answer is cached in data/ (git-ignored) and never fetched
again. Re-run until nothing is missing.
"""
import argparse
import csv
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import config
from src.db import read_sql

FIELDS = [
    "id_cliente",
    "score",
    "restricoes_ativas",
    "parcelas_outras_instituicoes",
    "consultas_90_dias",
    "meses_historico_bureau",
]
WORKERS = 16
TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 8
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_MAX_SECONDS = 10
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PermanentError(Exception):
    """Answer that will not change by retrying (401, 404, malformed body)."""


def new_clients() -> list[str]:
    frame = read_sql(
        "SELECT id_cliente FROM hackathon.pedidos WHERE tipo_base = 'novo' ORDER BY id_cliente"
    )
    return frame["id_cliente"].tolist()


def load_cache() -> dict[str, dict]:
    if not config.BUREAU_CACHE.exists():
        return {}
    with config.BUREAU_CACHE.open(encoding="utf-8", newline="") as handle:
        return {row["id_cliente"]: row for row in csv.DictReader(handle)}


def fetch_one(session: requests.Session, client_id: str, stats: "Stats") -> dict:
    url = f"{config.BUREAU_URL}/v1/bureau/{client_id}"
    headers = {"Authorization": f"Bearer {config.BUREAU_TOKEN}"}
    last_problem = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as error:
            last_problem = type(error).__name__
            stats.add(last_problem)
        else:
            if response.status_code == 200:
                body = response.json()
                missing = [field for field in FIELDS if field not in body]
                if missing or body["id_cliente"] != client_id:
                    raise PermanentError(f"resposta inesperada (faltando {missing})")
                return {field: body[field] for field in FIELDS}
            if response.status_code in (401, 403):
                raise PermanentError(f"HTTP {response.status_code}: confira BUREAU_TOKEN")
            if response.status_code == 404:
                raise PermanentError("HTTP 404: cliente fora da base de novos pedidos")
            if response.status_code not in RETRYABLE_STATUS:
                raise PermanentError(f"HTTP {response.status_code}")
            last_problem = f"HTTP {response.status_code}"
            stats.add(last_problem)
        delay = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))
        time.sleep(delay * random.uniform(0.5, 1.0))  # jitter: avoid retrying in lockstep
    raise TimeoutError(f"{MAX_ATTEMPTS} tentativas sem sucesso (ultima: {last_problem})")


class Stats:
    """Thread-safe counter of transient failures."""

    def __init__(self):
        self._counts = Counter()
        self._lock = threading.Lock()

    def add(self, key: str):
        with self._lock:
            self._counts[key] += 1

    def items(self):
        return self._counts.items()


def fetch_missing(missing: list[str]) -> tuple[int, dict[str, str]]:
    config.DATA.mkdir(exist_ok=True)
    new_file = not config.BUREAU_CACHE.exists()
    stats = Stats()
    failures: dict[str, str] = {}
    write_lock = threading.Lock()
    done = 0
    started = time.monotonic()

    with config.BUREAU_CACHE.open("a", encoding="utf-8", newline="") as handle, requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter(pool_connections=WORKERS, pool_maxsize=WORKERS)
        session.mount("https://", adapter)
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(fetch_one, session, client, stats): client for client in missing}
            for future in as_completed(futures):
                client = futures[future]
                try:
                    row = future.result()
                except PermanentError as error:
                    failures[client] = str(error)
                    if "BUREAU_TOKEN" in str(error):
                        pool.shutdown(cancel_futures=True)
                        break
                    continue
                except Exception as error:  # noqa: BLE001 - report and keep going
                    failures[client] = str(error)
                    continue
                with write_lock:
                    writer.writerow(row)
                    handle.flush()  # a crash keeps everything fetched so far
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(missing)} em {time.monotonic() - started:.0f}s", flush=True)

    retried = ", ".join(f"{key}={value}" for key, value in sorted(stats.items())) or "nenhuma"
    print(f"Falhas temporarias tratadas com nova tentativa: {retried}")
    return done, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="so mostra a cobertura do cache")
    args = parser.parse_args()

    clients = new_clients()
    cache = load_cache()
    missing = [client for client in clients if client not in cache]
    print(f"Clientes novos: {len(clients)} | em cache: {len(clients) - len(missing)} | faltando: {len(missing)}")
    if args.check or not missing:
        sys.exit(1 if missing else 0)

    if not config.BUREAU_URL or not config.BUREAU_TOKEN:
        sys.exit("Defina BUREAU_URL e BUREAU_TOKEN no .env")

    done, failures = fetch_missing(missing)
    print(f"Obtidos agora: {done} | ainda faltando: {len(missing) - done}")
    for client, reason in sorted(failures.items())[:20]:
        print(f"  {client}: {reason}")
    if failures:
        print("Rode de novo para tentar os que faltam.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
