"""HTTP API of the decision engine, consumed by the Next.js front end.

    uvicorn src.api:app --reload --port 8000     # serve (docs at /docs)
    python -m src.api --export-openapi           # refresh contracts/openapi.json

Routes only translate HTTP <-> src.service; the contract lives in src/schemas.py.
"""
import argparse
import json
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from src import service
from src.schemas import (
    ApproveRequest,
    Decision,
    ErrorResponse,
    Health,
    OrderDetail,
    OrderPage,
    OrderSort,
    Pattern,
    Policy,
    SimulationRequest,
    SimulationResult,
    Summary,
)

OPENAPI_FILE = config.ROOT / "contracts" / "openapi.json"
ERRORS = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}

app = FastAPI(
    title="Fortuna Crédito — motor de decisão",
    version="1.0.0",
    description="Contrato entre o motor de decisão (Python) e o painel (Next). Ver docs/api.md.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'] if part != 'body')}: {error['msg']}"
        for error in exc.errors()
    )
    return _error(422, "invalid_request", problems)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(service.OrderNotFound)
async def order_not_found(_: Request, exc: service.OrderNotFound) -> JSONResponse:
    return _error(404, "order_not_found", f"Pedido {exc.args[0]} não existe na base de novos pedidos.")


@app.exception_handler(service.EngineUnavailable)
async def engine_unavailable(_: Request, exc: service.EngineUnavailable) -> JSONResponse:
    return _error(503, "engine_unavailable", str(exc))


v1 = "/v1"


@app.get(f"{v1}/health", response_model=Health, tags=["status"])
def get_health():
    return service.health()


@app.get(f"{v1}/summary", response_model=Summary, tags=["painel"])
def get_summary():
    return service.summary()


@app.get(f"{v1}/patterns", response_model=list[Pattern], tags=["painel"])
def get_patterns():
    return service.patterns()


@app.get(f"{v1}/policy", response_model=Policy, tags=["política"])
def get_policy():
    return service.current_policy()


@app.post(f"{v1}/policy/approve", response_model=Policy, responses=ERRORS, tags=["política"])
def post_approve(request: ApproveRequest):
    return service.approve_policy(request)


@app.post(f"{v1}/simulate", response_model=SimulationResult, responses=ERRORS, tags=["política"])
def post_simulate(request: SimulationRequest):
    return service.simulate(request.params)


@app.get(f"{v1}/orders", response_model=OrderPage, responses=ERRORS, tags=["pedidos"])
def get_orders(
    decision: Decision | None = None,
    changed: Annotated[bool | None, Query(description="Só pedidos em que a decisão difere da política atual")] = None,
    q: Annotated[str | None, Query(description="Busca por id do pedido ou do cliente")] = None,
    sort: OrderSort = "risk",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return service.list_orders(decision, changed, q, sort, page, page_size)


@app.get(f"{v1}/orders/{{order_id}}", response_model=OrderDetail, responses=ERRORS, tags=["pedidos"])
def get_order(order_id: str):
    return service.get_order(order_id)


@app.get(
    f"{v1}/decisions.csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}, "description": "Arquivo de decisões no formato oficial"}},
    tags=["pedidos"],
)
def get_decisions_csv(
    decision: Decision | None = None,
    changed: Annotated[bool | None, Query(description="Só pedidos em que a decisão difere da política atual")] = None,
    q: Annotated[str | None, Query(description="Busca por id do pedido ou do cliente")] = None,
):
    filtered = decision is not None or changed is not None or bool(q)
    # a filtered file must never be mistaken for the official one
    filename = f"{config.TEAM_ID}_{'filtrado' if filtered else 'final'}.csv"
    return PlainTextResponse(
        service.decisions_csv(decision, changed, q),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def openapi_text() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--export-openapi", action="store_true", help=f"grava {OPENAPI_FILE.name}")
    if parser.parse_args().export_openapi:
        OPENAPI_FILE.write_text(openapi_text(), encoding="utf-8", newline="\n")
        print(f"Gravado {OPENAPI_FILE.relative_to(config.ROOT)}")
