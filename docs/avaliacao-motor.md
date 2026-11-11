# Avaliação do motor de decisão

Gerado por `python -m src.evaluate` com os parâmetros padrão. Só números agregados.
Casos individuais para conferência: `artifacts/casos.md` (local, fora do git).

## 1. A régua está certa?

- A política atual, reescrita em código, reproduz **100,0%** das 8.737 decisões
  históricas tomadas por ela (diferença máxima de valor: R$ 0,11, arredondamento).
- O pontuador aplica a regra do manual: o exemplo de 4 pedidos dá **−R$ 1.200** (manual: −R$ 1.200).
- Como cada desfecho histórico vale na simulação (por real aprovado):
  em dia 15%, quitado com atraso 5%,
  inadimplente −60%; **em atraso** vale −11,2%, porque
  20–32% desses contratos ainda terminam em calote (auditoria).

## 2. O modelo enxerga risco?

Treinado em 2.832 contratos aprovados com pelo menos 12 meses de vida
(calote médio 13,7%). Teste honesto: treino com pedidos anteriores a jul/2025 e teste em
703 pedidos de 2025-07 a 2025-09, que o modelo nunca viu.

| Medida (0,5 = sorteio, 1 = perfeito) | Valor |
|---|---|
| Modelo, pedidos nunca vistos | **0,80** |
| Score do bureau (régua da política atual) | 0,48 |
| Modelo em validação cruzada por blocos de meses | 0,76 |
| Modelo treinado com o alvo embaralhado (teste de vazamento) | 0,47 (de 0,40 a 0,66) |

Calibração no teste (o risco previsto bate com o observado?):

| Faixa prevista | Pedidos | Previsto | Observado |
|---|---|---|---|
| 0%–5% | 100 | 3,8% | 2,0% |
| 5%–10% | 342 | 7,3% | 5,0% |
| 10%–15% | 123 | 12,0% | 6,5% |
| 15%–20% | 37 | 17,0% | 18,9% |
| 20%–30% | 59 | 23,9% | 16,9% |
| 30%–50% | 10 | 35,6% | 30,0% |
| 50%–100% | 32 | 87,2% | 84,4% |

Leitura: o modelo prevê um pouco **acima** do observado entre 5% e 15%. É esperado: os contratos do teste
têm só 12 a 15 meses de vida, e o calote ainda cresce até ~18 meses. O modelo foi treinado com contratos
mais longos e estima o risco do contrato inteiro, que é o que a nota mede. Na faixa de decisão (15–20%) o
previsto e o observado ficam próximos.

## 3. Quanto ganhamos e de onde vem?

**Histórico (desfecho real)** — 2.832 contratos maduros, cada um avaliado por um
modelo que não o viu no treino:

| | Política atual | Proposta |
|---|---|---|
| Aprovados | 2.832 | 2.291 |
| Resultado (+15% / +5% / −60%) | −R$ 229.820 | R$ 884.754 |
| **Ganho** | | **R$ 1.114.574** |

A proposta evitaria 221 calotes que a política atual aprovou.

Por faixa de risco previsto:

| Risco previsto | Contratos | Calote observado | Atual | Proposta |
|---|---|---|---|---|
| 0–5% | 665 | 6,6% | R$ 246.869 | R$ 249.089 |
| 5–10% | 1300 | 6,9% | R$ 567.886 | R$ 558.076 |
| 10–15% | 371 | 12,1% | R$ 68.086 | R$ 77.589 |
| 15–20% | 152 | 15,8% | R$ 2.567 | R$ 0 |
| 20–30% | 87 | 19,5% | −R$ 32.030 | R$ 0 |
| 30–100% | 257 | 65,4% | −R$ 1.083.198 | R$ 0 |

**Pedidos novos (estimado pelo modelo)** — a melhor previsão da nota de 40%:

| | Política atual | Proposta |
|---|---|---|
| Aprovados | 1.145 | 1.232 |
| Resultado esperado | R$ 150.021 | R$ 630.950 |
| **Ganho esperado** | | **R$ 480.928** |

