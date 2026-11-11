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
from src.schemas import (
    AccountInfo,
    ApproveRequest,
    BureauInfo,
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


# --- health ---------------------------------------------------------------------------


def health() -> Health:
    mode: SectionMode = "live" if is_live() else "fixtures"
    sections: dict[str, SectionMode] = {name: mode for name in SECTION_NAMES}
    sections["patterns"] = "live" if _patterns_live() else "fixtures"
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
    )


def _patterns_live() -> bool:
    from src.patterns import PATTERNS_FILE

    return os.getenv("ENGINE_MODE") != "fixtures" and (PATTERNS_FILE.exists() or is_live())


def patterns() -> list[Pattern]:
    from src import patterns as computed

    if not _patterns_live():
        return [Pattern.model_validate(item) for item in _fixture("patterns")]
    if not computed.PATTERNS_FILE.exists():
        return computed.save(engine().orders)
    return [Pattern.model_validate(item) for item in json.loads(computed.PATTERNS_FILE.read_text(encoding="utf-8"))]


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
    return [
        PolicyStep(order=1, kind="filter", outcome="approve", title="Quem pode ser aprovado",
                   rule_text=f"Segue para aprovação quem tem consulta ao bureau, score acima de {p.min_score}, renda acima "
                             f"de {_brl(p.min_income)} e no máximo {p.max_restrictions} restrições ativas: o perfil que o "
                             f"piloto testou. O score não é usado como corte de risco."),
        PolicyStep(order=2, kind="filter", outcome="deny", title="Nega com sinais de aperto na conta",
                   rule_text=f"Basta um destes para negar:\n"
                             f"• saídas acima de {_pct(p.max_outflow_ratio)} das entradas\n"
                             f"• cheque especial em mais de {p.max_recent_overdraft_months} dos 3 meses antes do pedido\n"
                             f"• conta esvaziada: saída recente {p.max_drain:g}x maior que a típica\n"
                             f"• entradas abaixo de {_pct(p.min_inflow_ratio)} da renda declarada\n"
                             f"• mais de {p.max_inquiries_90d} consultas ao CPF em 90 dias"),
        PolicyStep(order=3, kind="capacity", outcome="deny" if full_or_deny else "amount",
                   title="Nega quando a parcela não cabe" if full_or_deny else "Ajusta o valor à capacidade",
                   rule_text=f"A parcela pode consumir até {_pct(p.max_commitment)} da renda efetiva (a menor entre a "
                             f"renda declarada e a média de entradas na conta). {capacity_text}"),
        PolicyStep(order=4, kind="risk", outcome="deny", title="Nega pelo risco estimado pela IA",
                   rule_text=f"Um modelo treinado no histórico estima a chance de calote no valor a aprovar. Nega acima "
                             f"de {_pct(p.risk_cutoff)} para quem a política atual aprovaria e acima de "
                             f"{_pct(p.risk_cutoff_expansion)} para quem ela negaria.{margin}"),
        PolicyStep(order=5, kind="limit", outcome="amount", title="Valor aprovado",
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
        "amount": lambda row: -row.requested_amount,
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
