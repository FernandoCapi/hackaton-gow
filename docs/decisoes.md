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

## Perguntas para o cliente (janela de dúvidas)

1. O desfecho dos novos pedidos é o do contrato inteiro? "Pagou com atraso" e "não pagou"
   seguem a regra de 90 dias de `situacao_final`?
2. O limite de 30% considera só a nossa parcela ou também `parcelas_outras_instituicoes`?
3. Como o desfecho reage a um valor aprovado menor que o pedido?
4. Podemos alterar o prazo, ou só o valor?
5. Os pedidos do piloto foram sorteados ou escolhidos?

## Respostas do cliente

_(registrar aqui, com horário)_