493 dos 2.000 pedidos têm decisão ou valor diferente da política atual.

**Quanto vale cada passo** (quanto o resultado mudaria sem ele; negativo = o passo protege dinheiro):

| Passo | Novos negados nele | Histórico sem o passo | Novos sem o passo |
|---|---|---|---|
| Quem pode ser aprovado | 422 | R$ 0 | R$ 71.743 |
| Nega com sinais de aperto na conta | 49 | −R$ 11.272 | R$ 70 |
| Nega quando a parcela não cabe | 134 | R$ 9.360 | R$ 8.252 |
| Nega pelo risco estimado pela IA | 163 | −R$ 16.079 | R$ 10.493 |

Como ler: no histórico, o desfecho é real; nos pedidos novos, é o modelo julgando a si mesmo. Por isso,
desligar o passo de risco "ganha" nos novos (o modelo acha que todo pedido com lucro esperado positivo
vale a pena) e perde no histórico (na vida real, esses pedidos dão prejuízo). Os filtros de aperto valem
pouco em R$ porque o modelo já enxerga esses sinais; ficam porque explicam a decisão ao analista.

## 4. O resultado é estável?

Risco máximo de calote (para quem a política atual aprovaria):

| Valor | Ganho no histórico | Aprovados (novos) | Ganho esperado (novos) |
|---|---|---|---|
| 8% | R$ 906.282 | 805 | R$ 317.444 |
| 10% | R$ 1.036.985 | 1041 | R$ 421.024 |
| 12% | R$ 1.117.182 | 1167 | R$ 463.516 |
| 15% | R$ 1.114.574 | 1232 | R$ 480.928 |
| 17% | R$ 1.101.730 | 1264 | R$ 483.864 |
| 20% | R$ 1.098.495 | 1270 | R$ 483.896 |
| 25% | R$ 1.098.495 | 1270 | R$ 483.896 |

Teto da parcela sobre a renda efetiva:

| Valor | Ganho no histórico | Aprovados (novos) | Ganho esperado (novos) |
|---|---|---|---|
| 15% | R$ 895.737 | 1063 | R$ 387.614 |
| 20% | R$ 1.040.776 | 1182 | R$ 449.430 |
| 25% | R$ 1.114.574 | 1232 | R$ 480.928 |
| 30% | R$ 1.123.934 | 1242 | R$ 489.181 |
| 35% | R$ 1.123.934 | 1242 | R$ 489.181 |

Risco máximo para quem a política atual negaria (0% = não expandir):

| Valor | Aprovados (novos) | Ganho esperado (novos) |
|---|---|---|
| 0% | 942 | R$ 363.519 |
| 8% | 1105 | R$ 435.410 |
| 10% | 1188 | R$ 467.154 |
| 12% | 1232 | R$ 480.928 |
| 15% | 1263 | R$ 487.967 |

Leitura: o ganho deve variar pouco perto dos valores escolhidos. Se o melhor resultado estivesse num
extremo da tabela, a régua estaria errada.

## 5. Negar ou reduzir o valor?

| Regra | Ganho no histórico | Aprovados (novos) | Volume (novos) | Ganho esperado (novos) |
|---|---|---|---|---|
| Valor pedido ou nega | R$ 1.114.574 | 1232 | R$ 8.516.200 | R$ 480.928 |
| Reduzir até caber | R$ 796.543 | 1412 | R$ 9.547.260 | R$ 549.785 |

Ressalva: no histórico, quem teve o valor reduzido ficou com parcela em 30% exatos da renda e deu 56% de
calote; reduções mais fundas quase não existem (5 casos). O ganho de "reduzir" vem do modelo
extrapolando. Por isso o padrão é "valor pedido ou nega" até o cliente confirmar como o desfecho reage
a um valor menor.

## 6. A expansão para quem a política atual nega se sustenta?

O piloto (sorteado, out/2025 a mar/2026) é a única evidência sobre quem a política atual nega. Seus
1.126 contratos têm de 6 a 12 meses de vida:
**o calote observado ainda é parcial** (cerca de metade a três quartos do final). O modelo nunca viu
esses contratos; mesmo assim separa bons e maus com 0,81.

