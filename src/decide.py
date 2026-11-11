"""Generates the official decisions file from scratch.

    python -m src.decide        # -> output/<TEAM_ID>_final.csv (+ artifacts/decisions_novos.csv)

Uses the policy approved by the analyst (artifacts/approved_policy.json) or, if none, the
default parameters. New orders without bureau data in the cache are fetched first; any
still missing are denied ("bureau indisponível"), never decided blind.
"""
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
    ensure_bureau()
    from src.simulate import Engine  # imported after the cache is complete

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
    print(f"Negados por passo: {decisions[~approved].denied_at.value_counts().to_dict()}")
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
