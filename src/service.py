"""Facade between the API routes and the decision engine.

Every route calls one function here. When the trained model (artifacts/risk_model.joblib)
and the database are available, answers come from the engine ("live"); otherwise from
contracts/fixtures/ (invented, schema-valid examples), so the front end can work without
Python data. ENGINE_MODE=fixtures forces the examples.
"""
import json
import os
from datetime import date, datetime
from functools import lru_cache

import pandas as pd

import config
from src.policy import STEP_CAPACITY, STEP_DOMAIN, STEP_LIMITS, STEP_RISK, STEP_STRAIN, step_title
from src.schemas import (
    AccountInfo,
    ApproveRequest,
    BureauInfo,
    Counteroffer,
    ExplainLine,
    DecisionStep,
    Health,
    ModelQuality,
    OrderDetail,
    OrderPage,
    OrderSort,
    OrderSummary,
    ParamOption,
    ParamSpec,
    Pattern,
    Policy,
    PolicyParams,
    PolicyStep,
    ResultBlock,
    SectionMode,
    SimulationResult,
    Summary,
)

FIXTURES = config.ROOT / "contracts" / "fixtures"
APPROVED_POLICY = config.ARTIFACTS / "approved_policy.json"
DATA_CUTOFF = date(2026, 9, 30)
SECTION_NAMES = ["summary", "patterns", "policy", "simulate", "orders", "decisions_csv"]


class OrderNotFound(LookupError):
    pass


@lru_cache
def _fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _brl(value: float) -> str:
    return f"R$ {value:,.0f}".replace(",", ".")


def _pct(value: float) -> str:
    number = f"{value * 100:.1f}".rstrip("0").rstrip(".")
    return number.replace(".", ",") + "%"


# --- engine ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def engine():
    """The decision engine, or None when it cannot run here (no model or no database)."""
    if os.getenv("ENGINE_MODE") == "fixtures":
        return None
    from src import risk_model

    if not risk_model.MODEL_FILE.exists():
        return None
    try:
        from src.simulate import Engine

        return Engine()
    except Exception as error:  # noqa: BLE001 - fall back to examples, but say why
        print(f"Motor indisponível, usando exemplos: {error}")
        return None


def is_live() -> bool:
    return engine() is not None


@lru_cache(maxsize=8)
def _decisions(params_json: str) -> pd.DataFrame:
    return engine().decide_new(PolicyParams.model_validate_json(params_json))


def _current_decisions() -> pd.DataFrame:
    return _decisions(current_policy().params.model_dump_json())


COUNTEROFFER_STEPS = (STEP_CAPACITY, STEP_RISK)  # internal step ids, not display titles


def _counteroffers() -> pd.DataFrame:
    """EXTRA, outside the official file: for orders denied only for capacity or risk, the
    smaller amount the same policy would approve (same filters and cutoffs, amounts from
    100% down to 30% of the request). Orders denied by the evidence or strain filters get
    no offer: a smaller amount does not fix those."""
    params = current_policy().params
    decisions = _current_decisions()
    reduced = _decisions(params.model_copy(update={"amount_rule": "maximize_expected_profit"}).model_dump_json())
    eligible = decisions.denied_at.isin(COUNTEROFFER_STEPS) & reduced.decision.eq("APROVADO")
    return reduced[eligible]


# --- health ---------------------------------------------------------------------------


def health() -> Health:
    mode: SectionMode = "live" if is_live() else "fixtures"
    sections: dict[str, SectionMode] = {name: mode for name in SECTION_NAMES}
    model_version = None
    if mode == "live":
        model_version = f"lightgbm-calote-{engine().metrics['trained_until']}"
    overall: SectionMode = "live" if all(m == "live" for m in sections.values()) else "fixtures"
    return Health(status="ok", mode=overall, sections=sections, data_cutoff=DATA_CUTOFF, model_version=model_version)


# --- summary and patterns -------------------------------------------------------------


