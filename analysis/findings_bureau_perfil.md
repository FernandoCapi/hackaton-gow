# Achados: bureau e perfil cadastral

Base: aprovados históricos maduros (≥ 10 meses), n = 3.444, inadimplência 13,6%, atraso 20,6%.
Robustez: IC Wilson 95% e holdout temporal (T1 < 10/05/2025, T2 depois).
Ponto de equilíbrio: lucro por real ≈ 0,13 − 0,75 × inadimplência → prejuízo acima de ~17%.
Scripts: `analysis/agent_perfil/`.

## Top 8

1. **Pedido com parcela > 30% da renda, aprovado com valor cortado**: 57% de inadimplência (n=218, IC 50–63, T1 58,9% / T2 54,7%). Resultado −R$ 872 mil (carteira toda: +R$ 256 mil). Taxa não cresce com o excesso: o sinal é pedir acima da capacidade. Novos: 61 que a atual aprovaria cortando (130 pedem > 30%). **Negar em vez de cortar.**
2. **Score não prevê inadimplência**: AUC 0,50; faixas de 601 a 1000 todas entre 12% e 15%. No piloto, score ≤ 600 "limpo": 8,9% vs 7,0% do limpo > 600 (mesma maturidade ≥ 7 meses, não significativo). Novos: 319 negados só pelo score (R$ 2,2 mi). Ressalva: só piloto, n pequeno.
3. **Prazo longo é mais seguro**: 36 meses 7,8% (n=876), até 12 meses 19,5% (n=930). Vale com parcela controlada e em safras ≥ 18 meses. Pior: 6 meses com R$ 5–20 mil (28–30%).
4. **Valor > R$ 20 mil é armadilha**: 35,8% (n=260), mas com parcela ≤ 20% cai para 9,9% (n=101). O risco é o comprometimento, não o valor.
5. **8+ consultas em 90 dias**: 83% (n=29, IC 65–92). 7+ consultas e parcela > 8%: 50% (n=58). 4–7: 19,6%. Novos: 38 com 8+.
6. **Parcela 25–30% da renda**: 30% (n=69, IC 21–42). 20–25%: 15%; ≤ 20%: ~10%. Sugestão: teto 25%.
7. **Outras dívidas só pesam quando grandes**: comprometimento total > 44% (com nossa parcela ≤ 25%): 19,9% (n=156). Outras > 40% da renda: 27,7% (n=65).
8. **Conta com até 3 meses**: 22,5% (n=111, IC 16–31); 4–6 meses cai para 3–7%. Com parcela ≤ 25%: 17,6%.

## Outros
- **Restrição ativa**: 23% (piloto, n=39); mesma maturidade 20,4% vs 7,0%. Manter negativa.
- **Histórico de bureau curto**: 13,9% (≤ 12 meses, n=101). Não é motivo para negar; 399 novos, só 10 aprovados pela atual.
- **Renda ≤ R$ 2.500**: 18,8%, mas com parcela ≤ 25% cai para 9,3% (n=270). Renda 1.500–2.000 no piloto: 12,5% (n=24).
- **Vínculo**: aposentado 9,3%, empresário 18,2%, autônomo 16,3% (efeito moderado).
- **Profissão**: nada passa Bonferroni (46 testadas). Motorista de app 29,4% é efeito de comprometimento. Não usar.

## Atributos sensíveis (reportar, não usar)
Gênero sem efeito. Viúvos 4,0% (n=100), parece plantado, mas é atributo sensível. Idade > 70: 6,5% instável. CEP prefixo 1: 20,1% não significativo.

## Alertas
- Atraso e inadimplência são quase independentes: não usar um como proxy do outro.
- Corte de valor da atual é mecânico (parcela = exatamente 30%).
- Piloto: score > 450, renda > 1.500, até 1 restrição, sem teto de comprometimento; só 367 maduros.
- Sem drift entre histórico e novos.
- AUC: score 0,50, restrições 0,505, consultas 0,54; comprometimento 0,67, comprometimento total 0,65, valor 0,63, prazo 0,59.
- `primeiro_nome_prof` é cópia de profissão; não há nome no banco.
- Árvore rasa: 1º corte parcela ≤ 26%; depois consultas > 6,5 e comprometimento total > 44%; do lado alto, prazo > 21 meses.
