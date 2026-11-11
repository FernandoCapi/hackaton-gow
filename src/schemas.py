"""API contract between the decision engine and the front end.

These Pydantic models are the single source of truth: FastAPI publishes them as OpenAPI
(contracts/openapi.json) and the front generates its TypeScript types from that file.
After the freeze, changes must be additive only (new optional fields or new routes).

Conventions: money in BRL with 2 decimals, rates as fractions (0.12 = 12%), ISO dates,
decision values identical to the official CSV.
"""
from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["APROVADO", "NEGADO"]
SectionMode = Literal["fixtures", "live"]
Money = float
Rate = float

T = TypeVar("T")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- errors and pagination ------------------------------------------------------------


class ErrorBody(Model):
    code: str = Field(examples=["order_not_found"])
    message: str = Field(examples=["Pedido P-99999 não existe na base de novos pedidos."])


class ErrorResponse(Model):
    error: ErrorBody


class Page(Model, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# --- health ---------------------------------------------------------------------------


class Health(Model):
    status: Literal["ok"]
    mode: SectionMode = Field(description="'fixtures' enquanto alguma seção ainda usa dados de exemplo")
    sections: dict[str, SectionMode] = Field(description="Origem dos dados por rota")
    data_cutoff: date
    model_version: str | None = None


# --- summary --------------------------------------------------------------------------


class ResultBlock(Model):
    approved: int
    denied: int
    approved_amount: Money
    expected_result: Money = Field(description="Resultado esperado em R$ pela regra +15% / +5% / -60%")


class ModelQuality(Model):
    auc: float = Field(description="Capacidade do modelo de separar bons e maus pagadores (0,5 a 1)")
    auc_current_rule: float = Field(description="Mesma medida para a regra atual (score > 600)")
    trained_until: date
    validated_on: str = Field(examples=["contratos de jul/2025 a dez/2025"])


class Summary(Model):
    new_orders_total: int
    historical_mature_total: int
    base_default_rate: Rate
    current_policy: ResultBlock
    proposed_policy: ResultBlock
    gain: Money = Field(description="proposed_policy.expected_result - current_policy.expected_result")
    model: ModelQuality
    counteroffers: int | None = Field(
        None, description="EXTRA: pedidos negados por capacidade ou risco que teriam aprovação com um valor menor"
    )


# --- patterns -------------------------------------------------------------------------


class PatternGroup(Model):
    label: str
    default_rate: Rate
    customers: int


class Pattern(Model):
    id: str
    sentence: str = Field(description="Frase pronta no formato do manual")
    group_description: str
    group_default_rate: Rate
    overall_default_rate: Rate
    customers_affected: int
    direction: Literal["worse", "better"]
    current_policy_view: Literal["approves", "denies", "mixed"] = Field(
        description="Como a política atual trata esse grupo"
    )
    groups: list[PatternGroup] = Field(description="Barras do gráfico, já agregadas")
    kind: Literal["risk", "opportunity", "trap"] | None = Field(
        None,
        description="risk: a atual aprova e perde; opportunity: a atual nega quem pagaria; "
        "trap: parece perigoso, mas não é",
    )
    new_orders_affected: int | None = Field(None, description="Quantos dos 2.000 pedidos novos caem no grupo")
    policy_step: str | None = Field(None, description="Passo da política proposta que usa este padrão")
    evidence: Literal["historico_maduro", "piloto"] | None = Field(
        None, description="historico_maduro: contratos com 12+ meses; piloto: sorteado, calote ainda parcial"
    )
    caveat: str | None = Field(None, description="Ressalva para o analista (amostra pequena, base de comparação)")


# --- policy ---------------------------------------------------------------------------


class PolicyParams(Model):
    """Every number of the proposed policy. Omitted fields take the default."""

    # Step 1 - outside what the pilot tested (no data to approve safely)
    min_score: int = Field(450, ge=0, le=1000, description="Nega com score do bureau até este valor")
    min_income: Money = Field(1500.0, ge=0, le=20000, description="Nega com renda declarada até este valor")
    max_restrictions: int = Field(
        0, ge=0, le=10,
        description="Nega acima deste número de restrições (1 restrição: 19–23% de calote no piloto; o modelo não as viu)",
    )
    # Step 2 - signs of financial strain in the account
    max_outflow_ratio: Rate = Field(0.90, ge=0, le=2, description="Nega se as saídas passam desta fração das entradas")
    max_recent_overdraft_months: int = Field(
        1, ge=0, le=3, description="Nega acima deste número de meses com cheque especial nos 3 antes do pedido"
    )
    max_drain: float = Field(3.0, ge=1, le=20, description="Nega se a maior saída recente passa X vezes a saída típica")
    min_inflow_ratio: Rate = Field(0.60, ge=0, le=2, description="Nega se as entradas cobrem menos que isto da renda declarada")
    max_inquiries_90d: int = Field(7, ge=0, le=50, description="Nega acima deste número de consultas ao CPF em 90 dias")
    # Step 3 - capacity and amount
    max_commitment: Rate = Field(0.25, ge=0.05, le=0.5, description="Parcela máxima sobre a renda efetiva")
    amount_rule: Literal["full_or_deny", "maximize_expected_profit"] = "full_or_deny"
    # Step 4 - risk estimated by the model
    risk_cutoff: Rate = Field(0.15, ge=0, le=1, description="Nega com chance de calote acima disto (quem a política atual aprovaria)")
    risk_cutoff_expansion: Rate = Field(
        0.12, ge=0, le=1, description="Mesmo corte para quem a política atual negaria (evidência só do piloto)"
    )
    safety_margin: Rate = Field(0.0, ge=0, le=0.5, description="Resultado esperado mínimo por real emprestado")
    late_rate: Rate = Field(0.20, ge=0, le=0.6, description="Chance de atraso usada na conta (não é previsível nos dados)")
    # Step 5 - product limits
    min_amount: Money = Field(500.0, ge=500, le=30000)


class ParamOption(Model):
    value: str
    label: str


class ParamSpec(Model):
    name: str = Field(description="Chave em PolicyParams")
    label: str
    description: str
    kind: Literal["number", "select"]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: Literal["percent", "brl", "count"] | None = None
    options: list[ParamOption] | None = None
    value: float | str


class PolicyStep(Model):
    order: int
    kind: Literal["filter", "capacity", "risk", "amount", "limit"]
    outcome: Literal["approve", "deny", "amount"] = Field(description="O que o passo decide: aprova, nega ou define o valor")
    title: str
    rule_text: str


class Policy(Model):
    version: int
    approved_at: datetime | None
    approved_by: str | None
    note: str | None = None
    params: PolicyParams
    steps: list[PolicyStep]
    param_specs: list[ParamSpec]


class ApproveRequest(Model):
    params: PolicyParams
    approved_by: str = Field(min_length=1)
    note: str | None = None


# --- simulation -----------------------------------------------------------------------


class SimulationRequest(Model):
    params: PolicyParams


class HistoricalResult(Model):
    current_result: Money
    proposed_result: Money
    gain: Money
    approved_current: int
    approved_proposed: int
    defaults_avoided: int = Field(description="Calotes que a política atual aprovou e a proposta nega")
    good_customers_gained: int = Field(
        description="No piloto (única evidência sobre quem a atual nega): clientes que a atual negaria, a proposta "
        "aprova e que não deram calote até agora (contratos de 6 a 12 meses, calote ainda parcial)"
    )


class NewOrdersResult(Model):
    approved: int
    denied: int
    total_approved_amount: Money
    current_approved: int
    changed_vs_current: int
    expected_result: Money | None = Field(None, description="Resultado esperado pelo modelo, política proposta")
    current_expected_result: Money | None = Field(None, description="Resultado esperado pelo modelo, política atual")
    expected_gain: Money | None = Field(None, description="Estimativa do ganho que a nota de 40% mede")


class RiskBand(Model):
    band: str = Field(examples=["5–10%"])
    orders: int
    observed_default_rate: Rate
    current_result: Money
    proposed_result: Money


class StepImpact(Model):
    step: str = Field(examples=["Sinais de aperto na conta"])
    denied_new_orders: int = Field(description="Pedidos novos negados neste passo")
    historical_gain_if_removed: Money = Field(
        description="Quanto o resultado no histórico muda se o passo for desligado (negativo = o passo ajuda)"
    )
    new_orders_gain_if_removed: Money = Field(description="Mesma medida, estimada nos pedidos novos")


class SimulationResult(Model):
    params: PolicyParams
    historical: HistoricalResult
    new_orders: NewOrdersResult
    by_risk_band: list[RiskBand]
    steps_impact: list[StepImpact] = Field(default_factory=list)


# --- orders ---------------------------------------------------------------------------


class OrderSummary(Model):
    order_id: str
    customer_id: str
    order_date: date
    requested_amount: Money
    term_months: int
    decision: Decision
    approved_amount: Money
    default_risk: Rate
    expected_profit: Money
    current_decision: Decision
    current_approved_amount: Money
    changed_vs_current: bool


class BureauInfo(Model):
    score: int
    active_restrictions: int
    other_installments: Money
    inquiries_90d: int
    bureau_history_months: int


class AccountInfo(Model):
    months_of_history: int
    avg_salary_inflow: Money
    avg_total_inflow: Money
    avg_outflow: Money
    min_balance: Money
    overdraft_days_12m: int


class DecisionStep(Model):
    order: int
    title: str
    result: Literal["passou", "negou", "ajustou"]
    detail: str


class Counteroffer(Model):
    """EXTRA, fora do arquivo oficial: valor menor que a política aprovaria para um pedido negado."""

    amount: Money
    installment: Money
    default_risk: Rate
    expected_profit: Money
    share_of_request: Rate = Field(description="amount / valor pedido")


class ExplainLine(Model):
    """One calculation shown to the analyst in plain words: what, how, result, and the limit it meets."""

    rule: Literal["nova", "antiga", "dados"] = Field(description="Regra nova (proposta), regra antiga ou dado do cliente")
    label: str
    formula: str = Field(description="A conta por extenso, com os valores do pedido")
    result: str
    limit: str | None = Field(None, description="Limite da regra e se o pedido passa")
    passes: bool | None = None


class OrderDetail(OrderSummary):
    employment_type: str
    income_declared: Money
    installment: Money = Field(description="Parcela do valor aprovado (ou do solicitado, se negado)")
    income_commitment: Rate = Field(description="(parcela + parcelas em outras instituições) / renda")
    bureau: BureauInfo
    account: AccountInfo
    reasons: list[str]
    steps: list[DecisionStep]
    effective_income: Money | None = Field(None, description="Menor entre a renda declarada e as entradas médias na conta")
    explain: list[ExplainLine] = Field(default_factory=list, description="Como chegamos aos números, conta a conta")
    counteroffer: Counteroffer | None = Field(
        None, description="EXTRA: só para negados por capacidade ou risco; não entra no selic_final.csv"
    )


class OrderPage(Page[OrderSummary]):
    pass


OrderSort = Literal["risk", "risk_asc", "amount", "amount_asc", "approved", "profit", "recent", "order_id"]
