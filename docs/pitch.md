# Pitch — time selic (5 min + 2 min de perguntas)

Fontes dos números: `docs/avaliacao-motor.md` (gerado por `python -m src.evaluate`),
`/v1/patterns` (`src/patterns.py`) e `analysis/pitch_numbers.py` (discriminação, alerta antecipado,
pedidos da demo). Tudo agregado; nenhum dado de cliente sai da máquina.

**Suposição marcada:** o ganho nos pedidos novos é **estimado pelo modelo**; o número real só a
organização calcula. O ganho no histórico usa o desfecho real.

| Bloco | Tempo | Quem fala |
|---|---|---|
| 1. Problema | 0:00–0:35 | _(definir)_ |
| 2. O que os dados revelaram | 0:35–1:35 | _(definir)_ |
| 3. A solução + demo | 1:35–3:05 | _(definir)_ |
| 4. Impacto | 3:05–3:35 | _(definir)_ |
| 5. Como o analista valida + escolhas e limites | 3:35–4:30 | _(definir)_ |
| 6. O que mudou no checkpoint + próximos passos | 4:30–5:00 | _(definir)_ |

---

## 1. Problema do cliente (35 s)

> A Fortuna decide, todo dia, **se empresta e quanto**. A política de hoje tem quatro regras fixas
> e está parada há mais de um ano. Errar custa caro e de forma assimétrica: um cliente que não paga
> custa 60% do valor, o mesmo que o lucro de **quatro** clientes que pagam em dia. E testar uma
> regra nova leva semanas de planilha para uma ou duas hipóteses.
>
> A pergunta que respondemos: **onde a política atual erra, e qual política ganha mais dinheiro
> com o analista no controle?**

## 2. O que os dados revelaram (60 s)

Três achados, na língua do analista:

1. **A movimentação da conta denuncia o calote; o score não.**
   > "Clientes que gastam mais de 90% do que entra na conta têm inadimplência de **91%**, contra
   > 13,7% da média. Quem esvaziou a conta antes do pedido: **87%**. Cheque especial em 2 dos 3
   > meses anteriores: **91%**."
   >
   > Enquanto isso, o score do bureau, a régua principal da política atual, separa bons e maus
   > pagadores tanto quanto um sorteio: nota **0,48** numa escala em que 0,5 é sorte. Todas as
   > faixas de score têm entre 12% e 16% de calote.

2. **Cortar o valor não salva quem pede além da conta.**
   > "Quem pediu uma parcela acima de 30% da renda e teve o valor cortado pela regra atual deu
   > **56%** de calote. Afeta 177 clientes." O pedido acima da capacidade já é o sinal de risco.

3. **A política atual nega bons pagadores.**
   > No piloto sorteado da própria Fortuna, "clientes que a política atual negaria, mas com conta
   > saudável, tiveram **5,3%** de calote, contra **9,7%** de quem ela aprova. Afeta 318 clientes."
   > Negados só pelo score: 10,9%, abaixo do ponto de equilíbrio de ~17%: dão lucro.

**Onde a IA entrou:** agentes de IA exploraram o banco em paralelo (movimentação, bureau,
auditoria de armadilhas, economia) e levantaram os padrões; um modelo de risco (LightGBM)
aprendeu com o histórico a chance de calote de cada pedido; e é esse modelo que decide o passo
de risco da política. A IA também auditou as armadilhas: contratos recentes que parecem bons
porque ainda não tiveram tempo de atrasar, e colunas que vazam o resultado.

## 3. A solução (90 s, com demo)

> A IA propõe uma política em cinco passos, na ordem em que são aplicados:
>
> 1. **Fora do que o piloto testou:** nega com restrição ativa, score até 450 ou renda até
>    R$ 1.500 — sem evidência, não arriscamos.
> 2. **Sinais de aperto na conta:** nega quem gasta mais de 90% do que entra, esvaziou a conta,
>    usou cheque especial em 2 dos 3 meses anteriores, tem entradas abaixo de 60% da renda
>    declarada ou 8+ consultas ao CPF.
> 3. **Capacidade:** parcela até 25% da renda efetiva (o menor entre a renda declarada e o que
>    de fato entra na conta).
> 4. **Risco estimado pela IA:** acima de 15% de chance de calote, nega (12% para quem a
>    política atual negaria).
> 5. **Valor:** o valor pedido, até R$ 30 mil; se não cabe, nega em vez de cortar.

**DEMO — o que mostrar na tela** (painel → aba de pedidos → busca por id):

| Pedido | O que mostra | Atual | Proposta |
|---|---|---|---|
| **P-05909** | Score **851**, R$ 5.600. Gasta 108% do que entra, 3 meses no cheque especial, saída 28x a normal. Risco **88%** | Aprova | **Nega** (aperto na conta) |
| **P-75328** | Score **510**, R$ 2.800 em 36x, renda R$ 3.150, conta saudável. Risco **3,4%** | Nega (score) | **Aprova** |
| **P-93615** | Score 674, R$ 13.100 em 12x. Nenhum filtro dispara, mas as entradas cobrem só 68% da renda declarada e a parcela come 28% da sobra do mês. Combinando os sinais, a IA estima risco **32%** | Aprova | **Nega** (risco da IA) |
| P-47965 | Caso tranquilo: R$ 3.500, risco 2,2% | Aprova | Aprova |
| P-80781 · **EXTRA** | Pediu R$ 26.000 e não cabe na renda: negado. O painel mostra a **contraproposta**: R$ 23.400 (90%) com 6,2% de risco. Não entra no arquivo oficial | — | Nega + oferta |

