# hackaton-gow

Solução do time para o hackathon interno da GOW (11/11/2026). O cliente fictício entrega um
banco PostgreSQL e a IA precisa encontrar padrões nos dados e apoiar uma decisão de negócio.

## Desafio

**Pendente — revelado às 8h.** Depois do kickoff, rode `/kickoff` com o briefing: ele grava
`docs/desafio.md` e substitui esta seção por decisão, métrica, entrega e restrições.

## Como a nota é formada

- Uma parte objetiva, em números (métrica a confirmar no kickoff).
- Uma parte da banca, no pitch: entendimento do problema, explicação em linguagem simples do
  que a IA descobriu, painel que o cliente usaria para decidir, defesa das escolhas.

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
python scripts/restore_db.py dumps/<arquivo> # restaura o banco do desafio (recria o banco)
python -m src.profile --save                 # perfil do schema em docs/perfil-banco.md
python -m src.train                          # modelo baseline + artifacts/
python -m src.explain                        # explicação via API (ANTHROPIC_API_KEY); sem chave, gera o prompt para /explicar
streamlit run app.py                         # painel
```

Use o Python da `.venv` (`.venv\Scripts\python.exe` no Windows, `.venv/bin/python` no Mac/Linux).
`psql` e `pg_restore` existem só dentro do container: `docker compose exec -T db psql -U hackaton -d hackaton`.

## Estrutura

- `config.py` — único lugar que nomeia alvo, id, data, tipo de tarefa e colunas descartadas.
- `sql/dataset.sql` — query que devolve uma linha por entidade a pontuar, com o alvo.
- `src/train.py` — LightGBM; grava métricas, previsões por id e fatores em `artifacts/`.
- `src/explain.py` — transforma métricas e fatores agregados em texto para o cliente.
- `app.py` — painel Streamlit: o que está acontecendo, por quê, o que fazer.
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
