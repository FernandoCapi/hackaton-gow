---
description: Monta o roteiro do pitch a partir dos resultados atuais
argument-hint: [duração em minutos]
---

Duração do pitch: $ARGUMENTS (se vazio, pergunte ao time antes de fechar o roteiro).

Leia `docs/desafio.md`, `artifacts/metrics.json`, `artifacts/factors.csv`,
`artifacts/factor_profiles.json` e, se existir, `artifacts/explanation.md`.

Escreva `docs/pitch.md` com o roteiro falado, nesta ordem:

1. **Problema do cliente** — a decisão que ele precisa tomar e o que custa errar.
2. **O que os dados revelaram** — de 2 a 3 achados, cada um com um número e em linguagem que
   o cliente usaria.
3. **A solução** — o que o painel mostra e como o cliente decide com ele; indique o momento
   da demonstração e o que mostrar na tela.
4. **Impacto** — resultado na métrica objetiva e, se houver base nos dados, estimativa em
   reais com a conta explícita.
5. **Escolhas e limites** — por que este caminho, o que foi descartado, o que o modelo não
   permite afirmar.
6. **Próximos passos** — o que faríamos com mais tempo.

Use apenas números presentes nos arquivos; sinalize qualquer suposição como suposição. Inclua
o tempo previsto por bloco e, ao final, as 5 perguntas mais prováveis da banca com respostas
curtas.
