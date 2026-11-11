"""Facade between the API routes and the decision engine.

Every route calls one function here. While the engine is being built, the functions
answer from contracts/fixtures/ (invented, schema-valid examples). Replace them one by one
with the real engine and switch the section to "live" in SECTIONS; the routes and the
front end do not change.
"""
import csv
import io
import json
from datetime import date, datetime
from functools import lru_cache

import config
from src.schemas import (
    ApproveRequest,
    Health,
    OrderDetail,
    OrderPage,
    OrderSort,
    OrderSummary,
    Pattern,
    Policy,
    PolicyParams,
    PolicyStep,
    SectionMode,
    SimulationResult,
    Summary,
)

FIXTURES = config.ROOT / "contracts" / "fixtures"
APPROVED_POLICY = config.ARTIFACTS / "approved_policy.json"
DATA_CUTOFF = date(2026, 9, 30)

SECTIONS: dict[str, SectionMode] = {
    "summary": "fixtures",
    "patterns": "fixtures",
    "policy": "fixtures",
    "simulate": "fixtures",
    "orders": "fixtures",
    "decisions_csv": "fixtures",
}


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


# --- health ---------------------------------------------------------------------------


def health() -> Health:
    mode: SectionMode = "live" if all(m == "live" for m in SECTIONS.values()) else "fixtures"
    return Health(status="ok", mode=mode, sections=SECTIONS, data_cutoff=DATA_CUTOFF)


# --- summary and patterns -------------------------------------------------------------


def summary() -> Summary:
    return Summary.model_validate(_fixture("summary"))


def patterns() -> list[Pattern]:
    return [Pattern.model_validate(item) for item in _fixture("patterns")]


# --- policy ---------------------------------------------------------------------------


def policy_steps(params: PolicyParams) -> list[PolicyStep]:
    """Business-language steps of the proposed policy, in the order they are applied."""
    amount_text = (
        "Testa valores de 100% a 30% do pedido e aprova o que dá o maior resultado esperado: "
        "valores menores reduzem a parcela e o risco."
        if params.amount_rule == "maximize_expected_profit"
        else "Reduz o valor por faixa de risco: quanto maior o risco, menor a fração do pedido aprovada."
    )
    margin_text = (
        f" Exige resultado esperado de pelo menos {_pct(params.safety_margin)} do valor."
        if params.safety_margin
        else ""
    )
    return [
        PolicyStep(
            order=1,
            kind="filter",
            title="Filtro de restrições",
            rule_text=f"Nega pedidos com mais de {params.max_restrictions} restrições ativas no bureau.",
        ),
        PolicyStep(
            order=2,
            kind="risk",
            title="Risco estimado pela IA",
            rule_text=(
                "Um modelo treinado no histórico estima a chance de o cliente não pagar. "
                f"Acima de {_pct(params.risk_cutoff)}, nega.{margin_text}"
            ),
        ),
        PolicyStep(order=3, kind="amount", title="Valor aprovado", rule_text=amount_text),
        PolicyStep(
            order=4,
            kind="limit",
            title="Limites do produto",
            rule_text=(
                f"O valor fica entre {_brl(params.min_amount)} e o menor entre o valor pedido e "
                f"R$ 30.000; abaixo de {_brl(params.min_amount)}, nega."
            ),
        ),
    ]


def _with_params(base: Policy, params: PolicyParams) -> Policy:
    values = {
        name: value if isinstance(value, str) else float(value)  # ParamSpec.value is float | str
        for name, value in params.model_dump().items()
    }
    specs = [spec.model_copy(update={"value": values[spec.name]}) for spec in base.param_specs]
    return base.model_copy(update={"params": params, "steps": policy_steps(params), "param_specs": specs})


def current_policy() -> Policy:
    """The policy in force: the last one approved by the analyst, else the AI proposal."""
    if APPROVED_POLICY.exists():
        return Policy.model_validate_json(APPROVED_POLICY.read_text(encoding="utf-8"))
    base = Policy.model_validate(_fixture("policy"))
    return _with_params(base, base.params)


def approve_policy(request: ApproveRequest) -> Policy:
    previous = current_policy()
    approved = _with_params(previous, request.params).model_copy(
        update={
            "version": previous.version + 1,
            "approved_at": datetime.now().astimezone(),
            "approved_by": request.approved_by,
            "note": request.note,
        }
    )
    config.ARTIFACTS.mkdir(exist_ok=True)
    APPROVED_POLICY.write_text(approved.model_dump_json(indent=2), encoding="utf-8")
    return approved


# --- simulation -----------------------------------------------------------------------


def simulate(params: PolicyParams) -> SimulationResult:
    """Fixture mode: scales the example so the front can see sliders react.

    The numbers are NOT a real simulation until this section is "live".
    """
    base = SimulationResult.model_validate(_fixture("simulation"))
    looseness = params.risk_cutoff / 0.20  # >1 approves more, <1 approves less
    quality = max(0.0, 1 - 4 * (params.risk_cutoff - 0.20) ** 2 - 2 * params.safety_margin)
    restriction_bonus = 1 + 0.03 * params.max_restrictions

    hist = base.historical
    proposed_result = round(hist.proposed_result * quality, 2)
    approved_proposed = round(hist.approved_proposed * looseness**0.3 * restriction_bonus)
    new = base.new_orders
    approved_new = min(2000, round(new.approved * looseness**0.3 * restriction_bonus))
    bands = [
        band.model_copy(update={"proposed_result": round(band.proposed_result * quality, 2)})
        for band in base.by_risk_band
    ]
    return base.model_copy(
        update={
            "params": params,
            "historical": hist.model_copy(
                update={
                    "proposed_result": proposed_result,
                    "gain": round(proposed_result - hist.current_result, 2),
                    "approved_proposed": approved_proposed,
                }
            ),
            "new_orders": new.model_copy(
                update={
                    "approved": approved_new,
                    "denied": 2000 - approved_new,
                    "total_approved_amount": round(new.total_approved_amount * approved_new / new.approved, 2),
                }
            ),
            "by_risk_band": bands,
        }
    )


# --- orders ---------------------------------------------------------------------------


def _orders() -> list[OrderDetail]:
    return [OrderDetail.model_validate(item) for item in _fixture("orders")]


def list_orders(
    decision: str | None = None,
    changed: bool | None = None,
    q: str | None = None,
    sort: OrderSort = "risk",
    page: int = 1,
    page_size: int = 50,
) -> OrderPage:
    rows = _orders()
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
    items = [OrderSummary.model_validate(row.model_dump(include=set(OrderSummary.model_fields))) for row in rows]
    return OrderPage(items=items[start : start + page_size], total=len(rows), page=page, page_size=page_size)


def get_order(order_id: str) -> OrderDetail:
    for row in _orders():
        if row.order_id == order_id.strip().upper():
            return row
    raise OrderNotFound(order_id)


def decisions_csv() -> str:
    """Official file format: id_pedido,decisao,valor_aprovado (UTF-8, comma, 2 decimals)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["id_pedido", "decisao", "valor_aprovado"])
    for row in sorted(_orders(), key=lambda row: row.order_id):
        amount = row.approved_amount if row.decision == "APROVADO" else 0.0
        writer.writerow([row.order_id, row.decision, f"{amount:.2f}"])
    return buffer.getvalue()
