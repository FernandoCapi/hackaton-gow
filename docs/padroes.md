# Padrões encontrados e rascunho da política

Consolidado de 4 análises em paralelo: movimentação, bureau e perfil, auditoria e economia.
Os detalhes e os scripts estão em `analysis/findings_*.md`.

- **Base:** pedidos históricos aprovados e maduros. A inadimplência média é **13,6%**.
- **Ponto de equilíbrio:** com +15% / +5% / −60%, um grupo só dá lucro se a inadimplência ficar **abaixo de ~17%**.

## Padrões (formato do painel)

### Onde a política atual aprova e perde dinheiro

1. **Saídas iguais às entradas.** Clientes cujas saídas consomem mais de 90% do que entra na conta têm inadimplência de **91%**, contra 13,6% da média. Afeta 67 clientes maduros (490 no histórico), e **97 pedidos novos** se encaixam nesse perfil. A política atual aprova 32% desse grupo.
2. **Conta esvaziada antes do pedido.** O cliente fazia o saldo crescer, retirou de uma vez cerca de 8 vezes a renda e ficou 2 ou 3 meses no cheque especial. Esses clientes têm inadimplência de **82%**, contra 13,6% da média. Afeta 88 clientes. Com cheque especial em 2 dos 3 meses antes do pedido, a inadimplência é de **85%** (73 clientes). Hoje a política atual aprova 107 dos 119 clientes com cheque recente.
3. **Pedido acima da capacidade, aprovado com valor cortado.** A política atual reduz o valor até a parcela caber em 30% da renda. Esses clientes têm inadimplência de **57%**, contra 13,6% da média. Afeta 218 clientes, que custaram **−R$ 872 mil**, enquanto a carteira inteira lucrou só R$ 256 mil. Pedir acima da capacidade já é sinal de risco: cortar o valor não resolve.
4. **Parcela que consome a sobra do mês.** Quando a parcela passa de 45% da sobra mensal (entradas menos saídas), a inadimplência é de **64%**, contra 13,6% da média. Afeta 339 clientes e concentra 46% de todos os inadimplentes.
5. **Parcela entre 25% e 30% da renda.** Já dá prejuízo: inadimplência de **26 a 30%**, contra 13,6% da média. Abaixo de 20% da renda fica em ~10%. O limite de 30% da política atual é frouxo.
6. **Renda declarada inflada.** Clientes cujas entradas na conta ficam abaixo de 60% da renda declarada têm inadimplência de **71%**, contra 13,6% da média. São poucos no histórico (14 maduros), mas **74 pedidos novos** têm esse perfil.
7. **Busca intensa por crédito.** Clientes com 8 ou mais consultas no CPF em 90 dias têm inadimplência de **83%**, contra 13,6% da média. Afeta 29 clientes (38 novos).
8. **Conta muito nova.** Clientes com conta aberta há até 3 meses têm inadimplência de **22,5%**, contra 13,6% da média. Afeta 111 clientes. A partir de 4 meses de conta cai para 3–7%.
9. **Dívidas pesadas em outras instituições.** Quando a nossa parcela somada às outras dívidas passa de 44% da renda, a inadimplência é de **20%**, contra 13,6% da média. Afeta 156 clientes.

### Onde a política atual nega quem pagaria

10. **O score do bureau não prevê inadimplência.** Os aprovados têm inadimplência entre 12% e 16% em todas as faixas de score. No piloto, que foi sorteado, clientes "limpos" com score até 600 tiveram **6,0%**, contra 5,5% dos que tinham score acima de 600. A regra "score > 600" nega **319 pedidos novos** sem reduzir o risco.
11. **Negados com conta saudável pagam.** Conta saudável aqui quer dizer sem cheque especial recente, sem esvaziamento e com parcela de até 25% da sobra. Entre os clientes que a política atual negaria e o piloto aprovou, os que tinham conta saudável tiveram inadimplência de **7,9%**, contra 13,6% da média. Nos pedidos novos, **607 dos 855 negados** têm conta saudável.
12. **Renda entre R$ 1.500 e R$ 2.000.** Esses clientes do piloto tiveram inadimplência de **12%**, abaixo da média. O corte de renda não protege nada.
13. **Restrição ativa (aqui a regra atual acerta).** Clientes com uma restrição têm inadimplência de **19 a 23%** e 48% de atraso. Manter a negativa.

