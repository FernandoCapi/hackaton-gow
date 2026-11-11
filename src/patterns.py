"""Patterns shown in the panel, computed from the database (docs/padroes.md, in numbers).

    python -m src.patterns     # -> artifacts/patterns.json (aggregates only, never committed)

Rates come from mature historical loans (the same base as the risk model); how the current
policy treats each group is measured on the 2,000 new orders.
"""
import json

import pandas as pd

import config
from src.features import features_at
from src.policy import current_policy
from src.risk_model import training_set
from src.schemas import Pattern

PATTERNS_FILE = config.ARTIFACTS / "patterns.json"
MIN_CUSTOMERS = 10  # below this a rate is noise, the pattern is left out


def _bands(column: str, edges: list[float], labels: list[str]):
    """Chart groups: one mask per band of `column` (right-closed bands)."""
    return [(label, lambda o, lo=lo, hi=hi: (o[column] > lo) & (o[column] <= hi))
            for label, lo, hi in zip(labels, edges[:-1], edges[1:])]


INF = float("inf")

# (id, "Clientes ..." phrase, group mask, chart groups)
DEFINITIONS = [
    ("outflow_over_inflow", "Clientes cujas saídas consomem mais de 90% do que entra na conta",
     lambda o: o.saidas_sobre_entradas > 0.90,
     _bands("saidas_sobre_entradas", [-INF, 0.70, 0.90, INF], ["Até 70%", "70% a 90%", "Acima de 90%"])),
    ("recent_overdraft", "Clientes com cheque especial em 2 ou mais dos 3 meses antes do pedido",
     lambda o: o.cheque_recente_meses >= 2,
     _bands("cheque_recente_meses", [-INF, 0, 1, INF], ["Nenhum mês", "1 mês", "2 ou 3 meses"])),
    ("account_drained", "Clientes que tiraram da conta, de uma vez, 3 vezes ou mais a saída típica antes do pedido",
     lambda o: o.dreno >= 3,
     [("Menos de 2x", lambda o: o.dreno < 2), ("2x a 3x", lambda o: (o.dreno >= 2) & (o.dreno < 3)),
      ("3x ou mais", lambda o: o.dreno >= 3)]),
    ("request_above_capacity", "Clientes que pediram uma parcela acima de 30% da renda (a regra atual corta o valor)",
     lambda o: o.pedido_acima_30 == 1,
     [("Pedido cabia na renda", lambda o: o.pedido_acima_30 == 0),
      ("Pedido acima de 30% da renda", lambda o: o.pedido_acima_30 == 1)]),
    ("installment_over_slack", "Clientes cuja parcela passa de 45% da sobra do mês (entradas menos saídas)",
     lambda o: o.parcela_sobre_folga > 0.45,
     _bands("parcela_sobre_folga", [-INF, 0.25, 0.45, INF], ["Até 25% da sobra", "25% a 45%", "Acima de 45%"])),
    ("installment_over_income", "Clientes cuja parcela passa de 25% da renda efetiva",
     lambda o: o.parcela_sobre_renda_efetiva > 0.25,
     _bands("parcela_sobre_renda_efetiva", [-INF, 0.20, 0.25, 0.30, INF],
            ["Até 20% da renda", "20% a 25%", "25% a 30%", "Acima de 30%"])),
    ("inflated_income", "Clientes cujas entradas na conta ficam abaixo de 60% da renda declarada",
     lambda o: o.entradas_sobre_renda < 0.60,
     [("Abaixo de 60%", lambda o: o.entradas_sobre_renda < 0.60),
      ("60% a 90%", lambda o: (o.entradas_sobre_renda >= 0.60) & (o.entradas_sobre_renda < 0.90)),
      ("90% ou mais", lambda o: o.entradas_sobre_renda >= 0.90)]),
    ("credit_seeking", "Clientes com 8 ou mais consultas ao CPF em 90 dias",
     lambda o: o.consultas_90_dias >= 8,
     _bands("consultas_90_dias", [-INF, 3, 7, INF], ["Até 3 consultas", "4 a 7", "8 ou mais"])),
    ("new_account", "Clientes com conta aberta há até 3 meses",
     lambda o: o.meses_conta <= 3,
     _bands("meses_conta", [-INF, 3, 12, INF], ["Até 3 meses", "4 a 12 meses", "Mais de 12 meses"])),
    ("heavy_other_debts", "Clientes cuja parcela somada às dívidas em outras instituições passa de 44% da renda",
     lambda o: o.comprometimento_total > 0.44,
     _bands("comprometimento_total", [-INF, 0.30, 0.44, INF], ["Até 30% da renda", "30% a 44%", "Acima de 44%"])),
    # Only the pilot approved these groups, and its loans are still young (< 12 months):
    # they are compared with the pilot's own average.
    ("low_score", "Clientes do piloto com score do bureau até 600 (a regra atual nega)",
     lambda o: o.score <= 600,
     _bands("score", [-INF, 550, 600, 700, INF], ["Até 550", "551 a 600", "601 a 700", "Acima de 700"]), "pilot"),
    ("income_1500_2000", "Clientes do piloto com renda declarada entre R$ 1.500 e R$ 2.000 (a regra atual nega)",
     lambda o: (o.renda_declarada > 1500) & (o.renda_declarada <= 2000),
     _bands("renda_declarada", [-INF, 2000, 4000, INF], ["Até R$ 2.000", "R$ 2.000 a R$ 4.000", "Acima de R$ 4.000"]),
     "pilot"),
    ("active_restriction", "Clientes do piloto com restrição ativa no bureau (a regra atual nega)",
     lambda o: o.restricoes_ativas >= 1,
     [("Sem restrição", lambda o: o.restricoes_ativas == 0), ("1 ou mais", lambda o: o.restricoes_ativas >= 1)],
     "pilot"),
]


