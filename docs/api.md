# Contrato da API — motor de decisão ↔ painel

O motor (Python, FastAPI) calcula tudo; o painel (Next, em `app/`) só busca e desenha.
Fonte da verdade: `src/schemas.py`. Arquivo para gerar tipos: `contracts/openapi.json`.
Documentação interativa com o motor no ar: <http://localhost:8000/docs>.

## Como usar no front

1. **Subir o motor** (na raiz do repo, com a `.venv`):
   ```
   uvicorn src.api:app --reload --port 8000
   ```
2. **Proxy no Next** (`app/next.config.ts`), para não depender de CORS nem de URL fixa:
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
4. **Sem banco ou modelo?** O motor responde sozinho com `contracts/fixtures/` (ou force com
   `ENGINE_MODE=fixtures`); basta `pip install -r requirements.txt`. Não há mock no Next.

## Dados de exemplo × motor real

Com o banco restaurado e o modelo treinado (`python -m src.risk_model`), as rotas respondem
com o **motor real** (pedidos `P-xxxxx` de verdade). Sem isso, respondem com exemplos
inventados (pedidos `P-99001` a `P-99006`); `ENGINE_MODE=fixtures` força os exemplos.
`GET /v1/health` diz a origem de cada seção: `"sections": { "orders": "fixtures" | "live", ... }`.
Hoje só `patterns` continua em exemplo. Quando uma seção vira `live`, o formato não muda.

A primeira chamada ao motor real leva ~2 s (carrega dados e modelo); depois, `/simulate`
responde em ~0,35 s. Em modo de exemplo, `/simulate` só escala os números para os controles
reagirem.

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
{ "params": { "risk_cutoff": 0.15, "max_commitment": 0.25 } }
```

Campos omitidos usam o padrão. A resposta repete `params` e traz:

- `historical`: resultado em R$ com o desfecho real dos contratos maduros (atual × proposta,
  ganho, calotes evitados, bons clientes ganhos);
- `new_orders`: aprovados, negados, volume, quantos mudam em relação à atual e
  `expected_result` / `current_expected_result` / `expected_gain` (estimativa da nota de 40%);
- `by_risk_band[]`: gráfico de resultado por faixa de risco;
- `steps_impact[]`: por passo da política, quantos pedidos novos ele nega e quanto o resultado
  mudaria sem ele (negativo = o passo protege dinheiro).

### Parâmetros da política (`PolicyParams`)

Todos opcionais; `GET /v1/policy` → `param_specs[]` traz rótulo, faixa, passo e unidade de cada um.

| Passo | Campo | Padrão | O que faz |
|---|---|---|---|
| 1 | `min_score` | 450 | Nega score até este valor (o piloto só testou acima) |
| 1 | `min_income` | 1500 | Nega renda declarada até este valor |
| 1 | `max_restrictions` | 0 | Nega acima deste número de restrições |
| 2 | `max_outflow_ratio` | 0.90 | Nega se as saídas passam desta fração das entradas |
| 2 | `max_recent_overdraft_months` | 1 | Nega acima deste nº de meses com cheque especial nos 3 antes do pedido |
| 2 | `max_drain` | 3.0 | Nega se a maior saída recente passa X vezes a típica |
| 2 | `min_inflow_ratio` | 0.60 | Nega se as entradas cobrem menos que isto da renda declarada |
| 2 | `max_inquiries_90d` | 7 | Nega acima deste nº de consultas ao CPF em 90 dias |
| 3 | `max_commitment` | 0.25 | Parcela máxima sobre a renda efetiva |
| 3 | `amount_rule` | `full_or_deny` | `full_or_deny` ou `maximize_expected_profit` (reduz o valor) |
| 4 | `risk_cutoff` | 0.15 | Risco máximo para quem a atual aprovaria |
| 4 | `risk_cutoff_expansion` | 0.12 | Risco máximo para quem a atual negaria |
| 4 | `safety_margin` | 0 | Resultado esperado mínimo por real |
| 4 | `late_rate` | 0.20 | Chance de atraso usada na conta |
| 5 | `min_amount` | 500 | Valor mínimo |

`PolicyStep.kind` agora inclui `capacity`. Os passos dos pedidos (`DecisionStep.title`) usam os
mesmos nomes dos passos da política.

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
