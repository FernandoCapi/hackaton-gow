# Auditoria dos dados

Scripts: `analysis/agent_audit/` (`a0_load.py` salva as tabelas brutas; `a1`…`a17` fazem as checagens; `tmp_*.parquet` podem ser apagados).
"Maduro" aqui = ≥ 12 meses desde o pedido, salvo indicação.

## A. Regras do dicionário: nenhuma violação
- IDs únicos, um pedido por cliente; prazo sempre em {6,12,18,24,36}; valor pedido de **800** a 30.000.
- Parcelas: número = prazo, Price 3% sobre o valor aprovado (6.033/6.033), vencimentos corretos, nada pago após o corte. Maior atraso pago: 60 dias.
- `situacao_final` recalculada das parcelas bate 100%, lendo `em_atraso` como "ativo com qualquer atraso no histórico" (600 dos 1.080 não têm parcela em aberto hoje).
- Movimentação consistente: min(12, meses de conta) meses, antes do pedido.
- Bureau da API completo e merge correto.
- Política atual replicada 100%. **Piloto replicado 100%**: score > 450, renda > 1.500, restrições ≤ 1, parcela ≤ **35%** da renda.
- Anomalias pequenas: 526 contas abertas antes dos 18 anos (mínimo 12); 1.188 com bureau antes dos 18. CEP repetido não é armadilha. 46 profissões sem variação de grafia. Sem duplicatas de movimentação. **Não há coluna de nome.**

## B. Top 10 por impacto
1. **Censura define o alvo.** Nenhum calote antes de 3,9 meses; acumulado 1,6% (4m), 5,1% (6m), 10,5% (10m), 11,9% (12m), 13,8% (15m), 15,0% (18m, estabiliza). Safras: 2024T4 15,2% … 2026T3 0%. `maduro ≥ 10` capta ~75% dos calotes. Usar ≥ 12 (n=2.832) ou ≥ 15 (n=2.129), ou alvo "calote até a parcela 8". Nunca usar data como feature.
2. **Saídas/entradas é bimodal** (≤ 0,5 ou > 0,9, nada entre). Segmento > 0,9: **91% de calote** (61/67 maduros), 490 no histórico, **97 nos novos**; a atual aprova 32% deles. Negar com saídas/entradas > 0,7.
3. **Score não discrimina.** Decis planos (12–16%). Piloto, aprovados limpos: score ≤ 600 6,0% (n=217) vs > 600 5,5% (n=638); score ≤ 500: 1,4% (n=74). Corte em 600 nega ~24% dos pedidos sem ganho de risco. Relaxar para ~450.
4. **Alvo**: `em_atraso` não é bom (backtest com corte em 31/03/2026: em_atraso terminou 20% inadimplente, 32% se tinha parcela aberta; em_dia 1,8%). MOB ≥ 18: atrasou uma das 6 primeiras → 43,6% calote vs 0,7%. `quitado_com_atraso` = bom com margem baixa.
5. **Comprometimento** (AUC 0,66): ≤ 5% 6,5%; 10–15% 11%; 20–25% 16%; 25–30% 29%; 30–35% 49%; > 35% 58%. Trava de 20–25% sobre a renda efetiva; usar comprometimento total.
6. **Renda declarada inflada**: entradas/renda < 0,6 em 396 clientes (322 hist., 74 novos). Ex.: P-02672 manicure declara 14.350 com entradas de 1.279. Calote 40% nos aprovados (n=55), 71–75% nos maduros. Renda efetiva = min(declarada, entradas).
7. **Vazamento** no `base.parquet`: `max_atraso` AUC 1,000; também `n_vencidas`, `n_parcelas`, `valor_parcela_real`, `valor_aprovado`, `atual_valor`, `decisao`, `politica_aplicada`, `situacao_final`, `late`, `meses_desde_pedido`, `maduro`, `data_pedido`. Usar lista explícita de features permitidas.
8. **Piloto é aleatório** (diferença padronizada < 0,1; GBM prevendo piloto AUC 0,526). Faixas relaxadas: 1 restrição 19% calote / 48% atraso (n=99); comprometimento > 30% 60% (n=47); renda 1.500–2.000 12%; score ≤ 600 sem piora. Só 6–12 meses de vida.
9. **Conta ≤ 3 meses**: 22,5% (n=111); médias de movimentação instáveis.
10. **Seleção e drift**: sem dados para restrição ≥ 2 nem score < 450 (manter negação). Drift desprezível (KS < 0,07; elegibilidade 56,1% vs 57,2%).

Outros: gênero não informado 16% (n pequeno, não usar); viúvo e > 70 anos confundidos com aposentadoria; nenhuma profissão com 0%/100%.

## Verificação cruzada (agente principal, maduros ≥ 12m, n=2.832)
- entradas/renda < 0,6: 71% calote (n=14); 0,6–0,8: 17,6% (n=205); ≥ 0,8: 13,1%.
- saídas/entradas > 0,9: 91% (n=67); ≤ 0,5: 11,8%. Nenhum valor entre 0,5 e 0,9.
- Novos: 74 com renda inflada, 97 com saídas > 0,9, nenhum nos dois.