def _pct(value: float) -> str:
    return f"{value * 100:.1f}".removesuffix(".0").replace(".", ",") + "%"


def _int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _policy_view(approved_share: float) -> str:
    if approved_share >= 0.9:
        return "approves"
    if approved_share <= 0.1:
        return "denies"
    return "mixed"


def build(orders: pd.DataFrame) -> list[Pattern]:
    pilot = orders[orders.situacao_final.notna() & orders.politica_aplicada.eq("piloto")]
    bases = {
        "mature": (training_set(orders), "da média"),
        "pilot": (features_at(pilot, pilot.valor_aprovado), "da média do piloto"),
    }
    new = orders[orders.tipo_base.eq("novo")]
    new_approved = current_policy(new).current_decision.eq("APROVADO")

    patterns = []
    for pattern_id, phrase, mask, groups, *base in DEFINITIONS:
        hist, average_label = bases[base[0] if base else "mature"]
        overall = float(hist.calote.mean())
        in_group = mask(hist)
        customers = int(hist.loc[in_group, "id_cliente"].nunique())
        if customers < MIN_CUSTOMERS:
            continue
        rate = float(hist.loc[in_group, "calote"].mean())
        new_in_group = mask(new)
        chart = [
            {"label": label, "default_rate": round(float(hist.loc[m, "calote"].mean()), 4),
             "customers": int(hist.loc[m, "id_cliente"].nunique())}
            for label, group_mask in groups
            if (m := group_mask(hist)).sum() >= MIN_CUSTOMERS
        ]
        patterns.append(Pattern(
            id=pattern_id,
            sentence=f"{phrase} têm inadimplência de {_pct(rate)}, contra {_pct(overall)} {average_label}. "
                     f"Afeta {_int(customers)} clientes.",
            group_description=phrase.removeprefix("Clientes "),
            group_default_rate=round(rate, 4),
            overall_default_rate=round(overall, 4),
            customers_affected=customers,
            direction="worse" if rate > overall else "better",
            current_policy_view=_policy_view(float(new_approved[new_in_group].mean()) if new_in_group.any() else 0.5),
            groups=chart,
        ))
    return patterns


def save(orders: pd.DataFrame) -> list[Pattern]:
    patterns = build(orders)
    config.ARTIFACTS.mkdir(exist_ok=True)
    PATTERNS_FILE.write_text(
        json.dumps([p.model_dump(mode="json") for p in patterns], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return patterns


def main():
    from src.features import load_orders

    for pattern in save(load_orders()):
        print(f"- {pattern.sentence}")
    print(f"Gravado em {PATTERNS_FILE}")


if __name__ == "__main__":
    main()