Fala na demo: "o score diz que o P-05909 é ótimo; a conta diz o contrário — e o histórico mostra
que perfis assim deram calote 9 em cada 10 vezes". Mostrar os **motivos** e os **passos** do pedido.

Depois, no **laboratório**: mover o corte de risco e mostrar o resultado em R$ mudando na hora.
> "O ciclo que levava semanas agora leva segundos."

## 4. Impacto (30 s)

> **Histórico, com o desfecho real** (2.832 contratos maduros, cada um avaliado por um modelo que
> não o viu): a política atual teria dado **−R$ 229.820**; a proposta, **+R$ 884.754**. Ganho de
> **R$ 1.114.574**, evitando **221 calotes** que a política atual aprovou.
>
> **Pedidos novos (estimado pelo modelo):** aprovamos **1.232** pedidos, contra 1.145 da atual.
> Resultado esperado de **R$ 630.950**, contra R$ 150.021: **+R$ 480.928**.
>
> Conta: cada pedido aprovado rende +15% se paga em dia, +5% com atraso, −60% se não paga; somamos
> e subtraímos o resultado da política atual nos mesmos pedidos.

## 5. Como o analista valida + escolhas e limites (55 s)

**Antes de aprovar**

- Simula qualquer ajuste no painel e vê o efeito em R$, os pedidos que mudam e o porquê, pedido
  a pedido. Só a aprovação dele coloca a política em vigor (versão, autor, data).
- **Checagem de discriminação:** gênero, idade, estado civil e CEP **não entram** no modelo. E
  conferimos o resultado. A taxa de aprovação ficou mais equilibrada entre gêneros: a razão entre o
  grupo menos e o mais aprovado subiu de 0,74 para 0,90. Também ficou equilibrada entre faixas de
  idade, com razão de 0,94. **Ponto de atenção honesto:** por região do CEP, a razão ficou em 0,77,
  contra 0,80 da atual. A diferença não vem do CEP, que o modelo não usa, mas o analista deve
  acompanhar.

**Depois de aprovar: alerta antecipado**

- O calote só aparece depois de ~4 meses e só estabiliza perto de 18. Esperar isso é inviável.
- Nos dados: quem atrasa alguma das **6 primeiras parcelas** termina com **43,6%** de calote;
  quem não atrasa, **0,7%**. Esse sinal captura **97%** dos calotes.
- Proposta: implantar como a Fortuna já fez com o piloto (uma fatia dos pedidos) e acompanhar o
  atraso das primeiras parcelas por safra, com gatilho para voltar à política anterior.

**Escolhas e o que descartamos**

- **Negar em vez de cortar o valor:** no histórico rende R$ 1,11 mi, contra R$ 0,80 mi cortando.
  Cortes fundos não existem nos dados (5 casos); seria o modelo inventando.
- **Score fora como filtro:** não prevê nada nos dados.
- **Testamos incluir o piloto no treino** (alvo de 9 meses): não melhorou onde importa (0,891
  contra 0,903 nos clientes que a atual negaria). Mantivemos o modelo mais simples.
- **Corte de risco estável:** entre 12% e 17%, o ganho no histórico quase não muda. A escolha não
  é um ponto frágil.

**Limites**

- Só há desfecho de quem foi aprovado; a expansão se apoia nos contratos do piloto, com 6 a 12
  meses de vida (calote ainda parcial).
- O ganho dos novos é estimativa do modelo, não resultado.

## 6. O que mudou depois do checkpoint + próximos passos (30 s)

**Depois do checkpoint (14h15):** _(preencher com o relatório da organização, a conversa com o
mentor e as respostas da Gabi. Pergunta mais importante: se aprovar um valor menor reduz o
calote, "reduzir até caber" vira opção — hoje estimada em +R$ 69 mil a mais nos novos)._

**Com mais tempo:**

1. Rodar a política em piloto controlado, com o alerta das primeiras parcelas.
2. Re-treinar quando as safras do piloto amadurecerem (hoje com 6 a 12 meses).
3. Levar a contraproposta (hoje EXTRA no painel: 180 negados por capacidade ou risco teriam
   aprovação com valor menor) para a esteira de venda, com a explicação ao cliente exigida pela LGPD.

---

## Perguntas prováveis da banca

1. **"Por que não usar o score, se todo mundo usa?"**
   Nos dados ele não separa bom de mau pagador: nota 0,48, que equivale a sorte. Ele continua
   como informação do modelo, mas não decide sozinho.

2. **"Como vocês sabem que o modelo não está trapaceando?"**
   Três testes. O modelo foi testado em pedidos de jul a set/2025 que nunca viu e teve nota 0,80.
   Com o desfecho embaralhado, a nota cai para cerca de 0,5. E colunas posteriores à decisão, como
   valor aprovado, situação e parcelas, ficam de fora.

3. **"Vocês aprovam quem a Fortuna nega. Não é arriscado?"**
   Só aprovamos quem o piloto sorteado da própria Fortuna testou e com risco abaixo de 12%. No
   piloto, esse grupo teve 3,9% de calote, abaixo dos 4,5% de quem as duas políticas aprovam.

4. **"Por que negar em vez de dar um valor menor?"**
   Quem a política atual cortou deu 56% de calote, porque o pedido acima da capacidade já é o
   sinal. E não há dados de cortes maiores: seria o modelo extrapolando. Se a Fortuna confirmar
   que um valor menor reduz o risco, a regra muda com um clique.

5. **"E se o modelo errar depois de implantado?"**
   O alerta das primeiras parcelas mostra em 3 a 6 meses, e não em 18, se a safra está pior que o
   esperado. A política tem versão, e voltar à anterior é um clique do analista.