| Grupo do piloto | Contratos | Calote até agora |
|---|---|---|
| Atual negaria, proposta aprova | 203 | 3,9% |
| Atual negaria, proposta nega | 224 | 23,2% |
| Atual aprovaria, proposta aprova | 577 | 4,5% |
| Atual aprovaria, proposta nega | 122 | 34,4% |

Leitura: o grupo que a proposta aprova e a atual negaria deve ter calote parecido ou menor que o
grupo que as duas aprovam. Clientes com restrição ativa ficam negados por padrão: o modelo foi
treinado só com contratos sem restrição e o piloto mostrou 19–23% de calote nesse grupo.

## 7. Há vazamento?

- O modelo usa só esta lista fechada, toda conhecida no dia do pedido: `prazo_meses`, `valor_solicitado`, `score`, `restricoes_ativas`, `consultas_90_dias`, `meses_historico_bureau`, `outras_sobre_renda`, `meses_conta`, `mov_meses`, `entradas_sobre_renda`, `saidas_sobre_entradas`, `entradas_cv`, `pico_entradas`, `dreno`, `cheque_recente_meses`, `pedido_acima_30`, `parcela_sobre_renda_efetiva`, `parcela_sobre_folga`, `comprometimento_total`
  e `tipo_vinculo`. O extrato termina no mês anterior ao pedido.
- Ficam de fora: decisão, valor aprovado, política aplicada, situação final, parcelas (vazam o desfecho) e
  gênero, CEP, estado civil, idade e profissão (atributos sensíveis ou sem sinal).
- Com o alvo embaralhado o modelo cai para ~0,5 (seção 2): não há atalho escondido nos dados.
- Nenhuma variável sozinha passa de 0,76; a mais forte é a parcela sobre a sobra do mês.

## 8. Padrões que o painel mostra

Os mesmos que a API serve em `/v1/patterns`, calculados por `src/patterns.py` com as
definições do motor. Base: contratos com 12+ meses, ou o piloto quando indicado.

**Onde a política atual aprova e perde dinheiro (ou onde ela acerta)**

- Clientes com saídas acima de 90% do que entra na conta têm inadimplência de 91%, contra 13,7% da média. Afeta 67 clientes. Pedidos novos no grupo: 97. Passo da política: Nega com sinais de aperto na conta.
- Clientes com cheque especial em 2 ou mais dos 3 meses antes do pedido têm inadimplência de 91%, contra 13,7% da média. Afeta 56 clientes. Pedidos novos no grupo: 90. Passo da política: Nega com sinais de aperto na conta.
  - Ressalva: Conta só os 3 meses antes do pedido: o cheque especial do mês mais antigo do extrato é artefato dos dados.
- Clientes com a conta esvaziada antes do pedido (uma saída 3 vezes maior que a típica) têm inadimplência de 87%, contra 13,7% da média. Afeta 70 clientes. Pedidos novos no grupo: 100. Passo da política: Nega com sinais de aperto na conta.
- Clientes com 8 ou mais consultas ao CPF em 90 dias têm inadimplência de 91%, contra 13,7% da média. Afeta 22 clientes. Pedidos novos no grupo: 38. Passo da política: Nega com sinais de aperto na conta.
  - Ressalva: Amostra pequena (22 contratos): usar como sinal, não como prova.
- Clientes com entradas na conta abaixo de 60% da renda declarada têm inadimplência de 71%, contra 13,7% da média. Afeta 14 clientes. Pedidos novos no grupo: 74. Passo da política: Nega com sinais de aperto na conta.
  - Ressalva: Amostra pequena (14 contratos): usar como sinal, não como prova. Usa o total de entradas, não o salário: autônomos e empresários quase não recebem "salário" na conta.
- Clientes com parcela acima de 45% da sobra do mês (entradas menos saídas) têm inadimplência de 65%, contra 13,7% da média. Afeta 265 clientes. Pedidos novos no grupo: 245. Passo da política: Nega pelo risco estimado pela IA.
  - Ressalva: Medido no valor pedido. É o sinal mais forte do modelo de risco.
