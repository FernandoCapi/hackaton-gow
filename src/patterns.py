"""Patterns for the dashboard (Part 1), computed from the data with the same definitions the
policy uses (src/features.py). Aggregates only: no customer rows leave this module.

    python -m src.patterns      # prints every pattern sentence

Evidence:
- historico_maduro: approved loans with 12+ months (same base as the risk model). Every one of
  them was approved by the current policy, so these show where it approves and loses money.
- piloto: the randomized pilot (Oct/2025-Mar/2026), the only evidence about clients the current
  policy denies. Contracts are 6-12 months old, so default rates are still partial; they are
  compared with pilot clients the current policy would approve (same age).
"""
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from src.features import installment
from src.policy import STEP_CAPACITY, STEP_DOMAIN, STEP_RISK, STEP_STRAIN, current_policy, step_title
from src.schemas import Pattern, PatternGroup

MATURITY_MONTHS = 12
SMALL_SAMPLE = 30

Mask = Callable[[pd.DataFrame], pd.Series]


@dataclass
class Spec:
    id: str
    kind: str  # risk | opportunity | trap
    evidence: str  # historico_maduro | piloto
    group: str  # completes "Clientes com ..."
    mask: Mask
    groups: list[tuple[str, Mask]]
    policy_step: str | None = None
    new_mask: Mask | None = None
    baseline: Mask | None = None  # None = whole base
    baseline_label: str = "da média"
    sentence: Callable[["Spec", dict], str] | None = None
    note: str | None = None
    subject: str = "Clientes com"
    groups_evidence: str | None = None  # draw the bars from another base
    extra: dict = field(default_factory=dict)


def pct(value: float) -> str:
    text = f"{value * 100:.1f}" if value < 0.2 else f"{value * 100:.0f}"
    return text.replace(".", ",") + "%"


