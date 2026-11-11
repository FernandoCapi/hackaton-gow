# Plano — Desafio Fortuna Crédito (Hackathon GOW 11/11/2026)

## Contexto

O material das 8h revelou o desafio:
**propor uma política de aprovação e de valor de crédito pessoal melhor que a atual** da
Fortuna Crédito e aplicá-la a 2.000 pedidos novos.

- **Política atual (referência):** score > 600, renda > R$ 2.000, zero restrições, parcela
  Price (3% a.m.) ≤ 30% da renda declarada. Teto R$ 30 mil, mínimo R$ 500.
- **Banco** `fortuna_hackathon.dump` (PG16), schema `hackathon`: `clientes`, `pedidos`
  (10 mil histórico out/24–set/26 + 2 mil novos out/26), `movimentacao_mensal` (12 meses
  antes do pedido), `bureau` (só histórico), `parcelas` (só aprovados do histórico).
  Data de corte 30/09/2026. Parte dos aprovados vem do **piloto**, com critérios mais
  flexíveis: são os únicos exemplos de "quem a política atual negaria, mas pagou ou não".
- **Bureau dos novos:** API `GET <BUREAU_URL>/v1/bureau/{id_cliente}`,
  Bearer token do time, com 503 e lentidão de propósito (conta em qualidade técnica).
- **Entrega:** `<time>_final.csv` (`id_pedido,decisao,valor_aprovado`, UTF-8, `APROVADO`/`NEGADO`,
  2 casas, gerado por código) + painel (padrões + política em passos) + pitch de 5 min
  + código com README (opcional, conta a favor).
- **Nota:** 40% ganho em R$ sobre a política atual (automático), 25% padrões, 15% pitch,
  10% painel, 10% qualidade técnica.

### A conta que decide tudo
Por pedido aprovado: **+15%** do valor se paga em dia, **+5%** com atraso, **−60%** se não paga.
Valor esperado por real emprestado = `0,15·P(em dia) + 0,05·P(atraso) − 0,60·P(calote)`.
Sem atraso, só compensa aprovar com **P(calote) < 20%**. O desfecho depende do valor
aprovado, então **reduzir o valor** é uma alavanca (parcela/renda menor → menos calote).
Política ótima = para cada pedido, escolher o valor (0 ou 500…solicitado) que maximiza
`valor × EV(valor)`.

## Decisões já tomadas (registrar em `docs/decisoes.md`)

| Tema | Decisão |
|---|---|
| Time | **selic** → arquivo `selic_final.csv`, `TEAM_ID=selic` no `.env` |
| Registro | `docs/desafio.md` = **resumo** das regras e da pontuação, sem URL/token do bureau; `docs/decisoes.md` = log datado (decisão + porquê + fonte: manual, cliente, dados); PDFs e dump fora do repo; `docs/plano.md` = este plano |
| Git | **Branch por frente** (`feat/data-model`, `feat/bureau-decide`, `feat/dashboard`), merges pequenos na `main`, que sempre roda |
| Risco | **Decidir depois dos dados**: primeiro checar a calibração do modelo no holdout; depois escolher entre maximizar R$ esperado e margem de segurança. O corte vira parâmetro em `config.py` e slider no painel |

## Estado do repo

Esqueleto genérico ainda configurado para o churn de ensaio: `config.py` (TARGET=churned),
`sql/dataset.sql` (customers/orders), `src/train.py` (LightGBM binário + SHAP nativo),
`src/explain.py`, `app.py` (painel genérico de risco), `scripts/restore_db.py` (já aceita
`.dump`), `docker-compose.yml` (postgres:18 — restaura dump PG16 sem problema).
Container parado, sem `.venv` nesta worktree, `docs/desafio.md` vazio.
Reaproveitável: `src/db.py`, `restore_db.py`, partes do `train.py` (`contributions`,
`factor_profiles`, `fit`), estrutura do `app.py` e o fluxo `/explicar`.

## Passos (em ordem de impacto na nota)

### 0. Setup (≤ 20 min, todos)
1. `python -m venv .venv` + `pip install -r requirements.txt` (+ `httpx` ou `requests`).
2. `docker compose up -d --wait`; `python scripts/restore_db.py <pasta do material>/fortuna_hackathon.dump --db fortuna`;
   conferir `SELECT tipo_base, count(*) FROM hackathon.pedidos GROUP BY 1` = 10000 / 2000.
