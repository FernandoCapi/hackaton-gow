"""Generates the official decisions file from scratch, in one command.

    python -m src.decide             # -> output/<TEAM_ID>_final.csv (+ artifacts/decisions_novos.csv)
    python -m src.decide --retrain   # retrains the risk model before deciding

On a fresh machine it prepares what is missing (neither goes to Git):
  1. bureau of the new orders (data/bureau_novos.csv), fetched from the API with retries;
     orders still without bureau are denied ("bureau indisponível"), never decided blind;
  2. the risk model (artifacts/risk_model.joblib), trained from the database.
Uses the policy approved by the analyst (artifacts/approved_policy.json) or, if none, the
default parameters.
"""
import argparse
import csv
import io
import sys
from pathlib import Path

import pandas as pd

import config
from src.schemas import Policy, PolicyParams

APPROVED_POLICY = config.ARTIFACTS / "approved_policy.json"
DECISIONS_FILE = config.ARTIFACTS / "decisions_novos.csv"
HEADER = ["id_pedido", "decisao", "valor_aprovado"]


def output_file() -> Path:
    return config.OUTPUT / f"{config.TEAM_ID}_final.csv"


def policy_params() -> tuple[PolicyParams, str]:
    if APPROVED_POLICY.exists():
        policy = Policy.model_validate_json(APPROVED_POLICY.read_text(encoding="utf-8"))
        return policy.params, f"versão {policy.version} aprovada por {policy.approved_by}"
    return PolicyParams(), "parâmetros padrão (nenhuma versão aprovada ainda)"


def check_database() -> None:
    """Stops with an actionable message when the challenge database is not reachable."""
    from src.db import read_sql

    try:
        counts = read_sql("SELECT tipo_base, count(*) AS n FROM hackathon.pedidos GROUP BY 1")
    except Exception as error:  # noqa: BLE001 - any connection or schema problem
        sys.exit(
            "Banco do desafio indisponível. Confira:\n"
            "  - Docker aberto e o container do banco no ar (docker compose up -d --wait)\n"
            "  - dump restaurado no banco fortuna (python scripts/restore_db.py <dump> --db fortuna)\n"
            "  - DATABASE_URL no .env apontando para o banco fortuna\n"
            f"Erro: {type(error).__name__}: {str(error).splitlines()[0]}"
        )
    found = dict(zip(counts.tipo_base, counts.n))
    print(f"Banco: {found.get('historico', 0)} pedidos históricos, {found.get('novo', 0)} novos")


def ensure_model(retrain: bool = False) -> None:
    from src import risk_model

    if risk_model.is_trained() and not retrain:
        return
    print("Treinando o modelo de risco (alguns segundos)..." if not retrain else "Retreinando o modelo de risco...")
    metrics = risk_model.train_and_save()
    validation = metrics["temporal_validation"]
    print(f"Modelo pronto: {metrics['trained_orders']} contratos, nota {validation['auc']:.2f} em pedidos "
          f"nunca vistos (score do bureau: {validation['auc_score_bureau']:.2f})")


def ensure_bureau() -> None:
    """Fetches bureau data for new clients missing from the cache (API only serves new ones)."""
    from src import bureau

    missing = [client for client in bureau.new_clients() if client not in bureau.load_cache()]
    if not missing:
        return
    if not (config.BUREAU_URL and config.BUREAU_TOKEN):
        print(f"Aviso: {len(missing)} clientes novos sem bureau e sem BUREAU_TOKEN; serão negados.")
        return
    print(f"Buscando bureau de {len(missing)} clientes novos que faltam no cache...")
    bureau.fetch_missing(missing)


def csv_text(decisions: pd.DataFrame) -> str:
    """Official format: UTF-8, comma, exact header, APROVADO/NEGADO, 2 decimals, 0.00 if denied."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for order_id, row in decisions.sort_index().iterrows():
        amount = row.approved_amount if row.decision == "APROVADO" else 0.0
        writer.writerow([order_id, row.decision, f"{amount:.2f}"])
    return buffer.getvalue()


def write_csv(decisions: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(csv_text(decisions), encoding="utf-8", newline="")


def validate_csv(path: Path, requested: pd.Series) -> list[str]:
    """Checks every rule of the manual. `requested` = valor_solicitado indexed by id_pedido."""
    problems = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["arquivo não é UTF-8"]
    if text.startswith("﻿"):
        problems.append("arquivo tem BOM")
    rows = list(csv.reader(text.splitlines()))
    if not rows or rows[0] != HEADER:
        return problems + [f"cabeçalho deve ser exatamente {','.join(HEADER)}"]
    ids = [row[0] for row in rows[1:]]
    if len(ids) != len(set(ids)):
        problems.append("id_pedido repetido")
    if set(ids) != set(requested.index):
        problems.append(f"ids diferentes da base de novos ({len(set(requested.index) - set(ids))} faltando, "
                        f"{len(set(ids) - set(requested.index))} a mais)")
    for line, row in enumerate(rows[1:], start=2):
        if len(row) != 3:
            problems.append(f"linha {line}: {len(row)} colunas")
            continue
        order_id, decision, amount = row
        if decision not in ("APROVADO", "NEGADO"):
            problems.append(f"linha {line}: decisão '{decision}'")
        if amount != f"{float(amount):.2f}" or "," in amount:
            problems.append(f"linha {line}: valor '{amount}' fora do formato 0.00")
            continue
        value = float(amount)
        if decision == "NEGADO" and value != 0:
            problems.append(f"linha {line}: negado com valor {amount}")
        if decision == "APROVADO":
            if value <= 0:
                problems.append(f"linha {line}: aprovado sem valor")
            if order_id in requested.index and value > min(requested[order_id], 30000) + 0.005:
                problems.append(f"linha {line}: valor acima do pedido ou de R$ 30 mil")
            if value < 500:
                problems.append(f"linha {line}: valor abaixo de R$ 500")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--retrain", action="store_true", help="retreina o modelo antes de decidir")
    args = parser.parse_args()

    check_database()
    ensure_bureau()
    ensure_model(args.retrain)
    from src.simulate import Engine  # imported after cache and model are ready

    params, origin = policy_params()
    engine = Engine()
    decisions = engine.decide_new(params)
    new = engine.new_grid.orders

    path = output_file()
    write_csv(decisions, path)
    detail = decisions.join(new[["id_cliente", "valor_solicitado", "prazo_meses"]])
    config.ARTIFACTS.mkdir(exist_ok=True)
    detail.to_csv(DECISIONS_FILE, index_label="id_pedido")

    problems = validate_csv(path, new.valor_solicitado)
    approved = decisions.decision.eq("APROVADO")
    no_bureau = int(new.bureau_ausente.sum())
    print(f"Política: {origin}")
    print(f"Arquivo: {path.relative_to(config.ROOT)} | {len(decisions)} pedidos | "
          f"{int(approved.sum())} aprovados (R$ {decisions.approved_amount.sum():,.2f}) | "
          f"{int((~approved).sum())} negados | {int(decisions.changed_vs_current.sum())} diferentes da política atual")
    from src.policy import step_title

    by_step = decisions[~approved].denied_at.value_counts()
    print("Negados por passo: " + "; ".join(f"{step_title(step, params)}: {count}" for step, count in by_step.items()))
    if no_bureau:
        print(f"Aviso: {no_bureau} pedidos negados por bureau indisponível")
    if problems:
        print("ARQUIVO INVÁLIDO:")
        for problem in problems[:20]:
            print(f"  - {problem}")
        sys.exit(1)
    print("Formato validado: pronto para enviar.")


if __name__ == "__main__":
    main()
