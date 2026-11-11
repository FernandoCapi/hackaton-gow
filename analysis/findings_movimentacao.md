# Achados: movimentação da conta

Base: aprovados históricos maduros, n = 3.444, inadimplência 13,6% (468 inadimplentes).
Robustez: IC Wilson 95%; holdout por tempo t1 (< 2025-05-10) / t2 (depois), formato taxa/n.
"Novos x/y": x dos 2.000 novos no segmento, y aprovados pela política atual (que aprova 1.145).
Scripts: `analysis/agent_mov/` (`final.py` regenera os números; pipeline `feat.py` → `feat2.py` → `folga.py` → `cap.py`).

**Movimentação é o sinal mais forte da base.** Holdout temporal (60% antigo / 40% novo), LightGBM:
AUC 0,724 só bureau/cadastro, 0,810 só movimentação, 0,817 tudo. Tirando os achados 1 e 2 da
política atual, os aprovados maduros cairiam de 13,5% para 7,9% de calote (remove 352 de 3.308,
dos quais 59,7% deram calote).

Definições:
- **Folga mensal**: média das entradas − média das saídas (12 meses).
- **Dreno**: maior saída mensal dos últimos 3 meses ÷ mediana das saídas do próprio cliente.
- **Cheque recente**: meses com cheque especial entre os 3 anteriores ao pedido.
- **Cortado**: pedido acima de 30% da renda, aprovado com valor reduzido ao teto.

## Achados

1. **Parcela > 45% da folga mensal (ou folga negativa)**: 63,7% (n=339, IC 58,5–68,7; t1 67%/165, t2 61%/174). Concentra 46% dos inadimplentes (216/468); resto 8,1%. Sem dreno nem cheque recente: 56,1% (n=253). AUC 0,696 vs 0,687 do comprometimento sobre a renda declarada. Novos 245/95.
2. **Dreno (saída ≥ 3x a típica nos 3 meses antes)**: 81,8% (n=88, IC 72,5–88,5; t1 92%, t2 74%). Padrão: saldo crescendo 9 meses → saída de ~8x a renda num mês → 2–3 meses no cheque especial → pedido. Cheque em 2+ dos últimos 3 meses: 84,9% (n=73). Qualquer cheque nos últimos 3: 68,1% (n=119), e a atual aprova 107 deles. Novos 100/24.
3. **Cortado no teto com folga ≤ 0,6x a renda**: 88,9% (n=90, IC 80,7–93,9). Todos os cortados: 56,9% (n=218); com folga > 0,6: 32,5%. Novos 27, todos aprovados pela atual.
4. **Negados pela atual que pagam**: no piloto, negados com movimentação limpa (sem cheque recente, sem dreno, parcela ≤ 25% da folga): 7,9% (n=101, IC 4,1–14,9). Suja: 42,9% (n=35). Limpa por motivo: score ≤ 600 10,1% (n=79); restrição 4,5% (n=22); renda ≤ 2.000 0% (n=14). Novos: 607 dos 855 negados pela atual têm movimentação limpa (339 score, 242 restrição, 119 renda).
5. **Segmento bom**: parcela ≤ 25% da folga + sem cheque recente + sem dreno + entradas regulares (CV ≤ 0,36): 6,4% (n=2.351, 68% da base; resto 29%). Novos 1.300/824.
6. **Entradas irregulares (CV > 0,36)**, incremental: 18,3% (n=311). Novos 228/95.
7. **Pico de entradas recente (> 1,3x a mediana)**, incremental: 16,6% (n=277). Sinal fraco: só como componente de score.
8. **Não se sustentam** depois de controlar 1 e 2: entradas < 80% da renda (11,8%); conta ≤ 2 meses (12,9% com controle); saídas/entradas > 0,42 (7,8% com controle); queda de salário (2 casos).

## Armadilhas
1. `renda_comprovada_ratio` só separa vínculo (autônomo/empresário ~9% vs assalariado ~83%); plana dentro do vínculo. Não usar como "renda inflada".
2. `mov_meses_sem_salario` é sempre 0.
3. Cheque especial no mês mais antigo é artefato (27,9% dos clientes; 0,3% nos meses do meio). Total de meses com cheque engana; use cheque recente.
4. Saldo é acumulativo e irreal (mediana ~R$ 30 mil para renda ~R$ 4,7 mil): mede tempo de conta e dreno, não riqueza.
5. Fluxo negativo e cheque fora do mês antigo só aparecem nos 3 meses antes do pedido: padrão plantado, presente na mesma proporção nos novos.
6. `late` não tem relação com movimentação (AUC ~0,50). Não usar como alvo.
7. Razão saídas/entradas de 12 meses engana: use pico/recência.
