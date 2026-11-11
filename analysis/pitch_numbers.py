"""Numbers for the pitch: fairness check, early warning, demo orders (aggregates only)."""
import numpy as np, pandas as pd
from src.db import read_sql
from src.features import load_orders

o = load_orders()
d = pd.read_csv("artifacts/decisions_novos.csv").set_index("id_pedido")
cli = read_sql("select id_cliente, genero, data_nascimento, estado_civil, cep from hackathon.clientes")
new = o[o.tipo_base.eq("novo")].join(d[["decision", "current_decision", "denied_at", "default_risk"]]).merge(cli, on="id_cliente")
new["idade"] = (new.data_pedido - pd.to_datetime(new.data_nascimento)).dt.days / 365.25
new["faixa_idade"] = pd.cut(new.idade, [0, 30, 45, 60, 200], labels=["até 30", "31–45", "46–60", "60+"])
new["regiao_cep"] = new.cep.str[0]
print("== aprovacao por grupo (novos): atual x proposta")
for col in ["genero", "faixa_idade", "estado_civil", "regiao_cep"]:
    t = new.groupby(col, observed=True).agg(n=("decision", "size"), atual=("current_decision", lambda s: (s == "APROVADO").mean()),
                                             proposta=("decision", lambda s: (s == "APROVADO").mean()))
    t["razao_menor_maior"] = None
    print(f"-- {col}: proposta min/max = {t.proposta.min():.2f}/{t.proposta.max():.2f} (razao {t.proposta.min()/t.proposta.max():.2f}) | atual razao {t.atual.min()/t.atual.max():.2f}")
    print(t.round(3).drop(columns="razao_menor_maior").to_string())

print("\n== alerta antecipado (contratos com 18+ meses)")
par = read_sql("select id_pedido, numero_parcela, dias_atraso from hackathon.parcelas where numero_parcela <= 6")
early = par.groupby("id_pedido").dias_atraso.max().fillna(0) > 0
old = o[o.situacao_final.notna() & (o.meses_desde_pedido >= 18)].copy()
old["atrasou_6"] = old.id_pedido.map(early).fillna(False)
g = old.groupby("atrasou_6").calote.agg(["size", "mean"]); print(g.round(3))
print("share of defaults flagged by early delay:", round(old[old.calote == 1].atrasou_6.mean(), 3))
par3 = par[par.numero_parcela <= 3].groupby("id_pedido").dias_atraso.max().fillna(0) > 0
old["atrasou_3"] = old.id_pedido.map(par3).fillna(False)
print(old.groupby("atrasou_3").calote.agg(["size", "mean"]).round(3)); print("captura 3:", round(old[old.calote == 1].atrasou_3.mean(), 3))

print("\n== demo: candidatos")
show = ["id_pedido", "valor_solicitado", "prazo_meses", "renda_declarada", "score", "restricoes_ativas", "saidas_sobre_entradas",
        "cheque_recente_meses", "dreno", "parcela_sobre_folga", "current_decision", "decision", "denied_at", "default_risk"]
pick = {
  "aprova_que_atual_nega_score": new[(new.decision == "APROVADO") & (new.current_decision == "NEGADO") & (new.score <= 600)].nsmallest(2, "default_risk"),
  "nega_gasta_tudo_atual_aprova": new[(new.current_decision == "APROVADO") & (new.saidas_sobre_entradas > 0.9)].head(2),
  "nega_conta_esvaziada_atual_aprova": new[(new.current_decision == "APROVADO") & (new.dreno >= 3)].head(2),
  "nega_risco_atual_aprova": new[(new.current_decision == "APROVADO") & (new.denied_at == "Risco estimado pela IA")].nlargest(2, "default_risk"),
  "ambos_aprovam_baixo_risco": new[(new.decision == "APROVADO") & (new.current_decision == "APROVADO")].nsmallest(1, "default_risk"),
}
for k, v in pick.items():
    print("--", k); print(v[show].round(3).to_string(index=False))