def summary() -> Summary:
    if not is_live():
        return Summary.model_validate(_fixture("summary"))
    e = engine()
    decisions = _current_decisions()
    approved = decisions.decision.eq("APROVADO")
    current_approved = decisions.current_decision.eq("APROVADO")
    validation = e.metrics["temporal_validation"]
    proposed_result = float(decisions.expected_profit.sum())
    current_result = float(decisions.current_expected_profit.sum())
    return Summary(
        new_orders_total=len(decisions),
        historical_mature_total=len(e.hist_grid.orders),
        base_default_rate=e.metrics["default_rate"],
        current_policy=ResultBlock(
            approved=int(current_approved.sum()),
            denied=int((~current_approved).sum()),
            approved_amount=round(float(decisions.current_amount.sum()), 2),
            expected_result=round(current_result, 2),
        ),
        proposed_policy=ResultBlock(
            approved=int(approved.sum()),
            denied=int((~approved).sum()),
            approved_amount=round(float(decisions.approved_amount.sum()), 2),
            expected_result=round(proposed_result, 2),
        ),
        gain=round(proposed_result - current_result, 2),
        model=ModelQuality(
            auc=validation["auc"],
            auc_current_rule=validation["auc_score_bureau"],
            trained_until=e.metrics["trained_until"],
            validated_on=f"pedidos de {validation['test_period']} (nunca vistos no treino)",
        ),
        counteroffers=int(len(_counteroffers())),
    )


@lru_cache(maxsize=1)
def _live_patterns() -> tuple[Pattern, ...]:
    from src.patterns import compute_patterns

    return tuple(compute_patterns(engine().orders))


def patterns() -> list[Pattern]:
    """Patterns computed from the data (src/patterns.py), same definitions as the policy."""
    if is_live():
        return list(_live_patterns())
    return [Pattern.model_validate(item) for item in _fixture("patterns")]


# --- policy ---------------------------------------------------------------------------

PARAM_SPECS: list[dict] = [
    dict(name="min_score", label="Score mínimo", kind="number", min=0, max=700, step=10, unit="count",
         description="Nega com score até este valor. O piloto só testou acima de 450; o score não prevê calote."),
    dict(name="min_income", label="Renda mínima", kind="number", min=0, max=5000, step=100, unit="brl",
         description="Nega com renda declarada até este valor. O piloto só testou acima de R$ 1.500."),
    dict(name="max_restrictions", label="Restrições aceitas", kind="number", min=0, max=2, step=1, unit="count",
         description="Com 1 restrição o calote foi de 19–23% no piloto, acima do ponto de equilíbrio."),
    dict(name="max_outflow_ratio", label="Saídas máximas sobre entradas", kind="number", min=0.5, max=1.2,
         step=0.05, unit="percent", description="Quem gasta mais de 90% do que entra teve 91% de calote."),
    dict(name="max_recent_overdraft_months", label="Meses de cheque especial aceitos (últimos 3)", kind="number",
         min=0, max=3, step=1, unit="count",
         description="Cheque especial em 2 ou mais dos 3 meses antes do pedido: 85–91% de calote."),
    dict(name="max_drain", label="Saque atípico máximo (vezes a saída típica)", kind="number", min=1.5,
         max=10, step=0.5, unit="count", description="Conta esvaziada antes do pedido: 82–87% de calote."),
    dict(name="min_inflow_ratio", label="Entradas mínimas sobre a renda declarada", kind="number", min=0,
         max=1, step=0.05, unit="percent", description="Entradas abaixo de 60% da renda declarada: 71% de calote."),
    dict(name="max_inquiries_90d", label="Consultas ao CPF aceitas (90 dias)", kind="number", min=0, max=15,
         step=1, unit="count", description="8 ou mais consultas em 90 dias: 83% de calote."),
    dict(name="max_commitment", label="Parcela máxima sobre a renda efetiva", kind="number", min=0.10,
         max=0.35, step=0.01, unit="percent",
         description="Renda efetiva = menor entre a declarada e a média de entradas. Acima de 25% o calote salta."),
    dict(name="amount_rule", label="Como definir o valor", kind="select",
         options=[{"value": "full_or_deny", "label": "Valor pedido ou nega"},
                  {"value": "maximize_expected_profit", "label": "Reduzir até caber (maior resultado esperado)"}],
         description="Reduzir valor não tem dados históricos que provem que reduz o calote."),
    dict(name="risk_cutoff", label="Risco máximo de calote", kind="number", min=0.05, max=0.30, step=0.01,
         unit="percent", description="Para quem a política atual aprovaria. Ponto de equilíbrio: ~17%."),
    dict(name="risk_cutoff_expansion", label="Risco máximo para quem a atual nega", kind="number", min=0.03,
         max=0.30, step=0.01, unit="percent", description="Mais rígido: a evidência vem só do piloto."),
    dict(name="safety_margin", label="Resultado mínimo por real emprestado", kind="number", min=0, max=0.10,
         step=0.005, unit="percent", description="Margem de segurança sobre o ponto de equilíbrio."),
    dict(name="late_rate", label="Chance de atraso considerada", kind="number", min=0, max=0.5, step=0.01,
         unit="percent", description="Atraso não é previsível nos dados; usamos a média do histórico (~20%)."),
    dict(name="min_amount", label="Valor mínimo", kind="number", min=500, max=5000, step=100, unit="brl",
         description="Abaixo deste valor o pedido é negado."),
]


