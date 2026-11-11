"""Current and proposed credit policies, vectorized over many orders.

The proposed policy is applied in five steps, in this order:
  1. Outside what the pilot tested  -> deny (no evidence to approve safely)
  2. Signs of strain in the account -> deny
  3. Capacity: installment <= max share of the effective income (and amount rule)
  4. Risk estimated by the model    -> deny above the cutoff
  5. Product limits (<= requested, <= R$ 30k, >= minimum)

Risk is precomputed once per order for a grid of candidate amounts (RiskGrid); changing a
parameter only filters and sums arrays, so the dashboard sliders answer in milliseconds.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features import MAX_AMOUNT, MIN_AMOUNT, features_at, installment, max_amount_for_installment
from src.schemas import PolicyParams

FRACTIONS = np.array([1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3])
ON_TIME, LATE, DEFAULT = 0.15, 0.05, -0.60  # official scoring, share of the approved amount

STEP_DOMAIN = "Fora do que o piloto testou"
STEP_STRAIN = "Sinais de aperto na conta"
STEP_CAPACITY = "Capacidade de pagamento"
STEP_RISK = "Risco estimado pela IA"
STEP_LIMITS = "Limites do produto"
STEPS = [STEP_DOMAIN, STEP_STRAIN, STEP_CAPACITY, STEP_RISK, STEP_LIMITS]  # internal ids (denied_at)


def step_title(step: str, params: PolicyParams | None = None) -> str:
    """Title the analyst sees for each step: one source for the policy page, the order trace,
    the lab and the patterns. Step 3 depends on the amount rule."""
    full_or_deny = params is None or params.amount_rule == "full_or_deny"
    return {
        STEP_DOMAIN: "Quem pode ser aprovado",
        STEP_STRAIN: "Nega com sinais de aperto na conta",
        STEP_CAPACITY: "Nega quando a parcela não cabe" if full_or_deny else "Ajusta o valor à capacidade",
        STEP_RISK: "Nega pelo risco estimado pela IA",
        STEP_LIMITS: "Valor aprovado",
    }[step]


def pct(value: float) -> str:
    """Percent in Brazilian format: one decimal below 10% ("6,5%"), whole above ("25%")."""
    text = f"{value * 100:.1f}" if abs(value) < 0.10 else f"{value * 100:.0f}"
    return text.replace(".", ",") + "%"
NO_BUREAU = "bureau indisponível"


def expected_rate(p_default, late_rate):
    """Expected result per real lent: +15% on time, +5% late, -60% default."""
    p_default = np.asarray(p_default, dtype=float)
    p_late = np.minimum(late_rate, 1 - p_default)
    return ON_TIME * (1 - p_default - p_late) + LATE * p_late + DEFAULT * p_default


# --- current policy -------------------------------------------------------------------


def current_policy(df: pd.DataFrame, reduce_amount: bool = False) -> pd.DataFrame:
    """Fortuna's rule: score > 600, income > 2,000, no active restriction and installment of the
    requested amount up to 30% of the declared income.

    Default (reduce_amount=False): yes or no, as Fortuna confirmed for today's rule — approves
    the requested amount when it fits, denies otherwise. This is the baseline of every comparison.
    reduce_amount=True reproduces the historical data, where the amount was cut down to the
    largest that fits 30%; it is used only to prove the rule is reproduced 100%.
    """
    eligible = (df.score > 600) & (df.renda_declarada > 2000) & (df.restricoes_ativas == 0)
    fits = max_amount_for_installment(0.30 * df.renda_declarada, df.prazo_meses)
    if reduce_amount:
        amount = np.floor(np.minimum(df.valor_solicitado, fits) * 100) / 100
    else:
        amount = np.where(installment(df.valor_solicitado, df.prazo_meses) <= 0.30 * df.renda_declarada,
                          df.valor_solicitado, 0.0)
    approve = eligible & (amount >= MIN_AMOUNT)
    return pd.DataFrame(
        {
            "current_decision": np.where(approve, "APROVADO", "NEGADO"),
            "current_amount": np.where(approve, amount, 0.0),
            "current_eligible": eligible.to_numpy(),
        },
        index=df.index,
    )


# --- risk grid ------------------------------------------------------------------------


@dataclass
class RiskGrid:
    """P(default) of each order at each candidate amount (rows = orders, cols = FRACTIONS)."""

    orders: pd.DataFrame
    amounts: np.ndarray
    risk: np.ndarray
    commitment: np.ndarray
    current_risk: np.ndarray  # P(default) at the amount the current policy would approve

    @classmethod
    def build(cls, orders: pd.DataFrame, predict) -> "RiskGrid":
        """predict(frame) -> P(default) for every row of a feature frame."""
        base = orders.valor_base.to_numpy()
        amounts = np.round(base[:, None] * FRACTIONS[None, :], 2)
        stacked = pd.concat(
            [features_at(orders, amounts[:, j]) for j in range(len(FRACTIONS))], ignore_index=True
        )
        risk = np.asarray(predict(stacked)).reshape(len(FRACTIONS), len(orders)).T
        commitment = installment(amounts, orders.prazo_meses.to_numpy()[:, None]) / orders.renda_efetiva.to_numpy()[:, None]
        current = current_policy(orders)
        current_amount = np.where(current.current_amount > 0, current.current_amount, base)
        current_risk = np.asarray(predict(features_at(orders, current_amount)))
        return cls(orders, amounts, risk, commitment, current_risk)

    def subset(self, mask) -> "RiskGrid":
        mask = np.asarray(mask)
        return RiskGrid(
            self.orders[mask], self.amounts[mask], self.risk[mask], self.commitment[mask], self.current_risk[mask]
        )


# --- proposed policy ------------------------------------------------------------------


def _step_masks(o: pd.DataFrame, p: PolicyParams, disabled: frozenset = frozenset()) -> dict:
    """Boolean 'denied at this step' per order for the filter steps."""
    domain = (
        o.bureau_ausente
        | (o.score <= p.min_score)
        | (o.renda_declarada <= p.min_income)
        | (o.restricoes_ativas > p.max_restrictions)
    )
    strain = (
        (o.saidas_sobre_entradas > p.max_outflow_ratio)
        | (o.cheque_recente_meses > p.max_recent_overdraft_months)
        | (o.dreno >= p.max_drain)
        | (o.entradas_sobre_renda < p.min_inflow_ratio)
        | (o.consultas_90_dias > p.max_inquiries_90d)
    )
    masks = {STEP_DOMAIN: domain.to_numpy(), STEP_STRAIN: strain.fillna(False).to_numpy()}
    for step in disabled & masks.keys():
        masks[step] = np.zeros(len(o), dtype=bool)
    masks[STEP_DOMAIN] = masks[STEP_DOMAIN] | o.bureau_ausente.to_numpy()  # never decide blind
    return masks


def proposed_policy(grid: RiskGrid, p: PolicyParams, disabled: frozenset = frozenset()) -> pd.DataFrame:
    """Decision per order. `disabled` switches steps off to measure what each one is worth."""
    o = grid.orders
    n = len(o)
    masks = _step_masks(o, p, disabled)
    current = current_policy(o)
    cutoff = np.where(current.current_eligible, p.risk_cutoff, p.risk_cutoff_expansion)

    columns = slice(0, 1) if p.amount_rule == "full_or_deny" else slice(None)
    amounts = grid.amounts[:, columns]
    risk = grid.risk[:, columns]
    commitment = grid.commitment[:, columns]
    rate = expected_rate(risk, p.late_rate)

    fits_limits = (amounts >= p.min_amount) & (amounts <= np.minimum(o.valor_solicitado.to_numpy(), MAX_AMOUNT)[:, None])
    fits_capacity = commitment <= p.max_commitment
    if STEP_CAPACITY in disabled:
        fits_capacity = np.ones_like(fits_capacity)
    passes_risk = (risk <= cutoff[:, None]) & (rate >= p.safety_margin) & (rate > 0)
    if STEP_RISK in disabled:
        passes_risk = rate > 0
    valid = fits_limits & fits_capacity & passes_risk

    value = np.where(valid, amounts * rate, -np.inf)
    best = value.argmax(axis=1)
    rows = np.arange(n)
    any_valid = valid.any(axis=1)

    blocked = masks[STEP_DOMAIN] | masks[STEP_STRAIN]
    approve = any_valid & ~blocked
    chosen_amount = np.where(approve, amounts[rows, best], 0.0)
    chosen_risk = np.where(approve, risk[rows, best], risk[:, 0])

    failed = np.full(n, "", dtype=object)
    failed[~approve & ~(fits_limits & fits_capacity).any(axis=1)] = STEP_CAPACITY
    failed[~approve & (fits_limits & fits_capacity).any(axis=1)] = STEP_RISK
    failed[~approve & ~fits_limits.any(axis=1)] = STEP_LIMITS
    failed[masks[STEP_STRAIN]] = STEP_STRAIN
    failed[masks[STEP_DOMAIN]] = STEP_DOMAIN

    result = pd.DataFrame(
        {
            "decision": np.where(approve, "APROVADO", "NEGADO"),
            "approved_amount": np.round(chosen_amount, 2),
            "default_risk": chosen_risk,
            "expected_profit": np.where(approve, chosen_amount * expected_rate(chosen_risk, p.late_rate), 0.0),
            "reduced": approve & (chosen_amount < o.valor_base.to_numpy() - 0.005),
            "denied_at": failed,
            "risk_cutoff_used": cutoff,
        },
        index=o.index,
    )
    result = result.join(current)
    result["current_risk"] = grid.current_risk
    result["current_expected_profit"] = result.current_amount * expected_rate(grid.current_risk, p.late_rate)
    result["changed_vs_current"] = (result.decision != result.current_decision) | (
        (result.approved_amount - result.current_amount).abs() > 0.005
    )
    return result


def decision_steps(row: pd.Series, o: pd.Series, p: PolicyParams) -> list[dict]:
    """Business-language trace of how one order was decided, step by step."""
    brl = lambda value: f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    steps = []

    if row.denied_at == STEP_DOMAIN:
        if o.bureau_ausente:
            detail = "Sem dados do bureau para este cliente (" + NO_BUREAU + ")"
        else:
            problems = []
            if o.score <= p.min_score:
                problems.append(f"score {o.score:.0f} (mínimo testado no piloto: {p.min_score + 1})")
            if o.renda_declarada <= p.min_income:
                problems.append(f"renda {brl(o.renda_declarada)} (mínimo testado: acima de {brl(p.min_income)})")
            if o.restricoes_ativas > p.max_restrictions:
                problems.append(f"{o.restricoes_ativas:.0f} restrições ativas (máximo: {p.max_restrictions})")
            detail = "; ".join(problems)
        return [{"order": 1, "title": step_title(STEP_DOMAIN, p), "result": "negou", "detail": detail}]
    steps.append({"order": 1, "title": step_title(STEP_DOMAIN, p), "result": "passou",
                  "detail": f"Score {o.score:.0f}, renda {brl(o.renda_declarada)}, {o.restricoes_ativas:.0f} restrições"})

    if row.denied_at == STEP_STRAIN:
        problems = []
        if o.saidas_sobre_entradas > p.max_outflow_ratio:
            problems.append(f"saídas consomem {pct(o.saidas_sobre_entradas)} das entradas")
        if o.cheque_recente_meses > p.max_recent_overdraft_months:
            problems.append(f"cheque especial em {o.cheque_recente_meses} dos 3 meses antes do pedido")
        if o.dreno >= p.max_drain:
            problems.append(f"saída recente {o.dreno:.1f}x maior que a típica (conta esvaziada)")
        if o.entradas_sobre_renda < p.min_inflow_ratio:
            problems.append(f"entradas cobrem só {pct(o.entradas_sobre_renda)} da renda declarada")
        if o.consultas_90_dias > p.max_inquiries_90d:
            problems.append(f"{o.consultas_90_dias:.0f} consultas ao CPF em 90 dias")
        steps.append({"order": 2, "title": step_title(STEP_STRAIN, p), "result": "negou", "detail": "; ".join(problems)})
        return steps
    steps.append({"order": 2, "title": step_title(STEP_STRAIN, p), "result": "passou",
                  "detail": f"Saídas {pct(o.saidas_sobre_entradas)} das entradas, sem cheque especial recente nem saque atípico"})

    if row.denied_at == STEP_CAPACITY:
        steps.append({"order": 3, "title": step_title(STEP_CAPACITY, p), "result": "negou",
                      "detail": f"Parcela do valor pedido consome {pct(o.parcela_sobre_renda_efetiva)} da renda efetiva "
                                f"(limite {pct(p.max_commitment)})"})
        return steps
    if row.denied_at == STEP_LIMITS:
        steps.append({"order": 5, "title": step_title(STEP_LIMITS, p), "result": "negou", "detail": f"Valor abaixo de {brl(p.min_amount)}"})
        return steps
    amount = row.approved_amount if row.decision == "APROVADO" else o.valor_base
    share = installment(amount, o.prazo_meses) / o.renda_efetiva
    steps.append({"order": 3, "title": step_title(STEP_CAPACITY, p), "result": "ajustou" if row.reduced else "passou",
                  "detail": (f"Valor reduzido para {brl(amount)}: " if row.reduced else "")
                            + f"parcela de {pct(share)} da renda efetiva (limite {pct(p.max_commitment)})"})

    if row.denied_at == STEP_RISK:
        steps.append({"order": 4, "title": step_title(STEP_RISK, p), "result": "negou",
                      "detail": f"Chance de calote de {pct(row.default_risk)}, acima do limite de {pct(row.risk_cutoff_used)}"})
        return steps
    steps.append({"order": 4, "title": step_title(STEP_RISK, p), "result": "passou",
                  "detail": f"Chance de calote de {pct(row.default_risk)}, dentro do limite de {pct(row.risk_cutoff_used)}"})
    steps.append({"order": 5, "title": step_title(STEP_LIMITS, p), "result": "passou",
                  "detail": f"{brl(row.approved_amount)} entre {brl(p.min_amount)} e o menor entre o pedido e R$ 30.000"})
    return steps


def reasons(o: pd.Series) -> list[str]:
    """Facts about the order that the analyst can check, strongest signals first."""
    facts = []
    if o.bureau_ausente:
        return ["Sem dados do bureau: decisão conservadora"]
    if o.saidas_sobre_entradas > 0.9:
        facts.append(f"Saídas consomem {pct(o.saidas_sobre_entradas)} do que entra na conta")
    if o.cheque_recente_meses >= 1:
        facts.append(f"Cheque especial em {o.cheque_recente_meses} dos 3 meses antes do pedido")
    if o.dreno >= 3:
        facts.append(f"Saída recente {o.dreno:.1f}x maior que a típica")
    if o.consultas_90_dias >= 5:
        facts.append(f"{o.consultas_90_dias:.0f} consultas ao CPF nos últimos 90 dias")
    if o.entradas_sobre_renda < 0.8:
        facts.append(f"Entradas na conta cobrem {pct(o.entradas_sobre_renda)} da renda declarada")
    facts.append(f"Parcela do pedido consome {pct(o.parcela_sobre_renda_efetiva)} da renda efetiva "
                 f"e {pct(min(o.parcela_sobre_folga, 9.99))} da sobra do mês")
    if o.score <= 600:
        facts.append(f"Score {o.score:.0f}: a política atual negaria, mas o score não prevê calote nos dados")
    if o.meses_conta <= 3:
        facts.append(f"Conta aberta há {o.meses_conta:.0f} meses")
    return facts[:4]