- Clientes com pedido acima da capacidade, aprovado com valor cortado pela regra dos 30% têm inadimplência de 56%, contra 13,7% da média. Afeta 177 clientes. Pedidos novos no grupo: 61. Passo da política: Nega quando a parcela não cabe.
  - Ressalva: Cortar não resolve: o corte deixa a parcela em exatos 30% da renda. Pedir acima da capacidade já é sinal de aperto.
- Clientes com nossa parcela somada às dívidas em outras instituições acima de 44% da renda têm inadimplência de 34%, contra 13,7% da média. Afeta 391 clientes. Pedidos novos no grupo: 323. Passo da política: Nega pelo risco estimado pela IA.
- Clientes com conta aberta há até 3 meses têm inadimplência de 20%, contra 13,7% da média. Afeta 83 clientes. Pedidos novos no grupo: 113. Passo da política: Nega pelo risco estimado pela IA.
- Clientes com restrição ativa no bureau têm inadimplência de 20%, contra 10,2% de quem não tem restrição. Afeta 127 clientes. Pedidos novos no grupo: 377. Passo da política: Quem pode ser aprovado.
  - Ressalva: Piloto sorteado com contratos de 6 a 12 meses: o calote ainda é parcial; a comparação é com clientes do piloto da mesma época. Aqui a regra atual acerta: manter a negativa.

**Onde a política atual nega quem pagaria**

- Clientes que a política atual negaria, mas com conta saudável (sem cheque especial recente, sem conta esvaziada, gastos até 90% das entradas e parcela até 25% da sobra) têm inadimplência de 5,3%, contra 9,7% de quem a política atual aprovaria. Afeta 318 clientes. Pedidos novos no grupo: 614. Passo da política: Nega pelo risco estimado pela IA.
  - Ressalva: Piloto sorteado com contratos de 6 a 12 meses: o calote ainda é parcial; a comparação é com clientes do piloto da mesma época.
- Clientes com score do bureau até 600, sem restrição e renda acima de R$ 2.000 (negados hoje só pelo score) têm inadimplência de 10,9%, contra 9,7% dos que têm score acima de 600. Afeta 238 clientes. Pedidos novos no grupo: 338. Passo da política: Quem pode ser aprovado.
  - Ressalva: Piloto sorteado com contratos de 6 a 12 meses: o calote ainda é parcial; a comparação é com clientes do piloto da mesma época. O gráfico mostra os contratos maduros: todas as faixas de score ficam entre 12% e 16% de calote, o score não separa bom de mau pagador. No piloto, os negados só pelo score ficam abaixo do ponto de equilíbrio (~17%): negar por score descarta clientes que dão lucro.
- Clientes com renda declarada entre R$ 1.500 e R$ 2.000 têm inadimplência de 12,9%, contra 11,3% de quem declara mais de R$ 2.000. Afeta 70 clientes. Pedidos novos no grupo: 120. Passo da política: Quem pode ser aprovado.
  - Ressalva: Piloto sorteado com contratos de 6 a 12 meses: o calote ainda é parcial; a comparação é com clientes do piloto da mesma época. Um pouco acima de quem ganha mais, mas abaixo do ponto de equilíbrio (~17%): o corte em R$ 2.000 nega clientes que dão lucro. A política proposta decide pelo risco, não pela renda.
- Clientes com prazo de 36 meses têm inadimplência de 8,3%, contra 13,7% da média. Afeta 726 clientes. Pedidos novos no grupo: 524. Passo da política: Nega pelo risco estimado pela IA.
  - Ressalva: Não é só a parcela menor: com a parcela até 20% da renda, 36 meses ainda têm menos calote que prazos de até 12 meses. O modelo de risco usa o prazo.

**Parecem perigosos, mas não são**

- Pedidos acima de R$ 20 mil parecem arriscados: inadimplência de 22%, contra 13,7% da média. Mas com parcela de até 20% da renda o calote cai para 9,7% (72 clientes). O que pesa é a parcela, não o valor. Passo da política: Nega quando a parcela não cabe.
