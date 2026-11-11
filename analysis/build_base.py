"""Build one analytical row per order (historical + new) for pattern hunting.

    python -m analysis.build_base   -> data/base.parquet
"""
import numpy as np
import pandas as pd

import config
from src.db import read_sql

CUTOFF = pd.Timestamp("2026-09-30")


def price(valor, prazo, i=0.03):
    return valor * i / (1 - (1 + i) ** (-prazo))


def main():
    q = lambda s: read_sql(s)
    ped = q("select * from hackathon.pedidos")
    cli = q("select * from hackathon.clientes")
    bur = q("select * from hackathon.bureau")
    mov = q("select * from hackathon.movimentacao_mensal")
    par = q("select * from hackathon.parcelas")

    df = ped.merge(cli, on="id_cliente", how="left").merge(bur, on="id_pedido", how="left")
    novos_b = pd.read_csv(config.BUREAU_CACHE)
    nb = df.tipo_base.eq("novo")
    df = df.set_index("id_cliente")
    df.loc[nb.values, novos_b.columns[1:]] = novos_b.set_index("id_cliente").loc[df.index[nb.values]].values
    df = df.reset_index()

    for c in ["data_pedido", "data_abertura_conta", "data_nascimento"]:
        df[c] = pd.to_datetime(df[c])
    num = ["renda_declarada", "valor_solicitado", "valor_aprovado", "score", "restricoes_ativas",
           "parcelas_outras_instituicoes", "consultas_90_dias", "meses_historico_bureau"]
    df[num] = df[num].astype(float)

    df["idade"] = (df.data_pedido - df.data_nascimento).dt.days / 365.25
    df["meses_conta"] = (df.data_pedido - df.data_abertura_conta).dt.days / 30.44
    df["parcela_solicitada"] = price(df.valor_solicitado, df.prazo_meses)
    df["comprometimento"] = df.parcela_solicitada / df.renda_declarada
    df["comprometimento_total"] = (df.parcela_solicitada + df.parcelas_outras_instituicoes) / df.renda_declarada
    df["valor_sobre_renda"] = df.valor_solicitado / df.renda_declarada
    df["uf_prefixo_cep"] = df.cep.str[:1]
    df["primeiro_nome_prof"] = df.profissao

    # monthly account movement aggregates
    mov["mes_referencia"] = pd.to_datetime(mov.mes_referencia)
    mc = ["total_entradas", "entradas_salario", "total_saidas", "saldo_medio", "saldo_minimo"]
    mov[mc] = mov[mc].astype(float)
    mov = mov.sort_values(["id_cliente", "mes_referencia"])
    g = mov.groupby("id_cliente")
    agg = pd.DataFrame({
        "mov_meses": g.size(),
        "mov_entradas_med": g.total_entradas.mean(),
        "mov_salario_med": g.entradas_salario.mean(),
        "mov_salario_min": g.entradas_salario.min(),
        "mov_meses_sem_salario": g.entradas_salario.apply(lambda s: (s <= 0).sum()),
        "mov_saidas_med": g.total_saidas.mean(),
        "mov_saldo_medio_med": g.saldo_medio.mean(),
        "mov_saldo_min_min": g.saldo_minimo.min(),
        "mov_cheque_dias_tot": g.dias_cheque_especial.sum(),
        "mov_cheque_meses": g.dias_cheque_especial.apply(lambda s: (s > 0).sum()),
        "mov_entradas_cv": g.total_entradas.std() / g.total_entradas.mean(),
    })
    last3 = mov.groupby("id_cliente").tail(3).groupby("id_cliente")
    agg["mov_entradas_ult3"] = last3.total_entradas.mean()
    agg["mov_saldo_ult3"] = last3.saldo_medio.mean()
    agg["mov_cheque_dias_ult3"] = last3.dias_cheque_especial.sum()
    agg["mov_tendencia_entradas"] = agg.mov_entradas_ult3 / agg.mov_entradas_med
    agg["mov_saidas_sobre_entradas"] = g.total_saidas.sum() / g.total_entradas.sum()
    df = df.merge(agg, left_on="id_cliente", right_index=True, how="left")
    df["renda_comprovada_ratio"] = df.mov_salario_med / df.renda_declarada
    df["entradas_sobre_renda"] = df.mov_entradas_med / df.renda_declarada

    # outcome from installments (historical approved)
    par["data_vencimento"] = pd.to_datetime(par.data_vencimento)
    par["vencida"] = par.data_vencimento <= CUTOFF
    pg = par.groupby("id_pedido")
    out = pd.DataFrame({
        "n_parcelas": pg.size(),
        "n_vencidas": pg.vencida.sum(),
        "max_atraso": pg.dias_atraso.max(),
        "valor_parcela_real": pg.valor_parcela.first().astype(float),
    })
    df = df.merge(out, left_on="id_pedido", right_index=True, how="left")
    df["meses_desde_pedido"] = (CUTOFF - df.data_pedido).dt.days / 30.44
    df["bad"] = np.where(df.situacao_final.notna(), df.situacao_final.eq("inadimplente").astype(float), np.nan)
    df["late"] = np.where(df.situacao_final.notna(),
                          df.situacao_final.isin(["em_atraso", "quitado_com_atraso"]).astype(float), np.nan)
    df["maduro"] = df.meses_desde_pedido >= 10

    # current policy replication
    elig = (df.score > 600) & (df.renda_declarada > 2000) & (df.restricoes_ativas == 0)
    max_val = 0.30 * df.renda_declarada * (1 - 1.03 ** (-df.prazo_meses)) / 0.03
    df["atual_aprova"] = elig & (np.minimum(df.valor_solicitado, max_val) >= 500)
    df["atual_valor"] = np.where(df.atual_aprova, np.floor(np.minimum(df.valor_solicitado, max_val) * 100) / 100, 0)

    config.DATA.mkdir(exist_ok=True)
    df.to_parquet(config.DATA / "base.parquet", index=False)
    print(df.shape)
    print(df.groupby("tipo_base").size())


if __name__ == "__main__":
    main()
