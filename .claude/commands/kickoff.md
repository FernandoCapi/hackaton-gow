---
description: Registra o briefing do desafio e prepara o repositório para ele
argument-hint: <briefing colado ou caminho do arquivo>
---

Briefing do desafio:

$ARGUMENTS

1. Grave o briefing em `docs/desafio.md`, sem resumir nem reescrever. Se o argumento for um
   caminho de arquivo, leia o arquivo.
2. Substitua a seção "Desafio" do `CLAUDE.md` por um resumo com estes itens, marcando como
   "não informado" o que o briefing não disser:
   - Cliente e contexto de negócio
   - Decisão que o cliente precisa tomar
   - Métrica objetiva: o que é medido, como é calculada, como e quantas vezes se submete
   - Formato da entrega (arquivo, endpoint, repositório, painel)
   - Critérios da banca e pesos
   - Restrições (ferramentas, dados, prazos)
3. Liste as perguntas em aberto para fazer à organização ainda no kickoff, da mais para a
   menos importante para a nota.
4. Diga em poucas linhas que tipo de problema é (classificação, regressão, ranking, previsão
   de série, otimização, outro) e se o esqueleto atual (`config.py`, `sql/dataset.sql`,
   `src/train.py`) serve como está, precisa de ajuste ou não se aplica. Não altere código
   nesta etapa.
