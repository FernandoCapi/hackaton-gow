"""One row per order with only information known at decision time.

    python -m src.features      # builds and summarizes the table (no files written)

Same code for historical and new orders. Bureau: historical orders use the
hackathon.bureau table (consulted on the order date); new orders use the API cache
(data/bureau_novos.csv). The API is never called for historical clients (it answers 404).

Definitions follow analysis/findings_*.md:
- effective income  = min(declared income, average monthly inflow)
- monthly slack     = average inflow - average outflow
- drain             = largest outflow of the last 3 months / median outflow of the client
- recent overdraft  = months with overdraft among the 3 before the order, ignoring the
                      oldest month of the statement (overdraft there is a data artifact)
"""
import numpy as np
import pandas as pd

import config
from src.db import read_sql

RATE = 0.03
MIN_AMOUNT = 500.0
MAX_AMOUNT = 30000.0
SLACK_FLOOR = 1.0  # avoids division by ~0 when inflow and outflow are equal

BUREAU_FIELDS = [
    "score",
    "restricoes_ativas",
    "parcelas_outras_instituicoes",
    "consultas_90_dias",
    "meses_historico_bureau",
]

# Features the risk model may use. Anything else (decision, approved amount, policy,
# outcome, installments, dates) is either leakage or a sensitive attribute.
MODEL_FEATURES = [
    "prazo_meses",
    "valor_solicitado",
    "score",
    "restricoes_ativas",
    "consultas_90_dias",
    "meses_historico_bureau",
    "outras_sobre_renda",
    "meses_conta",
    "mov_meses",
    "entradas_sobre_renda",
    "saidas_sobre_entradas",
    "entradas_cv",
    "pico_entradas",
    "dreno",
    "cheque_recente_meses",
    "pedido_acima_30",
    # amount-dependent (recomputed for each candidate amount by features_at)
    "parcela_sobre_renda_efetiva",
    "parcela_sobre_folga",
    "comprometimento_total",
]
AMOUNT_FEATURES = ["parcela_sobre_renda_efetiva", "parcela_sobre_folga", "comprometimento_total"]
CATEGORICAL_FEATURES = ["tipo_vinculo"]


def installment(amount, months):
    """Price table at 3% a month, as in the data dictionary."""
    amount = np.asarray(amount, dtype=float)
    months = np.asarray(months, dtype=float)
    return amount * RATE / (1 - (1 + RATE) ** (-months))


def max_amount_for_installment(max_installment, months):
    return np.asarray(max_installment, dtype=float) * (1 - (1 + RATE) ** (-np.asarray(months, dtype=float))) / RATE


def _movement() -> pd.DataFrame:
    mov = read_sql(
        "SELECT id_cliente, mes_referencia, total_entradas, entradas_salario, total_saidas, saldo_minimo, "
        "dias_cheque_especial FROM hackathon.movimentacao_mensal"
    )
    mov["mes_referencia"] = pd.to_datetime(mov["mes_referencia"])
    money = ["total_entradas", "entradas_salario", "total_saidas", "saldo_minimo"]
    mov[money] = mov[money].astype(float)
    mov = mov.sort_values(["id_cliente", "mes_referencia"])
    mov["pos_from_end"] = mov.groupby("id_cliente").cumcount(ascending=False)  # 0 = month before order
    mov["is_oldest"] = mov.groupby("id_cliente").cumcount() == 0
    mov["months"] = mov.groupby("id_cliente")["id_cliente"].transform("size")

    g = mov.groupby("id_cliente")
    out = pd.DataFrame(
        {
            "mov_meses": g.size(),
            "entradas_media": g.total_entradas.mean(),
            "saidas_media": g.total_saidas.mean(),
            "entradas_cv": g.total_entradas.std(ddof=0) / g.total_entradas.mean(),
            "saidas_sobre_entradas": g.total_saidas.sum() / g.total_entradas.sum(),
            "saidas_mediana": g.total_saidas.median(),
            "entradas_mediana": g.total_entradas.median(),
        }
    )
    last3 = mov[mov.pos_from_end < 3].groupby("id_cliente")
    out["saida_max_ult3"] = last3.total_saidas.max()
    out["entrada_max_ult3"] = last3.total_entradas.max()

    # Overdraft in the oldest month of a statement with more than one month is an artifact.
    usable = mov[(mov.pos_from_end < 3) & ~(mov.is_oldest & (mov.months > 1))]
    out["cheque_recente_meses"] = (
        usable.assign(flag=usable.dias_cheque_especial > 0).groupby("id_cliente").flag.sum()
    )
    out["cheque_recente_meses"] = out["cheque_recente_meses"].fillna(0).astype(int)
    # Shown to the analyst only (not model features).
    out["salario_media"] = g.entradas_salario.mean()
    out["saldo_minimo"] = g.saldo_minimo.min()
    real_months = mov[~(mov.is_oldest & (mov.months > 1))]
    out["dias_cheque_12m"] = real_months.groupby("id_cliente").dias_cheque_especial.sum()
    out["dias_cheque_12m"] = out["dias_cheque_12m"].fillna(0).astype(int)

    out["dreno"] = out.saida_max_ult3 / out.saidas_mediana.where(out.saidas_mediana > 0)
    out["pico_entradas"] = out.entrada_max_ult3 / out.entradas_mediana.where(out.entradas_mediana > 0)
    return out.drop(columns=["saida_max_ult3", "entrada_max_ult3", "saidas_mediana", "entradas_mediana"])


