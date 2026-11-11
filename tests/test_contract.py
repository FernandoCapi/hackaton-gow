"""The API answers every route in the shape the front end expects."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from src import api, service
from src.schemas import OrderDetail, OrderPage, Pattern, Policy, SimulationResult, Summary


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "APPROVED_POLICY", tmp_path / "approved_policy.json")
    return TestClient(api.app)


def test_health_reports_each_section(client):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok"
    assert set(body["sections"]) == set(service.SECTIONS)


@pytest.mark.parametrize(
    ("path", "model"),
    [("/v1/summary", Summary), ("/v1/policy", Policy), ("/v1/orders", OrderPage)],
)
def test_get_routes_match_schema(client, path, model):
    response = client.get(path)
    assert response.status_code == 200
    model.model_validate(response.json())


def test_patterns_have_ready_sentences(client):
    patterns = [Pattern.model_validate(item) for item in client.get("/v1/patterns").json()]
    assert patterns and all(p.sentence and p.groups for p in patterns)


def test_policy_specs_cover_every_param(client):
    policy = Policy.model_validate(client.get("/v1/policy").json())
    assert {spec.name for spec in policy.param_specs} == set(policy.params.model_dump())


def test_simulate_echoes_params_and_reacts(client):
    strict = client.post("/v1/simulate", json={"params": {"risk_cutoff": 0.08}}).json()
    loose = client.post("/v1/simulate", json={"params": {"risk_cutoff": 0.30}}).json()
    SimulationResult.model_validate(strict)
    assert strict["params"]["risk_cutoff"] == 0.08
    assert strict["new_orders"]["approved"] < loose["new_orders"]["approved"]


def test_invalid_params_return_error_envelope(client):
    response = client.post("/v1/simulate", json={"params": {"risk_cutoff": 2}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_approve_changes_policy_in_force(client):
    params = {"max_restrictions": 1, "risk_cutoff": 0.15}
    approved = client.post("/v1/policy/approve", json={"params": params, "approved_by": "Analista"}).json()
    current = client.get("/v1/policy").json()
    assert current["version"] == approved["version"] == 2
    assert current["params"]["risk_cutoff"] == 0.15
    assert "15%" in current["steps"][1]["rule_text"]


def test_order_filters_and_detail(client):
    changed = client.get("/v1/orders", params={"changed": True}).json()
    assert changed["total"] > 0 and all(item["changed_vs_current"] for item in changed["items"])
    order_id = changed["items"][0]["order_id"]
    OrderDetail.model_validate(client.get(f"/v1/orders/{order_id}").json())


def test_unknown_order_returns_404_envelope(client):
    response = client.get("/v1/orders/P-00000X")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "order_not_found"


def test_decisions_csv_follows_official_format(client):
    response = client.get("/v1/decisions.csv")
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["id_pedido", "decisao", "valor_aprovado"]
    for order_id, decision, amount in rows[1:]:
        assert decision in {"APROVADO", "NEGADO"}
        assert amount == f"{float(amount):.2f}"
        assert (float(amount) > 0) == (decision == "APROVADO")


def test_committed_openapi_is_up_to_date():
    assert api.OPENAPI_FILE.read_text(encoding="utf-8") == api.openapi_text(), (
        "Contrato mudou: rode `python -m src.api --export-openapi` e commite contracts/openapi.json"
    )