def policy_steps(p: PolicyParams) -> list[PolicyStep]:
    """Business-language steps of the proposed policy, in the order they are applied."""
    full_or_deny = p.amount_rule == "full_or_deny"
    capacity_text = (
        "Se a parcela do valor pedido não couber, nega: pedir acima da capacidade já é sinal de risco."
        if full_or_deny
        else "Se a parcela do valor pedido não couber, testa valores menores (até 30% do pedido) e fica com o de maior "
             "resultado esperado."
    )
    margin = f" Também nega se o resultado esperado ficar abaixo de {_pct(p.safety_margin)} do valor." if p.safety_margin else ""
    restrictions = (
        "sem restrição ativa" if p.max_restrictions == 0
        else f"no máximo {p.max_restrictions} {'restrição ativa' if p.max_restrictions == 1 else 'restrições ativas'}"
    )
    return [
        PolicyStep(order=1, kind="filter", outcome="approve", title=step_title(STEP_DOMAIN, p),
                   rule_text=f"Segue para aprovação quem tem consulta ao bureau, score acima de {p.min_score}, renda acima "
                             f"de {_brl(p.min_income)} e {restrictions}: o perfil que o "
                             f"piloto testou. O score não é usado como corte de risco."),
        PolicyStep(order=2, kind="filter", outcome="deny", title=step_title(STEP_STRAIN, p),
                   rule_text=f"Basta um destes para negar:\n"
                             f"• saídas acima de {_pct(p.max_outflow_ratio)} das entradas\n"
                             f"• cheque especial em mais de {p.max_recent_overdraft_months} dos 3 meses antes do pedido\n"
                             f"• conta esvaziada: saída recente {p.max_drain:g}x maior que a típica\n"
                             f"• entradas abaixo de {_pct(p.min_inflow_ratio)} da renda declarada\n"
                             f"• mais de {p.max_inquiries_90d} consultas ao CPF em 90 dias"),
        PolicyStep(order=3, kind="capacity", outcome="deny" if full_or_deny else "amount",
                   title=step_title(STEP_CAPACITY, p),
                   rule_text=f"A parcela pode consumir até {_pct(p.max_commitment)} da renda efetiva (a menor entre a "
                             f"renda declarada e a média de entradas na conta). {capacity_text}"),
        PolicyStep(order=4, kind="risk", outcome="deny", title=step_title(STEP_RISK, p),
                   rule_text=f"Um modelo treinado no histórico estima a chance de calote no valor a aprovar. Nega acima "
                             f"de {_pct(p.risk_cutoff)} para quem a política atual aprovaria e acima de "
                             f"{_pct(p.risk_cutoff_expansion)} para quem ela negaria.{margin}"),
        PolicyStep(order=5, kind="limit", outcome="amount", title=step_title(STEP_LIMITS, p),
                   rule_text=f"Quem passou por tudo recebe {'o valor pedido' if full_or_deny else 'o valor do passo 3'}, "
                             f"até R$ 30.000. Abaixo de "
                             f"{_brl(p.min_amount)}, nega."),
    ]


def _param_specs(p: PolicyParams) -> list[ParamSpec]:
    values = p.model_dump()
    specs = []
    for spec in PARAM_SPECS:
        value = values[spec["name"]]
        options = [ParamOption(**option) for option in spec.get("options", [])] or None
        specs.append(
            ParamSpec(
                **{key: spec[key] for key in ("name", "label", "description", "kind")},
                min=spec.get("min"), max=spec.get("max"), step=spec.get("step"), unit=spec.get("unit"),
                options=options, value=value if isinstance(value, str) else float(value),
            )
        )
    return specs