def _bureau_new() -> pd.DataFrame:
    """Bureau of new orders from the API cache. Missing clients come back as NaN."""
    if not config.BUREAU_CACHE.exists():
        return pd.DataFrame(columns=["id_cliente", *BUREAU_FIELDS])
    return pd.read_csv(config.BUREAU_CACHE, dtype={"id_cliente": str})


def load_orders() -> pd.DataFrame:
    """All orders (historical + new) with decision-time features and, for historical
    orders, the recorded decision and outcome (kept for evaluation, never as features)."""
    orders = read_sql(
        """
        SELECT p.id_pedido, p.id_cliente, p.data_pedido, p.valor_solicitado, p.prazo_meses,
               p.tipo_base, p.decisao, p.valor_aprovado, p.politica_aplicada, p.situacao_final,
               c.renda_declarada, c.tipo_vinculo, c.data_abertura_conta,
               b.score, b.restricoes_ativas, b.parcelas_outras_instituicoes,
               b.consultas_90_dias, b.meses_historico_bureau
        FROM hackathon.pedidos p
        JOIN hackathon.clientes c USING (id_cliente)
        LEFT JOIN hackathon.bureau b USING (id_pedido)
        """
    )
    is_new = orders.tipo_base.eq("novo")
    new_bureau = _bureau_new().set_index("id_cliente")
    for field in BUREAU_FIELDS:
        orders.loc[is_new, field] = orders.loc[is_new, "id_cliente"].map(new_bureau[field]).to_numpy()
    orders["bureau_ausente"] = orders[BUREAU_FIELDS].isna().any(axis=1)

    numeric = ["valor_solicitado", "valor_aprovado", "renda_declarada", *BUREAU_FIELDS]
    orders[numeric] = orders[numeric].astype(float)
    for column in ["data_pedido", "data_abertura_conta"]:
        orders[column] = pd.to_datetime(orders[column])

    orders = orders.merge(_movement(), left_on="id_cliente", right_index=True, how="left")

    orders["meses_conta"] = (orders.data_pedido - orders.data_abertura_conta).dt.days / 30.44
    orders["renda_efetiva"] = np.fmin(orders.renda_declarada, orders.entradas_media)
    orders["folga"] = orders.entradas_media - orders.saidas_media
    orders["entradas_sobre_renda"] = orders.entradas_media / orders.renda_declarada
    orders["outras_sobre_renda"] = orders.parcelas_outras_instituicoes / orders.renda_efetiva
    orders["valor_base"] = np.minimum(orders.valor_solicitado, MAX_AMOUNT)
    orders["pedido_acima_30"] = (
        installment(orders.valor_solicitado, orders.prazo_meses) > 0.30 * orders.renda_declarada
    ).astype(int)
    orders["tipo_vinculo"] = orders["tipo_vinculo"].astype("category")
    orders = features_at(orders, orders.valor_base)

    # Outcome (historical approved only). Used as target / for scoring, never as a feature.
    orders["meses_desde_pedido"] = (pd.Timestamp("2026-09-30") - orders.data_pedido).dt.days / 30.44
    orders["calote"] = np.where(
        orders.situacao_final.notna(), orders.situacao_final.eq("inadimplente").astype(float), np.nan
    )
    return orders.set_index("id_pedido", drop=False)


def features_at(df: pd.DataFrame, amount) -> pd.DataFrame:
    """Recomputes the amount-dependent features for a candidate approved amount."""
    out = df.copy()
    parcela = installment(amount, out.prazo_meses)
    out["parcela"] = parcela
    out["parcela_sobre_renda_efetiva"] = parcela / out.renda_efetiva
    out["parcela_sobre_folga"] = parcela / np.maximum(out.folga, SLACK_FLOOR)
    out["comprometimento_total"] = (parcela + out.parcelas_outras_instituicoes) / out.renda_efetiva
    return out


def model_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df[MODEL_FEATURES + CATEGORICAL_FEATURES]


def main():
    df = load_orders()
    hist = df[df.situacao_final.notna() & (df.meses_desde_pedido >= 12)]
    print(f"pedidos: {len(df)} | historicos maduros (>=12m): {len(hist)} | calote {hist.calote.mean():.3f}")
    print(f"novos sem bureau: {int(df[df.tipo_base.eq('novo')].bureau_ausente.sum())}")
    checks = {
        "saidas/entradas > 0.9": hist.saidas_sobre_entradas > 0.9,
        "dreno >= 3": hist.dreno >= 3,
        "cheque recente >= 2": hist.cheque_recente_meses >= 2,
        "entradas/renda < 0.6": hist.entradas_sobre_renda < 0.6,
        "consultas >= 8": hist.consultas_90_dias >= 8,
        "parcela/renda efetiva > 0.25": hist.parcela_sobre_renda_efetiva > 0.25,
        "parcela/folga > 0.45": hist.parcela_sobre_folga > 0.45,
        "conta <= 3 meses": hist.meses_conta <= 3,
    }
    for name, mask in checks.items():
        print(f"  {name:32s} n={int(mask.sum()):5d} calote={hist.loc[mask, 'calote'].mean():.3f}")


if __name__ == "__main__":
    main()
