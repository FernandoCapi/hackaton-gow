---
description: Explora o banco do desafio e propõe o dataset de modelagem
---

Pré-requisito: o banco do desafio já restaurado (`python scripts/restore_db.py dumps/<arquivo>`).

1. Rode `python -m src.profile --save` e leia `docs/perfil-banco.md`.
2. Leia `docs/desafio.md` para saber qual decisão e qual métrica importam.
3. Investigue com SQL somente leitura o que o perfil não responde: granularidade de cada
   tabela, relacionamentos sem chave estrangeira declarada, períodos cobertos pelas datas,
   valores estranhos (negativos, datas futuras, duplicados).
4. Escreva `docs/dicionario-dados.md` com:
   - o que cada tabela representa e sua granularidade
   - como as tabelas se relacionam
   - candidatas a alvo e a identificador da entidade a pontuar
   - colunas com risco de vazamento (só conhecidas depois do resultado) e por quê
   - problemas de qualidade encontrados
5. Proponha, sem aplicar, o novo `sql/dataset.sql` (uma linha por entidade, alvo incluído,
   apenas informação anterior ao resultado) e os valores de `config.py`. Aplique depois que o
   time confirmar.
