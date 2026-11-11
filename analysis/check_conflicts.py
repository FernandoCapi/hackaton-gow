import pandas as pd, numpy as np
df = pd.read_parquet("data/base.parquet")
h = df[df.situacao_final.notna() & (df.meses_desde_pedido>=12)].copy()
print("maduros12", len(h), h.bad.mean().round(3))
r = h.entradas_sobre_renda
for lo,hi in [(0,.6),(.6,.8),(.8,2)]:
    s=h[(r>=lo)&(r<hi)]; print(f"entradas/renda {lo}-{hi}: n={len(s)} bad={s.bad.mean():.3f}")
s=h[r<.6]; print("  <0.6 com compr<=25%:", len(s[s.comprometimento<=.25]), s[s.comprometimento<=.25].bad.mean().round(3))
so=h.mov_saidas_sobre_entradas
for lo,hi in [(0,.5),(.5,.9),(.9,9)]:
    s=h[(so>=lo)&(so<hi)]; print(f"saidas/entradas {lo}-{hi}: n={len(s)} bad={s.bad.mean():.3f}")
n=df[df.tipo_base=="novo"]
print("novos: entradas/renda<0.6", (n.entradas_sobre_renda<.6).sum(), "| saidas/entradas>0.9", (n.mov_saidas_sobre_entradas>.9).sum(), "| ambos", ((n.entradas_sobre_renda<.6)&(n.mov_saidas_sobre_entradas>.9)).sum())
