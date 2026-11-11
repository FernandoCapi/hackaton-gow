# Checklist do time selic

Ordem pensada pela nota: 40% ganho em R$ (CSV), 25% padrões, 15% pitch, 10% painel, 10% técnica.

## Setup (cada pessoa)
- [ ] `docker compose up -d --wait` e restore no banco `fortuna` (10000 / 2000)
- [ ] `.venv` + `pip install -r requirements.txt` (+ `pyarrow`)
- [ ] `.env` com `BUREAU_URL`, `BUREAU_TOKEN`, `TEAM_ID=selic` (nunca commitar)
- [ ] `python -m src.bureau` → 2000/2000 em cache
- [ ] `python -m analysis.build_base` → `data/base.parquet`

## Manhã: entender os dados (até ~11h)
- [x] Política atual reproduzida 100% (decisão e valor)
- [x] Corte de maturidade: só safras com ≥ 10 meses para medir calote
- [x] Auditoria de pegadinhas (`analysis/findings_auditoria.md`)
- [x] Padrões de movimentação (`analysis/findings_movimentacao.md`)
- [x] Padrões de bureau e perfil (`analysis/findings_bureau_perfil.md`)
- [x] Economia: efeito do valor, ponto de equilíbrio (`analysis/findings_economia.md`)
- [x] Consolidado com padrões e rascunho da política (`docs/padroes.md`)
- [ ] Decidir: maturidade do treino (12 ou 15 meses), cortes de risco, reduzir valor ou não
- [ ] Levar as perguntas de `docs/decisoes.md` na janela de dúvidas do cliente

## Modelo e política (11h–13h30)
- [ ] `sql/dataset.sql` + `config.py` com o alvo (calote) e as features escolhidas
- [ ] Modelo de P(calote) e P(atraso), validação por tempo, calibração conferida
- [ ] `src/policy.py`: `current_policy` + `proposed_policy` em passos legíveis
- [ ] `simulate()` no histórico: R$ proposta vs atual (número do pitch)
- [ ] `src/decide.py` → `output/selic_final.csv` com validação de formato

## Checkpoint 14h15
- [ ] Enviar CSV provisório no Teams e ler o relatório
- [ ] Conversa com o mentor: anotar o que mudar em `docs/decisoes.md`

## Painel (paralelo, a partir de ~12h)
- [ ] Parte 1: padrões no formato "Clientes com X têm inadimplência de N%, contra M% da média. Afeta K clientes."
- [ ] Parte 2: política em passos numerados
- [ ] Simulador (sliders de corte e valor) e consulta por `id_pedido` para a demo

## Fechamento (até 15h30, sem tolerância)
- [ ] CSV final gerado por código: `selic_final.csv` no Teams
- [ ] README com o comando que gera o arquivo do zero; link do repo/zip
- [ ] `/pitch`: onde a IA entra, 3 padrões, política, o que mudou pós-checkpoint, como o analista valida
- [ ] Ensaiar a demo ao vivo (decisão de pedidos específicos)
