"""Decision dashboard. Reads artifacts/ produced by `python -m src.train`.

    streamlit run app.py
"""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

import config

st.set_page_config(page_title="Painel de decisão", layout="wide")

REQUIRED = ["metrics.json", "predictions.csv", "factors.csv", "factor_profiles.json"]
if not all((config.ARTIFACTS / name).exists() for name in REQUIRED):
    st.info("Sem resultados ainda. Rode `python -m src.train` e recarregue a página.")
    st.stop()

metrics = json.loads((config.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
profiles = json.loads((config.ARTIFACTS / "factor_profiles.json").read_text(encoding="utf-8"))
predictions = pd.read_csv(config.ARTIFACTS / "predictions.csv")
factors = pd.read_csv(config.ARTIFACTS / "factors.csv")
explanation_file = config.ARTIFACTS / "explanation.md"

is_classification = metrics["task"] == "classification"
scored = predictions[predictions["split"] != "train"]
test_metrics = metrics["test_metrics"]

st.title("Painel de decisão")
st.caption(f"Unidade analisada: {config.ENTITY_LABEL} · Resultado previsto: {config.POSITIVE_LABEL}")

st.header("1. O que está acontecendo")
if is_classification:
    threshold = st.slider("Considerar em risco a partir do score", 0.05, 0.95, 0.50, 0.05)
    at_risk = scored[scored["score"] >= threshold]
    columns = st.columns(4)
    columns[0].metric(f"{config.ENTITY_LABEL.capitalize()}s avaliados", f"{len(scored):,}")
    columns[1].metric("Taxa histórica", f"{test_metrics['base_rate']:.1%}")
    columns[2].metric("Em risco", f"{len(at_risk):,}", f"{len(at_risk) / len(scored):.1%} do total")
    columns[3].metric(
        "Acerto nos 10% de maior score",
        f"{test_metrics['precision_top_10pct']:.0%}",
        f"{test_metrics['lift_top_10pct']:.1f}x a taxa histórica",
    )
else:
    threshold = None
    at_risk = scored
    columns = st.columns(3)
    columns[0].metric(f"{config.ENTITY_LABEL.capitalize()}s avaliados", f"{len(scored):,}")
    columns[1].metric("Previsão média", f"{scored['score'].mean():,.2f}")
    columns[2].metric("Erro médio absoluto", f"{test_metrics['mae']:,.2f}")

st.plotly_chart(
    px.histogram(scored, x="score", nbins=40, title="Distribuição do score"),
    width="stretch",
)

st.header("2. Por quê")
left, right = st.columns(2)
with left:
    top = factors.head(10).sort_values("importance_pct")
    st.plotly_chart(
        px.bar(
            top,
            x="importance_pct",
            y="feature",
            orientation="h",
            hover_data=["direction"],
            title="Peso de cada fator na previsão (%)",
        ),
        width="stretch",
    )
with right:
    chosen = st.selectbox("Detalhar fator", list(profiles))
    profile = pd.DataFrame(profiles[chosen])
    st.plotly_chart(
        px.bar(
            profile,
            x="group",
            y="average_outcome",
            hover_data=["count"],
            title=f"Resultado médio por faixa de {chosen}",
        ),
        width="stretch",
    )

if explanation_file.exists():
    st.markdown(explanation_file.read_text(encoding="utf-8"))
else:
    st.caption("Explicação em linguagem de negócio: rode `python -m src.explain`.")

st.header("3. O que fazer")
limit = st.number_input("Quantos priorizar", 10, max(10, len(at_risk)), min(100, max(10, len(at_risk))))
priority = at_risk.sort_values("score", ascending=False).head(int(limit))
st.dataframe(
    priority[[config.ID_COLUMN, "score", "top_factors"]].rename(
        columns={"top_factors": "principais motivos"}
    ),
    width="stretch",
    hide_index=True,
)
st.download_button(
    "Baixar lista priorizada (CSV)",
    priority.to_csv(index=False).encode("utf-8"),
    "lista_priorizada.csv",
    "text/csv",
)