### Padrões que parecem perigosos, mas não são (armadilhas)

- **Pedido acima de R$ 20 mil:** inadimplência de 35,8%. Com parcela de até 20% da renda, cai para 9,9%. O que pesa é a parcela, não o valor.
- **Prazo longo:** 36 meses tem 7,8% de inadimplência, contra 19,5% em até 12 meses. A diferença vem quase toda do peso da parcela na renda.
- **Histórico curto no bureau:** inadimplência de 13,9%, igual à média.
- **Profissão:** nenhuma se sustenta estatisticamente. O motorista de aplicativo só parece arriscado por causa do peso da parcela.
- **Salário comprovado contra renda declarada:** essa comparação não mede renda inflada. Autônomos e empresários quase não recebem "salário" na conta. Usar o total de entradas.
- **Viúvos (4%) e maiores de 70 anos:** são atributos sensíveis e não entram como regra (LGPD/BC). O efeito vem da aposentadoria.

### Pegadinhas técnicas

- **Contratos ainda não maduros.** Nenhum calote acontece antes de ~4 meses de contrato, e a inadimplência só estabiliza perto de 18 meses. Treinar com contratos recentes ensina ao modelo que "recente = bom".
- **Atraso hoje não é um bom desfecho.** Quem está `em_atraso` termina 20 a 30% inadimplente. Já `quitado_com_atraso` é bom, com margem baixa.
- **Colunas de depois da decisão vazam o resultado.** `max_atraso`, por exemplo, prevê o desfecho com acerto de 100%. Usar uma lista fechada de features.
- **Distorções da movimentação.** O cheque especial do mês mais antigo é artefato dos dados, e o saldo só cresce, então não mede riqueza.
- **Score e atraso não ajudam o modelo.** O score tem AUC de 0,50; o atraso não é previsível (AUC 0,51).

## Rascunho da política proposta (em validação)

1. **Filtros:**
   - nega quem tem 2 ou mais restrições (não há nenhum dado de aprovação nessa faixa);
   - nega saídas acima de 90% das entradas;
   - nega cheque especial em 2 dos últimos 3 meses ou esvaziamento recente da conta;
   - nega renda inflada (entradas abaixo de 60% da renda declarada);
   - nega 8 ou mais consultas em 90 dias.
2. **Capacidade:** a renda efetiva é o menor valor entre a renda declarada e a média de entradas. A parcela pode ser **no máximo 25%** da renda efetiva. Se o pedido passa muito desse limite, **nega** em vez de cortar.
3. **Risco:** um modelo treinado no histórico estima a chance de calote (AUC de 0,81 com validação por tempo).
   - Aprova até ~15% para quem passaria na política atual.
   - Aprova até ~12% para quem a política atual nega, ou seja, score ≤ 600, renda ≤ 2.000 ou 1 restrição.
4. **Valor:** aprova o valor pedido quando ele cabe no limite. Reduz só se o lucro esperado continuar positivo. Respeita o máximo de R$ 30 mil e o valor solicitado.
5. **Score:** não é filtro.

**Estimativa nos 2.000 pedidos novos:** cerca de 1.500 aprovações (contra 1.145 da política atual), com ganho esperado de **+R$ 300 mil a +R$ 600 mil** sobre a política atual.

## Decisões abertas

- **Maturidade usada no treino:** 12 ou 15 meses.
- **Cortes de risco:** 12% e 15% ou outros valores, e quão conservadores ser.
- **Redução de valor:** reduzir ou só aprovar ou negar. A redução profunda não tem dados históricos e seria extrapolação.
- **Pergunta para o cliente:** confirmar se o desfecho dos pedidos novos considera o valor reduzido.
