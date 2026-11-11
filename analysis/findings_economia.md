# Economia da política de crédito

Base: aprovados maduros (≥ 10 meses), n=3.444, calote 13,6%, atraso 20,6%.
Resultado por pedido: +15% (em dia), +5% (atraso), −60% (calote).
Ponto de equilíbrio: EV/valor = 0,15 − 0,10·P(atraso) − 0,75·P(calote) → só dá lucro com **P(calote) < 17,3%** (20% se não houvesse atraso).
Scripts: `analysis/agent_econ/` (`common.py`, `model.py`, `01_dose.py` … `09_final_new.py`); `new_recommended.parquet` tem `v_rec_final` (valor recomendado por pedido novo).

## 1. Dose-resposta

| parcela aprovada / renda declarada | n | calote | atraso | EV (% do valor) |
|---|---|---|---|---|
| ≤ 5% | 424 | 6,8% | 24,5% | +7,6% |
| 5–10% | 1.681 | 9,8% | 20,5% | +5,7% |
| 10–15% | 617 | 11,3% | 20,3% | +4,8% |
| 15–20% | 300 | 12,0% | 23,7% | +4,6% |
| 20–25% | 127 | 15,0% | 14,2% | +0,4% |
| 25–28% | 46 | 26,1% | 17,4% | −6,2% |
| 28–30% | 220 | 53,6% | 14,1% | −26,2% |
| 30–35% (piloto) | 29 | 65,5% | 27,6% | −37,1% |

- O risco dá um **salto** perto de 28–30% da renda real, não sobe aos poucos.
- **Melhor régua: parcela ÷ média de entradas da conta** (AUC 0,682 vs 0,670 renda declarada, 0,646 salário, 0,498 score). Acima de 0,30: 59% de calote; abaixo: 10%.
- Salário comprovado só vale para assalariados (autônomos/empresários: salário ≈ 9% da renda).
- Renda declarada ≈ 10% acima das entradas reais: "30% da declarada" ≈ 33% da real.
- **Limite seguro: parcela ≤ 25% de min(renda declarada, entradas).**

**Experimento natural**: a atual reduz o valor até parcela = 30% da declarada (197–215 pedidos) → calote 55–57%, EV −29%. Calote cresce com o tamanho do pedido original (49% → 69% do 1º ao 4º quartil). Mesma parcela aprovada: reduzidos 41%, valor cheio 15%. **Pedir demais é sinal de risco.** Não há dados de redução profunda (5 casos).

## 2. Política atual (histórico, n=3.308)
R$ 26,6 mi aprovados, P&L ≈ +R$ 300–319 mil (+1,1%). Reduzidos: −R$ 859 mil; demais: +R$ 1,16 mi.

| segmento perdedor | P&L |
|---|---|
| parcela/entradas > 0,30 (n=220, calote 59%) | −R$ 939k |
| saídas/entradas > 0,405 (calote 29%) | −R$ 409k |
| renda R$ 2–3 mil | −R$ 253k |
| entradas instáveis (CV > 0,31) | −R$ 213k |
| valor > R$ 10 mil | −R$ 210k |
| > 2 meses com cheque especial (n=38, calote 89%) | −R$ 186k |
| > 4 consultas em 90 dias (calote 27%) | −R$ 177k |
| prazo 6 meses (calote 24%) | −R$ 73k |

## 3. Modelo (LightGBM)
- Fora do tempo (treino até 2025-06, teste 2025-07 a 2025-11): **AUC calote 0,81**, calibração boa e levemente conservadora (14,4% previsto vs 11,7%). **AUC atraso 0,51**: tratar como constante ~20%.
- Reduzir a 60% um pedido com parcela > 30% das entradas: P(calote) 60% → 14–18% pelo modelo (extrapolação).

| simulação | atual | proposta | ganho |
|---|---|---|---|
| fora do tempo, 1.179 pedidos, grade de valor | 322k | 577k | +255k |
| fora do tempo, só aprova/nega valor cheio | 322k | 698k | +376k |
| validação cruzada 5 partes, 3.308 | 319k | 1.132k | +813k |
| regra simples sem redução | 319k | 1.448k | +1,13 mi |

Piloto negados pela atual: modelo aprova 116/136, −43k → +28k; com P(calote) < 12%: 63 pedidos, 3,2% calote, +36k.

## 4. Pedidos novos (EV pelo modelo)
| política | aprovados | volume | ganho vs atual |
|---|---|---|---|
| atual | 1.145 | R$ 8,86 mi | (EV 248k) |
| regra simples 25% | 1.049 | R$ 7,7 mi | +270k |
| modelo, só elegíveis atuais | 1.068 | R$ 7,55 mi | +388k |
| **recomendada** | **1.529** | **R$ 10,19 mi** | **+601k** |
| modelo, todos EV > 0 | 1.721 | R$ 11,24 mi | +657k |

Faixa realista: **+R$ 300k a +R$ 600k**.

## Política recomendada (rascunho)
1. Valor-base = min(solicitado, 30.000).
2. Teto de parcela: ≤ 25% de min(renda declarada, média de entradas).
3. Recusa direta: 2+ restrições; > 2 meses com cheque especial.
4. Valor: grade 0 ou 30–100% do valor-base dentro do teto, maximizando valor × EV. Na prática, valor cheio quando cabe; reduzir só se o EV continua positivo.
5. Corte: P(calote) < 15–17% para quem passa nas regras atuais; < 12% para quem a atual nega.
6. Score não é filtro.

## Ressalvas
Só há desfecho para aprovados; expansão a negados apoiada em 136 pedidos maduros do piloto. Redução profunda é extrapolação. Safras 2025T3/T4 ainda com 10–14 meses. Atraso não é previsível.
