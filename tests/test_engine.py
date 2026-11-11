"""Decision engine against the real data. Skipped where the database or the trained model
(python -m src.risk_model) are not available."""
import numpy as np
import pandas as pd
import pytest

from src.policy import STEP_DOMAIN, current_policy, proposed_policy
from src.schemas import PolicyParams
from src.simulate import official_result


def test_official_scoring_matches_manual_example():
    # Manual 7.2: R$ 10k on time, R$ 6k late, R$ 5k default, 1 denied = -R$ 1,200
    amounts = [10000, 6000, 5000, 0]
    statuses = ["quitado_em_dia", "quitado_com_atraso", "inadimplente", "inadimplente"]
    assert official_result(amounts, statuses) == pytest.approx(-1200)


@pytest.fixture(scope="module")
def engine():
    from src import risk_model

    if not risk_model.MODEL_FILE.exists():
        pytest.skip("modelo nao treinado: rode python -m src.risk_model")
    try:
        from src.simulate import Engine

        return Engine()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"banco indisponivel: {error}")


def test_current_policy_reproduces_history(engine):
    hist = engine.orders[engine.orders.politica_aplicada.eq("atual")]
    current = current_policy(hist)
    assert (current.current_decision.str.lower() == hist.decisao).all()
    approved = hist.decisao.eq("aprovado")
    assert (current.current_amount[approved] - hist.valor_aprovado[approved]).abs().max() < 0.5


def test_smaller_amount_never_raises_risk(engine):
    risk = engine.new_grid.risk  # columns: 100%, 90%, ..., 30% of the requested amount
    assert (np.diff(risk, axis=1) <= 1e-9).all()


@pytest.mark.parametrize("rule", ["full_or_deny", "maximize_expected_profit"])
def test_decisions_respect_product_limits(engine, rule):
    decisions = engine.decide_new(PolicyParams(amount_rule=rule))
    orders = engine.new_grid.orders
    approved = decisions.decision.eq("APROVADO")
    amount = decisions.approved_amount[approved]
    assert (amount >= 500).all()
    assert (amount <= np.minimum(orders.valor_solicitado[approved], 30000) + 0.005).all()
    assert (decisions.approved_amount[~approved] == 0).all()


def test_order_without_bureau_is_denied(engine):
    grid = engine.new_grid.subset(np.arange(len(engine.new_grid.orders)) < 50)
    grid.orders = grid.orders.copy()
    grid.orders["bureau_ausente"] = True
    decisions = proposed_policy(grid, PolicyParams())
    assert decisions.decision.eq("NEGADO").all()
    assert decisions.denied_at.eq(STEP_DOMAIN).all()


def test_bureau_api_is_only_queried_for_new_clients(engine):
    from src import bureau

    queried = set(bureau.new_clients())
    new_clients = set(engine.orders.loc[engine.orders.tipo_base.eq("novo"), "id_cliente"])
    historical_clients = set(engine.orders.loc[engine.orders.tipo_base.eq("historico"), "id_cliente"])
    assert queried == new_clients
    assert not queried & historical_clients


def test_generated_csv_passes_validation(engine, tmp_path):
    from src.decide import validate_csv, write_csv

    path = tmp_path / "selic_final.csv"
    write_csv(engine.decide_new(PolicyParams()), path)
    assert validate_csv(path, engine.new_grid.orders.valor_solicitado) == []
    assert len(pd.read_csv(path)) == 2000


def test_patterns_are_computed_from_data(engine):
    import re

    from src.patterns import compute_patterns

    patterns = {p.id: p for p in compute_patterns(engine.orders)}
    assert {p.kind for p in patterns.values()} == {"risk", "opportunity", "trap"}
    for p in patterns.values():
        assert p.customers_affected > 0 and p.groups
        assert 0 <= p.group_default_rate <= 1 and 0 <= p.overall_default_rate <= 1
        assert f"{p.customers_affected:,}".replace(",", ".") in p.sentence or p.kind == "trap"
    outflow = patterns["outflow_over_inflow"]  # reference from analysis/findings_auditoria.md
    assert (outflow.customers_affected, round(outflow.group_default_rate, 2)) == (67, 0.91)
    assert outflow.new_orders_affected == 97
    payload = "".join(p.model_dump_json() for p in patterns.values())
    assert not re.search(r"\b[PC]-\d{5}\b", payload), "padroes nao podem expor ids de clientes"


def test_minimum_balance_agrees_with_overdraft_days(engine):
    # The oldest statement month carries an overdraft artifact; both measures skip it.
    o = engine.orders
    assert not ((o.saldo_minimo < 0) & (o.dias_cheque_12m == 0)).any()
    assert not ((o.saldo_minimo >= 0) & (o.dias_cheque_12m > 0)).any()


def test_pilot_shows_good_customers_gained(engine):
    assert engine.simulate(PolicyParams(), with_steps=False).historical.good_customers_gained > 0


@pytest.mark.parametrize("rule", ["full_or_deny", "maximize_expected_profit"])
def test_step_titles_match_the_policy_page(engine, rule):
    from src import service
    from src.policy import decision_steps

    params = PolicyParams(amount_rule=rule)
    titles = {step.title for step in service.policy_steps(params)}
    decisions = engine.decide_new(params)
    orders = engine.new_grid.orders
    sample = pd.concat([decisions[decisions.denied_at.eq(step)].head(3) for step in decisions.denied_at.unique()])
    for order_id, row in sample.iterrows():
        assert {s["title"] for s in decision_steps(row, orders.loc[order_id], params)} <= titles
    impacts = engine.simulate(params).steps_impact
    assert {impact.step for impact in impacts} <= titles


def test_proposed_policy_beats_current_on_history(engine):
    result = engine.simulate(PolicyParams(), with_steps=False)
    assert result.historical.gain > 0
    assert result.new_orders.expected_gain > 0