def _policy(version: int, params: PolicyParams, approved_at=None, approved_by=None, note=None) -> Policy:
    return Policy(version=version, approved_at=approved_at, approved_by=approved_by, note=note,
                  params=params, steps=policy_steps(params), param_specs=_param_specs(params))


def current_policy() -> Policy:
    """The policy in force: the last one approved by the analyst, else the AI proposal."""
    if APPROVED_POLICY.exists():
        saved = json.loads(APPROVED_POLICY.read_text(encoding="utf-8"))
        return _policy(saved["version"], PolicyParams.model_validate(saved["params"]), saved.get("approved_at"),
                       saved.get("approved_by"), saved.get("note"))  # steps rebuilt: their text may have changed
    return _policy(1, PolicyParams())


def approve_policy(request: ApproveRequest) -> Policy:
    approved = _policy(
        current_policy().version + 1, request.params,
        approved_at=datetime.now().astimezone(), approved_by=request.approved_by, note=request.note,
    )
    config.ARTIFACTS.mkdir(exist_ok=True)
    APPROVED_POLICY.write_text(approved.model_dump_json(indent=2), encoding="utf-8")
    return approved


# --- simulation -----------------------------------------------------------------------


def simulate(params: PolicyParams) -> SimulationResult:
    if is_live():
        return engine().simulate(params)
    return _fixture_simulation(params)


def _fixture_simulation(params: PolicyParams) -> SimulationResult:
    """Example mode: scales the example so the front can see sliders react (not real)."""
    base = SimulationResult.model_validate(_fixture("simulation"))
    looseness = params.risk_cutoff / 0.15
    quality = max(0.0, 1 - 4 * (params.risk_cutoff - 0.15) ** 2 - 2 * params.safety_margin)
    hist, new = base.historical, base.new_orders
    proposed_result = round(hist.proposed_result * quality, 2)
    approved_new = min(2000, round(new.approved * looseness**0.3))
    return base.model_copy(update={
        "params": params,
        "historical": hist.model_copy(update={
            "proposed_result": proposed_result,
            "gain": round(proposed_result - hist.current_result, 2),
            "approved_proposed": round(hist.approved_proposed * looseness**0.3),
        }),
        "new_orders": new.model_copy(update={
            "approved": approved_new,
            "denied": 2000 - approved_new,
            "total_approved_amount": round(new.total_approved_amount * approved_new / new.approved, 2),
        }),
        "by_risk_band": [b.model_copy(update={"proposed_result": round(b.proposed_result * quality, 2)})
                         for b in base.by_risk_band],
    })


# --- orders ---------------------------------------------------------------------------


def _summary_from(order_id: str, row: pd.Series, o: pd.Series) -> dict:
    return dict(
        order_id=order_id,
        customer_id=o.id_cliente,
        order_date=o.data_pedido.date(),
        requested_amount=float(o.valor_solicitado),
        term_months=int(o.prazo_meses),
        decision=row.decision,
        approved_amount=round(float(row.approved_amount), 2),
        default_risk=round(float(row.default_risk), 4),
        expected_profit=round(float(row.expected_profit), 2),
        current_decision=row.current_decision,
        current_approved_amount=round(float(row.current_amount), 2),
        changed_vs_current=bool(row.changed_vs_current),
    )


