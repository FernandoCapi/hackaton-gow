# Desafio Fortuna Crédito — resumo das regras

Resumo do Manual do Participante e do Dicionário de dados (material das 8h, fora do repo).
Endereço e token do bureau ficam só no `.env` local.

## Cliente e pedido

Fintech de crédito pessoal para quem já tem conta digital nela. Teto de R$ 30 mil por cliente,
mínimo de R$ 500. A IA precisa encontrar padrões de bom e mau pagamento no histórico e propor
uma **política de aprovação e de valor** melhor que a atual, aplicada aos pedidos novos.
A IA sugere e o analista de risco decide: nenhuma política vai para produção sem aprovação humana.

### Política atual (referência da pontuação)

1. Score do bureau acima de 600.
2. Renda declarada acima de R$ 2.000.
3. Sem restrições ativas no bureau.
4. Parcela de até 30% da renda declarada.

Conferido nos dados: os 4 primeiros critérios decidem aprova/nega sem exceção nos pedidos da
política atual; quando a parcela do valor pedido passa de 30% da renda, o valor aprovado é
reduzido ao máximo que cabe nos 30%.

Houve um **piloto** de 6 meses (out/2025 a mar/2026) com critérios mais flexíveis: o histórico
tem aprovados que a política atual negaria.

### Parcela

Tabela Price, juros de 3% ao mês: `parcela = valor × 0,03 / (1 − 1,03^(−prazo))`.
Ex.: R$ 10.000 em 12 meses = R$ 1.004,62. Prazos possíveis: 6, 12, 18, 24 ou 36 meses.

## Dados (schema `hackathon`)

| Tabela | Uma linha por | Base |
|---|---|---|
| `clientes` | cliente (cadastro na data do pedido) | histórica e novos |
| `pedidos` | pedido (`tipo_base` = `historico` ou `novo`) | histórica e novos |
| `movimentacao_mensal` | cliente e mês, 12 meses antes do pedido | histórica e novos |
| `bureau` | pedido | só histórica |
| `parcelas` | parcela de pedido aprovado | só histórica |

- Histórico: 10 mil pedidos de out/2024 a set/2026, com decisão, valor aprovado, política
  aplicada e `situacao_final`. Novos: 2 mil pedidos de out/2026, sem decisão.
- Cada cliente aparece em um único pedido.
- **Data de corte 30/09/2026**: contratos recentes ainda estão em andamento.
- `situacao_final`: `quitado_em_dia`, `quitado_com_atraso`, `em_dia`, `em_atraso`,
  `inadimplente` (alguma parcela vencida e não paga há 90 dias ou mais).
- Bureau dos novos vem da API, consultada pelo `id_cliente`. Falha com 503 e demora de
  propósito; resposta é sempre a mesma para o mesmo cliente; sem limite de chamadas;
  chamadas registradas por time. 401 token, 404 cliente fora da base de novos.

## Como a nota é formada

| Critério | Peso | Como |
|---|---|---|
| Ganho sobre a política atual | 40% | Automático, pelo arquivo de decisões |
| Padrões descobertos pela IA | 25% | Banca: padrões e se a explicação está correta |
| Pitch | 15% | Clareza, demo ao vivo, defesa das escolhas |
| Painel de experimentação | 10% | Analista entende padrões e política sem ler código |
| Qualidade técnica | 10% | Código, tratamento de falhas do bureau, reprodutibilidade |

### Resultado financeiro

Para cada pedido novo aprovado, com o desfecho que só a organização conhece:

| Desfecho | Resultado |
|---|---|
| Pagou em dia | +15% do valor aprovado |
| Pagou com atraso | +5% do valor aprovado |
| Não pagou | −60% do valor aprovado |
| Negado | 0 |

Ganho = resultado da nossa política − resultado da política atual nos mesmos pedidos.
Nota = ganho ÷ maior ganho entre os times × 10; ganho ≤ 0 vale zero. O desfecho considera o
valor aprovado: aprovar mais do que o cliente consegue pagar aumenta o risco.

## Entregas

1. **Arquivo de decisões** `selic_final.csv`, gerado por código (CSV editado à mão desclassifica):
   - UTF-8, vírgula, cabeçalho exato `id_pedido,decisao,valor_aprovado`;
   - uma linha por pedido novo, sem repetição; `APROVADO`/`NEGADO` em maiúsculas;
   - valor com ponto e duas casas; > 0 se aprovado, `0.00` se negado;
   - ausente ou decisão inválida conta como negado; valor acima do pedido ou de R$ 30 mil é
     reduzido ao limite.
2. **Painel de experimentação** para o analista de risco, com duas partes obrigatórias:
   - Padrões: "Clientes com [característica] têm inadimplência de N%, contra M% da média.
     Afeta K clientes."
   - Política proposta em passos, na ordem em que são aplicados (aprova, nega, valor).
3. **Pitch** de 5 min + 2 min de perguntas: onde a IA entra, principais padrões, política e o
   que mudou depois do checkpoint, como o analista valida. A banca pode pedir a decisão de
   pedidos específicos ao vivo.
4. **Código** (opcional, conta a favor) com README e o comando que gera o arquivo do zero.

## Regras

- A IA precisa participar da descoberta dos padrões e da decisão (modelo treinado, LLM ou os
  dois). Usar IA só para escrever código não conta.
- Proibido usar dados externos ao kit. Pode conversar com outros times, sem compartilhar
  código, consultas ou arquivos.

## Relógio

| Horário | Marco |
|---|---|
| 08h00 | Kickoff |
| 14h15 | Checkpoint: enviar versão do CSV no Teams, relatório de formato + 10 min com mentor |
| até 15h30 | Validação do arquivo a qualquer hora, quantas vezes quiser |
| 15h30 | Code freeze e envio final (vale o último arquivo até 15h30) |
| 15h45 | Pitches |