3. `.env` (local, já no `.gitignore`, nunca commitado): `BUREAU_URL`, `BUREAU_TOKEN`
   (token do time, recebido em mensagem privada), `TEAM_ID=selic`; `.env.example` ganha as
   chaves vazias. Testar `GET /health` e uma consulta a um `id_cliente` novo antes de
   rodar o lote. O token nunca aparece em log, docs, painel ou commit.
4. Registro (commit `docs:` na `main` antes de abrir as branches):
   - `docs/desafio.md`: resumo das regras — política atual, tabelas, alvo, conta de
     pontuação (+15/+5/−60), formato do CSV, critérios e pesos, horários. Sem URL nem token.
   - Seção "Desafio" do `CLAUDE.md` atualizada com o mesmo resumo curto (o que o `/kickoff`
     faria, mas sem a transcrição integral).
   - `docs/decisoes.md` com as 4 decisões acima e espaço para as respostas do cliente.
   - `docs/plano.md` com este plano.
5. Dividir papéis e abrir as branches: dados/modelo, bureau+CSV, painel; pitch acompanha.

### 1. Bureau dos novos (bureau+CSV, em paralelo — começar já)
`src/bureau.py`: busca os 2.000 `id_cliente` novos, threads (~16), timeout ~10 s, retry com
backoff exponencial em 503/timeout, cache em `data/bureau_novos.parquet` (gitignored;
resposta é determinística, então nunca recalcula), log de tentativas/falhas, relatório final
(quantos 200, quantos ainda faltam). Re-executável até zerar faltantes.
Fallback: pedido sem bureau após N tentativas → decisão conservadora (nega, ou só com
regras de movimentação) — documentar.

### 2. Alvo e dataset (dados/modelo)
- `sql/dataset.sql` → uma linha por pedido (histórico + novos), juntando clientes,
  pedidos, bureau e agregados de `movimentacao_mensal`:
  médias/mín de entradas, `entradas_salario` vs `renda_declarada` (renda comprovada ×
  declarada), meses com salário, `dias_cheque_especial` (soma, meses com uso),
  `saldo_minimo` < 0, saídas/entradas, tendência dos últimos 3 vs 12 meses, nº de meses
  de conta; idade, tempo de conta; comprometimento `(parcela + parcelas_outras)/renda`.
- **Alvo** a partir de `situacao_final`/`parcelas`: calote = `inadimplente`;
  atraso = `quitado_com_atraso`/`em_atraso`; em dia = `quitado_em_dia`/`em_dia`.
  **Censura:** contrato recente com 1–2 parcelas vencidas ainda não mostrou calote.
  Olhar taxa de calote por safra (mês do pedido) e treinar só com safras maduras
  (ex.: ≥ 6 parcelas vencidas) ou ponderar por exposição. Validar por tempo.
- Vazamento: `decisao`, `valor_aprovado`, `politica_aplicada`, `situacao_final`, `parcelas`
  nunca entram como feature. Valor/parcela entram como **valor solicitado** no treino e
  como **valor candidato** na decisão.
- `config.py`: TARGET, ID=`id_pedido`, DATE_COLUMN=`data_pedido`, DROP_COLUMNS.

### 3. Modelo de risco (dados/modelo)
Adaptar `src/train.py`: LightGBM prevendo P(calote) (e, se der tempo, P(atraso) — modelo
multiclasse ou dois binários), treinado só em aprovados (atual + piloto), validação
temporal. Checar calibração (as probabilidades entram em R$). Comparar AUC com o "modelo"
da política atual (regra score>600) para mostrar o ganho.

### 4. Política e simulação (dados/modelo + bureau+CSV)
`src/policy.py`:
- `current_policy(row)` — regra da Fortuna (reproduz a referência da pontuação).
- `proposed_policy(row)` — passos legíveis: (1) filtros duros que os dados sustentarem
  (ex.: restrição ativa), (2) risco do modelo acima de X nega, (3) valor = o que maximiza
  `valor × EV(valor)` re-pontuando o modelo com a parcela do valor candidato (grade de
  100% a 30% do solicitado, mín R$ 500), (4) teto: ≤ solicitado e ≤ R$ 30 mil.
  Corte de risco e margem de segurança são parâmetros (`config.py`), escolhidos depois
  da curva de calibração e da simulação; a escolha vai para `docs/decisoes.md`.
