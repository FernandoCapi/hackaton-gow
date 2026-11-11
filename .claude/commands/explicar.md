---
description: Gera a explicação para o cliente usando o seu próprio acesso ao Claude
---

1. Rode `python -m src.explain --prompt-only`. Se ainda não houver `artifacts/metrics.json`,
   rode `python -m src.train` antes.
2. Leia `artifacts/explain_prompt.md`. A parte antes do `---` traz as instruções de formato e
   de tom; a parte depois traz o desafio, as métricas e os fatores agregados.
3. Escreva a explicação seguindo essas instruções, usando apenas números presentes no prompt,
   e grave o resultado em `artifacts/explanation.md` (o painel lê esse arquivo).
4. Mostre o texto e aponte qualquer afirmação que dependa de suposição.
