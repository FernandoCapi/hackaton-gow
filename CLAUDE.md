# hackaton-gow

Solução do time para o hackathon interno da GOW (11/11/2026). O cliente fictício entrega um
banco PostgreSQL e a IA precisa encontrar padrões nos dados e apoiar uma decisão de negócio.

## Desafio

**Fortuna Crédito** (time **selic**). Regras completas em `docs/desafio.md`, decisões em
`docs/decisoes.md`, plano em `docs/plano.md`.

- **Decisão:** para cada um dos 2.000 pedidos novos, aprovar ou negar e com qual valor
  (≤ solicitado, ≤ R$ 30 mil, ≥ R$ 500). A IA sugere, o analista de risco decide.
- **Referência:** política atual — score > 600, renda > R$ 2.000, 0 restrições, parcela
  (Price, 3% a.m.) ≤ 30% da renda; acima disso reduz o valor ao que cabe.
- **Métrica (40%):** por aprovado, +15% do valor se paga em dia, +5% com atraso, −60% se não
  paga; ganho = nosso resultado − política atual. Sem atraso, só compensa aprovar com
  chance de calote < 20%. O desfecho piora quando o valor aprovado é alto demais.
- **Entrega:** `selic_final.csv` (`id_pedido,decisao,valor_aprovado`, gerado por código) até
  15h30 no Teams; painel (padrões + política em passos); pitch de 5 min; código com README.
- **Banca (60%):** padrões descobertos pela IA 25%, pitch 15%, painel 10%, qualidade técnica
  10% (inclui tratar as falhas do bureau).
- **Restrições:** IA precisa participar da descoberta e da decisão; sem dados externos;
  bureau dos novos só pela API (token no `.env`).

## Como a nota é formada

- 40% objetivo: ganho em reais sobre a política atual, calculado do arquivo de decisões.
- 60% banca: padrões explicados corretamente, pitch, painel para o analista, qualidade técnica.

Na dúvida entre duas tarefas, priorize a que move uma dessas duas partes.

## Relógio

| Horário | Marco |
|---|---|
| 08h00 | Kickoff |
| 14h15 | Checkpoint com pontuação parcial e mentor |
| 15h30 | Code freeze, sem tolerância |
| 15h45 | Pitches |

## Comandos

```
docker compose up -d --wait                  # Postgres em localhost:5432 (hackaton/hackaton)
python scripts/restore_db.py <dump> --db fortuna  # restaura o desafio no banco fortuna
python -m src.bureau                         # bureau dos pedidos novos -> data/ (re-rodar até 0 faltando)
python -m src.profile --save                 # perfil do schema em docs/perfil-banco.md
python -m src.train                          # modelo baseline + artifacts/
python -m src.explain                        # explicação via API (ANTHROPIC_API_KEY); sem chave, gera o prompt para /explicar
streamlit run app.py                         # painel (legado; o painel novo é o Next em web/)
uvicorn src.api:app --reload --port 8000     # API do motor para o front (docs em /docs)
python -m src.api --export-openapi           # atualiza contracts/openapi.json após mudar src/schemas.py
python -m pytest -q                          # testes (inclui o contrato da API)
```

Use o Python da `.venv` (`.venv\Scripts\python.exe` no Windows, `.venv/bin/python` no Mac/Linux).
`psql` e `pg_restore` existem só dentro do container: `docker compose exec -T db psql -U hackaton -d hackaton`.

## Estrutura

- `config.py` — único lugar que nomeia alvo, id, data, tipo de tarefa e colunas descartadas.
- `sql/dataset.sql` — query que devolve uma linha por entidade a pontuar, com o alvo.
- `src/train.py` — LightGBM; grava métricas, previsões por id e fatores em `artifacts/`.
- `src/explain.py` — transforma métricas e fatores agregados em texto para o cliente.
- `app.py` — painel Streamlit: o que está acontecendo, por quê, o que fazer.
- `src/schemas.py` — contrato da API (fonte da verdade); `src/api.py` — rotas FastAPI `/v1`;
  `src/service.py` — fachada que as rotas chamam (exemplos em `contracts/fixtures/` até o
  motor real assumir cada seção). Guia para o front: `docs/api.md`.
- `contracts/` — `openapi.json` (gera os tipos TypeScript do front) e `fixtures/` (exemplos
  inventados, sem dados do banco).
- `web/` — painel em Next (front), consome a API por proxy `/api/*` → `localhost:8000/v1/*`.
- `src/bureau.py` — bureau dos pedidos novos com novas tentativas e cache em `data/`.
- `docs/` — briefing, perfil do banco, dicionário de dados e roteiro do pitch.

O dataset de exemplo (churn sintético, `scripts/load_sample.py`) serve só de ensaio.

## Regras

- O repositório é público: nunca commitar dados, dumps, `artifacts/` nem `.env`. Linhas de
  clientes não vão para a API de LLM; só agregados.
- Para adaptar ao desafio, altere `config.py` e `sql/dataset.sql` antes de mexer no código.
- Vazamento: toda coluna do dataset precisa ser conhecida antes do resultado acontecer. Uma
  métrica boa demais é suspeita de vazamento até prova em contrário. Havendo data, valide
  por tempo (`DATE_COLUMN`).
- Linhas com alvo nulo são tratadas como "a pontuar": recebem score, mas não entram no treino.
- Previsão sozinha não é entrega: cada resultado vira uma recomendação ("quem abordar, em que
  ordem, por quê"), de preferência com o impacto estimado em reais.
- Texto para o cliente e para a banca em português simples, sem jargão de ciência de dados.
- Cada pessoa usa o próprio acesso à IA (assinatura do Claude Code ou chave de API no `.env`
  local). Nada de credencial compartilhada ou commitada; o fluxo funciona sem chave pelo `/explicar`.
- Commits no padrão Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`...), em inglês,
  sem linha `Co-Authored-By`.
- A `main` precisa sempre rodar. Commits pequenos; mudança arriscada só depois de commitar a
  versão que funciona. Depois das 15h, apenas correções.
- Código e nomes em inglês; textos de interface e documentos em português.