def _live_detail(order_id: str) -> OrderDetail:
    from src.features import installment
    from src.policy import decision_steps, reasons

    decisions = _current_decisions()
    if order_id not in decisions.index:
        raise OrderNotFound(order_id)
    row = decisions.loc[order_id]
    o = engine().new_grid.orders.loc[order_id]
    params = current_policy().params
    amount = row.approved_amount if row.decision == "APROVADO" else o.valor_base
    parcela = float(installment(amount, o.prazo_meses))
    bureau = BureauInfo(
        score=int(o.score), active_restrictions=int(o.restricoes_ativas),
        other_installments=float(o.parcelas_outras_instituicoes), inquiries_90d=int(o.consultas_90_dias),
        bureau_history_months=int(o.meses_historico_bureau),
    ) if not o.bureau_ausente else BureauInfo(score=0, active_restrictions=0, other_installments=0,
                                              inquiries_90d=0, bureau_history_months=0)
    return OrderDetail(
        **_summary_from(order_id, row, o),
        employment_type=str(o.tipo_vinculo),
        income_declared=float(o.renda_declarada),
        installment=round(parcela, 2),
        income_commitment=round((parcela + float(o.parcelas_outras_instituicoes or 0)) / float(o.renda_efetiva), 4),
        bureau=bureau,
        account=AccountInfo(
            months_of_history=int(o.mov_meses),
            avg_salary_inflow=round(float(o.salario_media), 2),
            avg_total_inflow=round(float(o.entradas_media), 2),
            avg_outflow=round(float(o.saidas_media), 2),
            min_balance=round(float(o.saldo_minimo), 2),
            overdraft_days_12m=int(o.dias_cheque_12m),
        ),
        reasons=reasons(o),
        steps=[DecisionStep(**step) for step in decision_steps(row, o, params)],
        effective_income=round(float(o.renda_efetiva), 2),
        explain=_explain(row, o, params),
        counteroffer=_counteroffer_for(order_id, o),
    )


