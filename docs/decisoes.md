# Registro de decisões

Uma entrada por decisão: quando, o que foi decidido, por quê e de onde veio (manual, cliente,
dados, time). Alimenta a "defesa das escolhas" e o "que mudou depois do checkpoint" do pitch.

| Horário | Decisão | Por quê | Fonte |
|---|---|---|---|
| 11/11 manhã | Time **selic**; arquivo final `selic_final.csv` | Identificador do time no manual | Time |
| 11/11 manhã | Regras resumidas em `docs/desafio.md`, sem URL e token do bureau; PDFs e dump fora do repo | Repositório é público | Time |
| 11/11 manhã | Uma branch por frente (dados/modelo, bureau+CSV, painel), merges pequenos na `main` | Trabalho em paralelo sem quebrar a `main` | Time |
| 11/11 manhã | Postura de risco decidida **depois** de ver a calibração do modelo; o corte é parâmetro | Não chutar o apetite a risco antes dos dados | Time |
| 11/11 manhã | Bureau dos novos em cache local (`data/`), com nova tentativa e espera crescente em 503 e lentidão | Resposta é determinística; falha é proposital e conta em qualidade técnica | Manual |
| 11/11 manhã | Política atual reproduzida: elegível se score > 600, renda > 2.000 e 0 restrições; valor = solicitado ou o máximo cuja parcela cabe em 30% da renda | Bate 100% com as decisões históricas da política atual | Dados |
| 11/11 manhã | Inadimplência só pode ser medida em safras maduras (cai de ~15% em 2024 para 0% em 2026T3 por falta de tempo) | Contratos recentes ainda não tiveram tempo de chegar a 90 dias de atraso | Dados |
| 11/11 manhã | Candidato a corte de safra madura: ≥ 10 meses desde o pedido (calote: 0% em 0–3 meses, 4% em 4–6, 8,5% em 7–9, ~12–15% a partir de 10) | É onde a taxa de calote para de subir; abaixo disso, "em dia" ainda não quer dizer bom pagador | Dados |
| 11/11 manhã | Bureau dos 2.000 novos obtido: 119 respostas 503 recuperadas com nova tentativa, 0 faltando | Lote completo em ~1 min; segunda execução não chama a API | Dados |
| 11/11 manhã | Modelo treinado com contratos de **≥ 12 meses** (2.832); só calote, atraso como taxa fixa de 20% | Calote estabiliza perto de 18 meses; atraso não é previsível (AUC 0,51) | Dados (auditoria) |
| 11/11 manhã | Restrição monotônica: o risco só sobe com o peso da parcela | Garante que valor menor nunca piore o risco e deixa a regra explicável | Time |
| 11/11 manhã | **Restrição ativa: nega** (padrão `max_restrictions = 0`) | Nenhum contrato com 12 meses tem restrição (o piloto é mais novo): o modelo não aprendeu esse risco; no piloto deu 19–23% de calote | Dados |
| 11/11 manhã | Fora do que o piloto testou (score ≤ 450, renda ≤ 1.500) **nega** | Sem evidência; o modelo aprovaria mais (+R$ 72 mil estimado), mas seria extrapolação | Dados |
| 11/11 manhã | Regra de valor padrão: **valor pedido ou nega** | No histórico rende mais (+R$ 1,11 mi × +R$ 0,80 mi reduzindo); redução profunda não tem dados | Dados (avaliação) |
| 11/11 manhã | Cortes de risco 15% (quem a atual aprovaria) e 12% (quem ela negaria) | Ganho no histórico estável entre 12% e 17%; no piloto, os aprovados pela expansão tiveram 3,9% de calote | Dados (avaliação) |
| 11/11 manhã | Alvo do modelo mantido em **contratos com 12+ meses**. Testado o alvo "calote nos 9 primeiros meses", que traria 560 contratos do piloto para o treino, e descartado | Mesma régua: AUC em maduros nunca vistos 0,797 × 0,772; em clientes do piloto que a atual negaria 0,903 × 0,891; ganho no histórico R$ 1,11 mi × R$ 1,13 mi (dentro do ruído). Incluir o piloto não melhora onde importa | Dados (teste do Davi) |
| 11/11 | Padrões do painel calculados por código (`src/patterns.py`) na base de **12+ meses**, a mesma do modelo; os do piloto comparados com clientes do piloto da mesma época | Painel e motor contam a mesma história com o mesmo número; o piloto ainda tem calote parcial | Time |
| 11/11 | **Prazo de 36 meses é padrão real**, não armadilha (corrige `docs/padroes.md`) | Com a mesma parcela (até 20% da renda): 5,9% de calote em 36 meses × 13,5% em até 12 meses | Dados |
| 11/11 | "Parcela entre 25% e 30% da renda" **fora** da lista de padrões | Medida sobre a renda efetiva, dá 10,6% (66 contratos), sem salto; o salto só aparece acima de 30%, nos valores cortados (56%) | Dados |

## Perguntas para o cliente (janela de dúvidas)

1. O desfecho dos novos pedidos é o do contrato inteiro? "Pagou com atraso" e "não pagou"
   seguem a regra de 90 dias de `situacao_final`?
2. O limite de 30% considera só a nossa parcela ou também `parcelas_outras_instituicoes`?
3. Como o desfecho reage a um valor aprovado menor que o pedido?
4. Podemos alterar o prazo, ou só o valor?
5. Os pedidos do piloto foram sorteados ou escolhidos?

## Respostas do cliente

_(registrar aqui, com horário)_