def num(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _frames(orders: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frame = orders.join(current_policy(orders))
    frame["pti_aprov"] = installment(frame.valor_aprovado.fillna(0), frame.prazo_meses) / frame.renda_efetiva
    frame["cortado"] = frame.valor_aprovado < frame.valor_solicitado - 0.005
    frame["conta_saudavel"] = (
        (frame.cheque_recente_meses == 0)
        & (frame.dreno < 3)
        & (frame.parcela_sobre_folga <= 0.25)
        & (frame.saidas_sobre_entradas <= 0.9)
    )
    return {
        "historico_maduro": frame[frame.situacao_final.notna() & (frame.meses_desde_pedido >= MATURITY_MONTHS)],
        "piloto": frame[frame.politica_aplicada.eq("piloto") & frame.decisao.eq("aprovado")],
        "novos": frame[frame.tipo_base.eq("novo")],
    }


def _denied_now(f: pd.DataFrame) -> pd.Series:
    return f.current_decision.eq("NEGADO")


def _trap_sentence(spec: Spec, s: dict) -> str:
    control_label, control_mask = spec.extra["control"]
    control = s["frame"][spec.mask(s["frame"]) & control_mask(s["frame"])]
    return (
        f"{(spec.subject + " ") if spec.subject else ""}{spec.group} parecem arriscados: inadimplência de {pct(s['rate'])}, contra "
        f"{pct(s['base_rate'])} {spec.baseline_label}. Mas {control_label} o calote cai para "
        f"{pct(control.calote.mean())} ({num(len(control))} clientes). {spec.extra['lesson']}"
    )


SPECS: list[Spec] = [
    # --- the current policy approves and loses money (mature loans) ---------------------
    Spec("outflow_over_inflow", "risk", "historico_maduro",
         "saídas acima de 90% do que entra na conta",
         lambda f: f.saidas_sobre_entradas > 0.9,
         [("até 50%", lambda f: f.saidas_sobre_entradas <= 0.5),
          ("50–90%", lambda f: f.saidas_sobre_entradas.between(0.5, 0.9, inclusive="right")),
          ("acima de 90%", lambda f: f.saidas_sobre_entradas > 0.9)],
         STEP_STRAIN, lambda f: f.saidas_sobre_entradas > 0.9),
    Spec("recent_overdraft", "risk", "historico_maduro",
         "cheque especial em 2 ou mais dos 3 meses antes do pedido",
         lambda f: f.cheque_recente_meses >= 2,
         [(f"{k} {'mês' if k == 1 else 'meses'}", lambda f, k=k: f.cheque_recente_meses == k) for k in range(4)],
         STEP_STRAIN, lambda f: f.cheque_recente_meses >= 2,
         note="Conta só os 3 meses antes do pedido: o cheque especial do mês mais antigo do extrato é "
              "artefato dos dados."),
    Spec("account_drain", "risk", "historico_maduro",
         "a conta esvaziada antes do pedido (uma saída 3 vezes maior que a típica)",
         lambda f: f.dreno >= 3,
         [("saída típica", lambda f: f.dreno < 2), ("2 a 3 vezes", lambda f: f.dreno.between(2, 3, inclusive="left")),
          ("3 vezes ou mais", lambda f: f.dreno >= 3)],
         STEP_STRAIN, lambda f: f.dreno >= 3),
    Spec("credit_seeking", "risk", "historico_maduro",
         "8 ou mais consultas ao CPF em 90 dias",
         lambda f: f.consultas_90_dias >= 8,
         [("0 a 3", lambda f: f.consultas_90_dias <= 3), ("4 a 7", lambda f: f.consultas_90_dias.between(4, 7)),
          ("8 ou mais", lambda f: f.consultas_90_dias >= 8)],
         STEP_STRAIN, lambda f: f.consultas_90_dias >= 8),
    Spec("inflated_income", "risk", "historico_maduro",
         "entradas na conta abaixo de 60% da renda declarada",
         lambda f: f.entradas_sobre_renda < 0.6,
         [("abaixo de 60%", lambda f: f.entradas_sobre_renda < 0.6),
          ("60–80%", lambda f: f.entradas_sobre_renda.between(0.6, 0.8, inclusive="left")),
          ("80% ou mais", lambda f: f.entradas_sobre_renda >= 0.8)],
         STEP_STRAIN, lambda f: f.entradas_sobre_renda < 0.6,
         note="Usa o total de entradas, não o salário: autônomos e empresários quase não recebem "
              "\"salário\" na conta."),
    Spec("installment_over_slack", "risk", "historico_maduro",
         "parcela acima de 45% da sobra do mês (entradas menos saídas)",
         lambda f: f.parcela_sobre_folga > 0.45,
         [("até 25%", lambda f: f.parcela_sobre_folga <= 0.25),
          ("25–45%", lambda f: f.parcela_sobre_folga.between(0.25, 0.45, inclusive="right")),
          ("acima de 45%", lambda f: f.parcela_sobre_folga > 0.45)],
         STEP_RISK, lambda f: f.parcela_sobre_folga > 0.45,
         note="Medido no valor pedido. É o sinal mais forte do modelo de risco."),
    Spec("amount_cut_by_30pct_rule", "risk", "historico_maduro",
         "pedido com parcela acima de 30% da renda (no histórico, aprovado com o valor cortado)",
         lambda f: f.cortado,
         [("valor cortado", lambda f: f.cortado), ("valor pedido", lambda f: ~f.cortado)],
         STEP_CAPACITY,
         # new orders that pass the rest of the current rule but ask for more than 30% of income
         lambda f: f.current_eligible & (f.pedido_acima_30 == 1),
         sentence=lambda spec, s: (
             f"No histórico, pedidos com parcela acima de 30% da renda foram aprovados com o valor cortado e "
             f"deram {pct(s['rate'])} de calote, contra {pct(s['base_rate'])} da média. "
             f"Afeta {num(s['n'])} clientes."
         ),
         note="A regra da Fortuna hoje nega esses pedidos, e a nossa política também: cortar não resolveu, "
              "porque deixa a parcela em exatos 30% da renda, e pedir acima da capacidade já é sinal de aperto."),
    Spec("total_debt_burden", "risk", "historico_maduro",
         "nossa parcela somada às dívidas em outras instituições acima de 44% da renda",
         lambda f: f.comprometimento_total > 0.44,
         [("até 30%", lambda f: f.comprometimento_total <= 0.30),
          ("30–44%", lambda f: f.comprometimento_total.between(0.30, 0.44, inclusive="right")),
          ("acima de 44%", lambda f: f.comprometimento_total > 0.44)],
         STEP_RISK, lambda f: f.comprometimento_total > 0.44),
    Spec("new_account", "risk", "historico_maduro",
         "conta aberta há até 3 meses",
         lambda f: f.meses_conta <= 3,
         [("até 3 meses", lambda f: f.meses_conta <= 3), ("4 a 6 meses", lambda f: f.meses_conta.between(3, 6, inclusive="right")),
          ("mais de 6 meses", lambda f: f.meses_conta > 6)],
         STEP_RISK, lambda f: f.meses_conta <= 3),
    Spec("active_restriction", "risk", "piloto",
         "restrição ativa no bureau",
         lambda f: f.restricoes_ativas == 1,
         [("sem restrição", lambda f: f.restricoes_ativas == 0), ("1 restrição", lambda f: f.restricoes_ativas == 1)],
         STEP_DOMAIN, lambda f: f.restricoes_ativas >= 1,
         baseline=lambda f: f.restricoes_ativas == 0, baseline_label="de quem não tem restrição",
         note="Aqui a regra atual acerta: manter a negativa."),
    # --- the current policy denies clients who would pay (pilot) ------------------------
    Spec("denied_with_healthy_account", "opportunity", "piloto",
         "a política atual negaria, mas com conta saudável (sem cheque especial recente, sem conta "
         "esvaziada, gastos até 90% das entradas e parcela até 25% da sobra)",
         lambda f: _denied_now(f) & f.conta_saudavel,
         [("atual negaria, conta saudável", lambda f: _denied_now(f) & f.conta_saudavel),
          ("atual negaria, conta com aperto", lambda f: _denied_now(f) & ~f.conta_saudavel),
          ("atual aprovaria", lambda f: ~_denied_now(f))],
         STEP_RISK, lambda f: _denied_now(f) & f.conta_saudavel,
         baseline=lambda f: ~_denied_now(f), baseline_label="de quem a política atual aprovaria",
         subject="Clientes que"),
    Spec("score_does_not_predict", "opportunity", "piloto",
         "score do bureau até 600, sem restrição e renda acima de R$ 2.000 (negados hoje só pelo score)",
         lambda f: (f.score <= 600) & (f.restricoes_ativas == 0) & (f.renda_declarada > 2000),
         [(f"score {low + 1}–{high} (maduros)", lambda f, low=low, high=high: f.score.between(low + 1, high))
          for low, high in [(600, 650), (650, 700), (700, 750), (750, 800), (800, 850), (850, 1000)]],
         STEP_DOMAIN, lambda f: (f.score <= 600) & (f.restricoes_ativas == 0) & (f.renda_declarada > 2000),
         baseline=lambda f: (f.score > 600) & (f.restricoes_ativas == 0) & (f.renda_declarada > 2000),
         baseline_label="dos que têm score acima de 600",
         groups_evidence="historico_maduro",
         note="O gráfico mostra os contratos maduros: todas as faixas de score ficam entre 12% e 16% de "
              "calote, o score não separa bom de mau pagador. No piloto, os negados só pelo score ficam "
              "abaixo do ponto de equilíbrio (~17%): negar por score descarta clientes que dão lucro."),
    Spec("income_1500_2000", "opportunity", "piloto",
         "renda declarada entre R$ 1.500 e R$ 2.000",
         lambda f: (f.renda_declarada > 1500) & (f.renda_declarada <= 2000),
         [("R$ 1.500–2.000", lambda f: (f.renda_declarada > 1500) & (f.renda_declarada <= 2000)),
          ("acima de R$ 2.000", lambda f: f.renda_declarada > 2000)],
         STEP_DOMAIN, lambda f: (f.renda_declarada > 1500) & (f.renda_declarada <= 2000),
         baseline=lambda f: f.renda_declarada > 2000, baseline_label="de quem declara mais de R$ 2.000",
         note="Um pouco acima de quem ganha mais, mas abaixo do ponto de equilíbrio (~17%): o corte em "
              "R$ 2.000 nega clientes que dão lucro. A política proposta decide pelo risco, não pela renda."),
    Spec("long_term", "opportunity", "historico_maduro",
         "prazo de 36 meses",
         lambda f: f.prazo_meses == 36,
         [(f"{k} meses", lambda f, k=k: f.prazo_meses == k) for k in (6, 12, 18, 24, 36)],
         STEP_RISK, lambda f: f.prazo_meses == 36,
         note="Não é só a parcela menor: com a parcela até 20% da renda, 36 meses ainda têm menos calote "
              "que prazos de até 12 meses. O modelo de risco usa o prazo."),
    # --- looks dangerous, but is not --------------------------------------------------------
    Spec("large_amount", "trap", "historico_maduro",
         "Pedidos acima de R$ 20 mil",
         lambda f: f.valor_aprovado > 20000,
         [("acima de R$ 20 mil", lambda f: f.valor_aprovado > 20000),
          ("acima de R$ 20 mil, parcela até 20%", lambda f: (f.valor_aprovado > 20000) & (f.pti_aprov <= 0.20)),
          ("até R$ 20 mil", lambda f: f.valor_aprovado <= 20000)],
         STEP_CAPACITY, None, sentence=_trap_sentence, subject="",
         extra={"control": ("com parcela de até 20% da renda", lambda f: f.pti_aprov <= 0.20),
                "lesson": "O que pesa é a parcela, não o valor."}),
]


def _current_view(frame: pd.DataFrame) -> str:
    share = frame.current_decision.eq("APROVADO").mean()
    return "approves" if share >= 0.95 else "denies" if share <= 0.05 else "mixed"


def _build(spec: Spec, frames: dict[str, pd.DataFrame]) -> Pattern | None:
    f = frames[spec.evidence]
    group = f[spec.mask(f).fillna(False)]
    if group.empty:
        return None
    base = f if spec.baseline is None else f[spec.baseline(f).fillna(False)]
    stats = {"frame": f, "rate": float(group.calote.mean()), "base_rate": float(base.calote.mean()), "n": len(group)}
    if spec.sentence:
        sentence = spec.sentence(spec, stats)
    else:
        sentence = (
            f"{spec.subject} {spec.group} têm inadimplência de {pct(stats['rate'])}, contra "
            f"{pct(stats['base_rate'])} {spec.baseline_label}. Afeta {num(stats['n'])} clientes."
        )
    caveats = []
    if spec.evidence == "piloto":
        caveats.append("Piloto sorteado com contratos de 6 a 12 meses: o calote ainda é parcial; a "
                       "comparação é com clientes do piloto da mesma época.")
    if stats["n"] < SMALL_SAMPLE:
        caveats.append(f"Amostra pequena ({stats['n']} contratos): usar como sinal, não como prova.")
    if spec.note:
        caveats.append(spec.note)
    new = frames["novos"]
    bars = frames[spec.groups_evidence or spec.evidence]
    return Pattern(
        id=spec.id,
        sentence=sentence,
        group_description=spec.group[0].upper() + spec.group[1:],
        group_default_rate=round(stats["rate"], 4),
        overall_default_rate=round(stats["base_rate"], 4),
        customers_affected=stats["n"],
        direction="worse" if stats["rate"] > stats["base_rate"] else "better",
        current_policy_view=_current_view(group),
        groups=[
            PatternGroup(label=label, default_rate=round(float(bars.calote[m].mean()), 4), customers=int(m.sum()))
            for label, mask in spec.groups
            if (m := mask(bars).fillna(False)).any()
        ],
        kind=spec.kind,
        new_orders_affected=int(spec.new_mask(new).fillna(False).sum()) if spec.new_mask else None,
        policy_step=step_title(spec.policy_step) if spec.policy_step else None,
        evidence=spec.evidence,
        caveat=" ".join(caveats) or None,
    )


def compute_patterns(orders: pd.DataFrame) -> list[Pattern]:
    frames = _frames(orders)
    return [pattern for spec in SPECS if (pattern := _build(spec, frames)) is not None]


def main():
    from src.features import load_orders

    for pattern in compute_patterns(load_orders()):
        new = f" | novos: {pattern.new_orders_affected}" if pattern.new_orders_affected is not None else ""
        print(f"[{pattern.kind}/{pattern.evidence}] {pattern.sentence}{new}")
        if pattern.caveat:
            print(f"    ressalva: {pattern.caveat}")


if __name__ == "__main__":
    main()