def _brl2(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct1(value: float) -> str:
    return f"{value * 100:.1f}".replace(".", ",") + "%"


def _explain(row: pd.Series, o: pd.Series, p: PolicyParams) -> list[ExplainLine]:
    """Every number on the order page, as a calculation a layperson can follow."""
    from src.features import installment
    from src.policy import expected_rate

    requested = float(o.valor_solicitado)
    term = int(o.prazo_meses)
    parcela = float(installment(requested, term))
    declared = float(o.renda_declarada)
    inflow = float(o.entradas_media)
    effective = float(o.renda_efetiva)
    others = float(o.parcelas_outras_instituicoes or 0)
    risk = float(row.default_risk)
    cutoff = float(row.risk_cutoff_used)
    old_share = parcela / declared
    new_share = parcela / effective
    total_share = (parcela + others) / effective
    # Same criterion the engine uses to pick the cutoff (src/policy.py::proposed_policy): the stricter
    # limit applies to whoever fails score, income or restrictions of the old rule. An order the old
    # rule denies only because the installment passes 30% of income keeps the regular limit.
    expansion = not bool(row.current_eligible)
    lines = [
        ExplainLine(rule="dados", label="Parcela do valor pedido",
                    formula=f"{_brl2(requested)} × 0,03 ÷ (1 − 1,03^−{term}) — tabela Price, juros de 3% ao mês, {term} parcelas",
                    result=_brl2(parcela)),
        ExplainLine(rule="antiga", label="Score, renda e restrições",
                    formula=f"score {o.score:.0f} (precisa passar de 600) · renda declarada {_brl2(declared)} "
                            f"(precisa passar de R$ 2.000,00) · {int(o.restricoes_ativas)} restrição(ões) ativa(s) "
                            f"(precisa ser 0)",
                    result="passa" if bool(o.score > 600 and declared > 2000 and o.restricoes_ativas == 0) else "não passa",
                    limit="Regra antiga exige os três",
                    passes=bool(o.score > 600 and declared > 2000 and o.restricoes_ativas == 0)),
        ExplainLine(rule="antiga", label="Parcela sobre a renda declarada",
                    formula=f"{_brl2(parcela)} ÷ {_brl2(declared)} (renda que o cliente informou)",
                    result=_pct1(old_share), limit="Regra antiga aceita até 30%", passes=bool(old_share <= 0.30)),
        ExplainLine(rule="dados", label="Renda efetiva",
                    formula=f"menor valor entre a renda declarada ({_brl2(declared)}) e o que de fato entra na conta "
                            f"por mês ({_brl2(inflow)})",
                    result=_brl2(effective)),
        ExplainLine(rule="nova", label="Parcela sobre a renda efetiva",
                    formula=f"{_brl2(parcela)} ÷ {_brl2(effective)}",
                    result=_pct1(new_share), limit=f"Regra nova aceita até {_pct1(p.max_commitment)}",
                    passes=bool(new_share <= p.max_commitment)),
        ExplainLine(rule="dados", label="Comprometimento total da renda efetiva",
                    formula=f"({_brl2(parcela)} da parcela + {_brl2(others)} de dívidas em outras instituições) "
                            f"÷ {_brl2(effective)}",
                    result=_pct1(total_share)),
        ExplainLine(rule="nova", label="Chance de calote",
                    formula="estimada pelo modelo de IA treinado com 2.832 contratos, olhando a parcela frente à "
                            "sobra do mês, o comportamento da conta e os dados do bureau",
                    result=_pct1(risk),
                    limit=f"Regra nova aceita até {_pct1(cutoff)}"
                          + (" (limite menor para quem não passa em score, renda ou restrições da regra antiga)"
                             if expansion else ""),
                    passes=bool(risk <= cutoff)),
    ]
    if row.decision == "APROVADO":
        amount = float(row.approved_amount)
        p_late = min(p.late_rate, 1 - risk)
        on_time = 1 - risk - p_late
        lines.append(ExplainLine(
            rule="nova", label="Resultado esperado para a Fortuna",
            formula=f"{_brl2(amount)} × (15% × {_pct1(on_time)} de pagar em dia + 5% × {_pct1(p_late)} de atrasar "
                    f"− 60% × {_pct1(risk)} de calote)",
            result=_brl2(amount * float(expected_rate(risk, p.late_rate)))))
    return lines


def _counteroffer_for(order_id: str, o: pd.Series) -> Counteroffer | None:
    from src.features import installment

    offers = _counteroffers()
    if order_id not in offers.index:
        return None
    offer = offers.loc[order_id]
    amount = float(offer.approved_amount)
    return Counteroffer(
        amount=round(amount, 2),
        installment=round(float(installment(amount, o.prazo_meses)), 2),
        default_risk=round(float(offer.default_risk), 4),
        expected_profit=round(float(offer.expected_profit), 2),
        share_of_request=round(amount / float(o.valor_solicitado), 4),
    )


def _orders_fixture() -> list[OrderDetail]:
    return [OrderDetail.model_validate(item) for item in _fixture("orders")]


def list_orders(
    decision: str | None = None,
    changed: bool | None = None,
    q: str | None = None,
    sort: OrderSort = "risk",
    page: int = 1,
    page_size: int = 50,
) -> OrderPage:
    if is_live():
        decisions = _current_decisions()
        orders = engine().new_grid.orders
        rows = [OrderSummary(**_summary_from(order_id, row, orders.loc[order_id]))
                for order_id, row in decisions.iterrows()]
    else:
        rows = [OrderSummary.model_validate(r.model_dump(include=set(OrderSummary.model_fields)))
                for r in _orders_fixture()]
    if decision:
        rows = [row for row in rows if row.decision == decision]
    if changed is not None:
        rows = [row for row in rows if row.changed_vs_current == changed]
    if q:
        needle = q.strip().upper()
        rows = [row for row in rows if needle in row.order_id or needle in row.customer_id]
    key = {
        "risk": lambda row: -row.default_risk,
        "risk_asc": lambda row: row.default_risk,
        "amount": lambda row: -row.requested_amount,
        "amount_asc": lambda row: row.requested_amount,
        "approved": lambda row: -row.approved_amount,
        "profit": lambda row: -row.expected_profit,
        "recent": lambda row: -row.order_date.toordinal(),
        "order_id": lambda row: row.order_id,
    }[sort]
    rows.sort(key=key)
    start = (page - 1) * page_size
    return OrderPage(items=rows[start : start + page_size], total=len(rows), page=page, page_size=page_size)


def get_order(order_id: str) -> OrderDetail:
    order_id = order_id.strip().upper()
    if is_live():
        return _live_detail(order_id)
    for row in _orders_fixture():
        if row.order_id == order_id:
            return row
    raise OrderNotFound(order_id)


def decisions_csv() -> str:
    """Official file format, from the same engine that generates selic_final.csv."""
    from src.decide import csv_text

    if is_live():
        return csv_text(_current_decisions())
    frame = pd.DataFrame(
        [{"decision": r.decision, "approved_amount": r.approved_amount} for r in _orders_fixture()],
        index=[r.order_id for r in _orders_fixture()],
    )
    return csv_text(frame)