- `simulate()` no histórico (holdout temporal): R$ da política atual vs proposta nos
  aprovados com desfecho conhecido, inclusive os do piloto. Esse é o número do pitch.

`src/decide.py`: lê novos + bureau em cache → aplica a política → grava
`output/<TEAM_ID>_final.csv` validando o formato (cabeçalho exato, 2.000 linhas únicas,
maiúsculas, 2 casas, 0.00 nos negados). Um comando gera do zero.

### 5. Padrões (25% — dados/modelo + IA)
`src/patterns.py`: gera frases no formato exigido — "Clientes com X têm inadimplência de
N%, contra M% da média. Afeta K clientes." — a partir de SHAP + perfis por faixa e de
combinações (árvore rasa sobre as features / interações de 2 variáveis), com foco em:
onde a política atual erra (negaria e pagou — piloto; aprovou e caloteou), renda declarada
× salário real, cheque especial, consultas recentes, tipo de vínculo. LLM (Claude via
`/explicar` ou API) recebe **só agregados** e redige/valida a explicação — isso cumpre
"IA na descoberta", não só no código.

### 6. Painel (`app.py`, painel)
Reescrever para o analista de risco:
1. **Padrões encontrados** (frases + gráfico por grupo).
2. **Política proposta** em passos numerados, com os parâmetros atuais.
3. **Experimentação:** sliders de corte de risco e redução de valor → resultado simulado em
   R$ vs política atual, aprovados/negados (esta é a "dor": testar hipótese em minutos).
4. **Consulta por `id_pedido`**: decisão, valor e motivos — para a demo ao vivo da banca.
5. Nota "a IA sugere, o analista decide".

### 7. Checkpoint e entrega
- **Até 14h15:** mandar uma versão do CSV no Teams (mesmo que provisória) para validar
  formato. Mandar antes também, sempre que mudar.
- 15h00 em diante: só correções. 15h30: `<time>_final.csv` + zip/link do repo com README
  ("como gerar o arquivo do zero").
- `/pitch 5` → `docs/pitch.md`: onde a IA entra, 3 padrões, política, o que mudou após o
  checkpoint, como o analista valida.

## Perguntas para a janela de dúvidas com o cliente
1. O desfecho dos novos pedidos é de contrato completo? "Pagou com atraso" vs "não pagou"
   segue a mesma regra de 90 dias de `situacao_final`?
2. Na política atual, quando aprova, o valor aprovado é sempre o solicitado? O limite de 30%
   considera `parcelas_outras_instituicoes`?
3. Como o desfecho reage a um valor menor que o solicitado (o manual diz que reage — é
   pela parcela/renda)?
4. O prazo pode ser alterado por nós, ou só o valor?
5. Pedidos do piloto foram sorteados ou escolhidos? (viés na amostra)

## Arquivos críticos
- Alterar: `config.py`, `sql/dataset.sql`, `src/train.py`, `app.py`, `requirements.txt`,
  `.env.example`, `README.md`, `CLAUDE.md` (via `/kickoff`), `.gitignore` (`output/`).
- Criar: `src/bureau.py`, `src/policy.py`, `src/decide.py`, `src/patterns.py`.
- Reusar: `src/db.py`, `scripts/restore_db.py`, `contributions`/`factor_profiles` de
  `src/train.py`, fluxo `/explicar` de `src/explain.py`.

## Verificação
- Restore: contagem 10000/2000.
- Bureau: 2.000/2.000 em cache, rodar duas vezes sem nova chamada à API.
- Política atual reproduzida no histórico bate com `decisao` nos pedidos `politica_aplicada='atual'`.
- `simulate()` mostra ganho > 0 em R$ no holdout temporal; métrica boa demais → checar vazamento.
- `python -m src.decide` gera o CSV; validador interno passa; mandar ao Teams para validação oficial.
- `streamlit run app.py`: as 4 seções abrem e a consulta por `id_pedido` funciona.
