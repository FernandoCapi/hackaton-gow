# Contrato da API — motor de decisão ↔ painel

O motor (Python, FastAPI) calcula tudo; o painel (Next, em `web/`) só busca e desenha.
Fonte da verdade: `src/schemas.py`. Arquivo para gerar tipos: `contracts/openapi.json`.
Documentação interativa com o motor no ar: <http://localhost:8000/docs>.

## Como usar no front

1. **Subir o motor** (na raiz do repo, com a `.venv`):
   ```
   uvicorn src.api:app --reload --port 8000
   ```
2. **Proxy no Next** (`web/next.config.*`), para não depender de CORS nem de URL fixa:
   ```js
   async rewrites() {
     return [{ source: '/api/:path*', destination: 'http://localhost:8000/v1/:path*' }]
   }
   ```
   No front, chame sempre `/api/...` (ex.: `fetch('/api/orders?changed=true')`).
3. **Tipos TypeScript** gerados do contrato (refazer quando `contracts/openapi.json` mudar):
   ```
   npx openapi-typescript ../contracts/openapi.json -o src/lib/api-types.ts
   ```
   Uso: `import type { components } from '@/lib/api-types'` e
   `type OrderDetail = components['schemas']['OrderDetail']`.
4. **Sem Python?** As respostas de exemplo estão em `contracts/fixtures/*.json` e podem ser
   servidas por rotas mock do próprio Next até o motor estar disponível.

## Dados de exemplo × motor real

Enquanto o motor é construído, cada rota responde com exemplos inventados (pedidos
`P-99001` a `P-99006`). `GET /v1/health` diz a origem de cada seção:
`"sections": { "orders": "fixtures" | "live", ... }`. Mostre uma faixa "dados de exemplo"
enquanto `mode` for `"fixtures"`. Quando uma seção vira `live`, o formato não muda.

Em modo de exemplo, `POST /v1/simulate` só escala os números para os controles reagirem;
os valores não são uma simulação real.

## Tela → rota

| Tela / componente | Rota | Quando chamar |
|---|---|---|
| Faixa de status | `GET /v1/health` | Ao abrir |
| Visão geral (KPIs do topo) | `GET /v1/summary` | Ao abrir e após aprovar política |
| Parte 1 — Padrões encontrados | `GET /v1/patterns` | Ao abrir |
| Parte 2 — Política em vigor + controles | `GET /v1/policy` | Ao abrir e após aprovar |
| Laboratório (simulação) | `POST /v1/simulate` | A cada mudança nos controles, com debounce de ~300 ms |
| Botão "Aprovar política" | `POST /v1/policy/approve` | Clique do analista |
| Lista de pedidos novos | `GET /v1/orders` | Ao abrir, filtrar, paginar |
| Detalhe do pedido (demo ao vivo) | `GET /v1/orders/{order_id}` | Clique na lista ou busca |
| Baixar arquivo de decisões | `GET /v1/decisions.csv` | Clique (download `selic_final.csv`) |

Regras para o front não ter lógica de negócio:

- **Controles vêm da API.** `GET /v1/policy` → `param_specs[]` traz `name`, `label`,
  `description`, `kind` (`number` | `select`), `min`, `max`, `step`, `unit`
  (`percent` | `brl` | `count`), `options` e `value`. Monte cada controle a partir disso e
  envie `{ params: { [name]: valor } }` para `/simulate` e `/policy/approve`.
- **Textos prontos** para exibir: `Pattern.sentence`, `PolicyStep.rule_text`,
  `OrderDetail.reasons[]`, `DecisionStep.detail`.
- **Gráficos já agregados:** `Pattern.groups[]` (barras por grupo) e
  `SimulationResult.by_risk_band[]` (resultado atual × proposto por faixa de risco).
- **Simular não altera nada.** Só `POST /v1/policy/approve` muda a política em vigor; depois
  dele, recarregue `/summary`, `/policy` e `/orders`.

## Convenções

| Item | Regra |
|---|---|
| Prefixo | `/v1` |
| Campos | inglês, `snake_case` |
| Dinheiro | número em reais, 2 casas (`8500.00`). Formatar com `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })` |
| Taxas e risco | fração de 0 a 1 (`0.12` = 12%) |
| Datas | ISO 8601 (`2026-10-15`, `2026-11-11T10:42:00-03:00`) |
| Decisão | `"APROVADO"` ou `"NEGADO"` (iguais ao CSV oficial) |
| Erros | sempre `{ "error": { "code", "message" } }`; `message` pode ser exibida |
| Paginação | `{ items, total, page, page_size }`; `page_size` até 200 |
| Evolução | depois do congelamento (~10h30), só mudanças **aditivas** |

Códigos de erro: `invalid_request` (422, parâmetro fora da faixa), `order_not_found` (404),
`not_found` (404, rota inexistente).

## Rotas

### `GET /v1/orders`

Query: `decision` (`APROVADO` | `NEGADO`), `changed` (`true` = decisão difere da política
atual), `q` (trecho do id do pedido ou do cliente), `sort` (`risk` | `amount` | `order_id`;
padrão `risk`, do maior para o menor), `page`, `page_size`.

```json
{ "items": [ { "order_id": "P-99004", "decision": "NEGADO", "approved_amount": 0.0,
  "default_risk": 0.34, "current_decision": "APROVADO", "changed_vs_current": true, "...": "..." } ],
  "total": 6, "page": 1, "page_size": 50 }
```

### `GET /v1/orders/{order_id}`

Tudo de `OrderSummary` mais: `employment_type`, `income_declared`, `installment`,
`income_commitment`, `bureau{}`, `account{}`, `reasons[]` e `steps[]` (cada passo com
`result` `passou` | `negou` | `ajustou`). Exemplo completo em `contracts/fixtures/orders.json`.

### `POST /v1/simulate`

```json
{ "params": { "risk_cutoff": 0.15, "max_restrictions": 0 } }
```

Campos omitidos usam o padrão. A resposta repete `params` e traz `historical` (resultado
em R$ no histórico: atual × proposto, ganho, calotes evitados, bons clientes ganhos),
`new_orders` (aprovados, negados, valor total, quantos mudam em relação à política atual)
e `by_risk_band[]`. Exemplo em `contracts/fixtures/simulation.json`.

### `POST /v1/policy/approve`

```json
{ "params": { "risk_cutoff": 0.15 }, "approved_by": "Nome do analista", "note": "opcional" }
```

Devolve a nova `Policy` com `version` incrementada, `approved_at` e `approved_by`.

Os demais exemplos estão em `contracts/fixtures/` (`summary.json`, `patterns.json`,
`policy.json`).

## Para quem mexe no motor

- Rotas em `src/api.py` só traduzem HTTP; a lógica fica em `src/service.py`.
- Para ligar uma seção ao motor real: troque a função em `src/service.py` e mude a seção
  para `"live"` em `SECTIONS`.
- Mudou um esquema em `src/schemas.py`? Rode `python -m src.api --export-openapi`, commite
  `contracts/openapi.json` e avise o front. O teste `test_committed_openapi_is_up_to_date`
  falha se esquecer.
- Testes: `python -m pytest -q`.
