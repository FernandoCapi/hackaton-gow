"""Report to understand, check and defend the decision engine.

    python -m src.evaluate

Writes docs/avaliacao-motor.md (aggregates only, safe to commit) and
artifacts/casos.md (individual orders, never committed).
"""
import pandas as pd
from sklearn.metrics import roc_auc_score

import config
from src.policy import current_policy, decision_steps, proposed_policy, reasons
from src.schemas import PolicyParams
from src.simulate import OUTCOME_RATE, Engine, official_result

REPORT = config.ROOT / "docs" / "avaliacao-motor.md"
CASES = config.ARTIFACTS / "casos.md"


def brl(value: float) -> str:
    sign = "−" if value < 0 else ""
    return f"{sign}R$ {abs(value):,.0f}".replace(",", ".")


def num(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def dec(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%".replace(".", ",").replace("-", "−")


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def section_ruler(engine: Engine) -> str:
    hist = engine.orders[engine.orders.politica_aplicada.eq("atual")]
    current = current_policy(hist, reduce_amount=True)
    match = (current.current_decision.str.lower() == hist.decisao).mean()
    approved = hist.decisao.eq("aprovado")
    diff = (current.current_amount[approved] - hist.valor_aprovado[approved]).abs().max()
    example = official_result([10000, 6000, 5000, 0], ["quitado_em_dia", "quitado_com_atraso", "inadimplente", "inadimplente"])
    mature = engine.hist_grid.orders
    cut = mature.valor_aprovado < mature.valor_solicitado - 0.005
    return f"""## 1. A régua está certa?

- A política atual, reescrita em código, reproduz **{pct(match)}** das {num(len(hist))} decisões
  históricas tomadas por ela (diferença máxima de valor: R$ {dec(diff)}, arredondamento). No histórico,
  quando a parcela passava de 30% da renda, o valor aparece cortado até caber.
- **A régua de comparação é a regra que nega.** A Fortuna confirmou que hoje a regra é "sim ou não":
  quando a parcela do valor pedido passa de 30% da renda, nega. Todas as comparações deste relatório,
  do painel e da API usam essa regra. Ela tira da conta da política atual os {num(int(cut.sum()))} contratos
  maduros que tiveram o valor cortado ({pct(float(mature.calote[cut].mean()))} de calote).
- O pontuador aplica a regra do manual: o exemplo de 4 pedidos dá **{brl(example)}** (manual: −R$ 1.200).
- Como cada desfecho histórico vale na simulação (por real aprovado):
  em dia {pct(OUTCOME_RATE['quitado_em_dia'], 0)}, quitado com atraso {pct(OUTCOME_RATE['quitado_com_atraso'], 0)},
  inadimplente {pct(OUTCOME_RATE['inadimplente'], 0)}; **em atraso** vale {pct(OUTCOME_RATE['em_atraso'])}, porque
  20–32% desses contratos ainda terminam em calote (auditoria).
"""


def section_model(engine: Engine) -> str:
    m = engine.metrics
    v = m["temporal_validation"]
    calibration = table(
        ["Faixa prevista", "Pedidos", "Previsto", "Observado"],
        [[c["band"], c["orders"], pct(c["predicted"]), pct(c["observed"])] for c in v["calibration"]],
    )
    low, high = v["auc_shuffled_target_range"]
    return f"""## 2. O modelo enxerga risco?

Treinado em {num(m['trained_orders'])} contratos aprovados com pelo menos {m['maturity_months']} meses de vida
(calote médio {pct(m['default_rate'])}). Teste honesto: treino com pedidos anteriores a jul/2025 e teste em
{v['test_orders']} pedidos de {v['test_period']}, que o modelo nunca viu.

| Medida (0,5 = sorteio, 1 = perfeito) | Valor |
|---|---|
| Modelo, pedidos nunca vistos | **{dec(v['auc'])}** |
| Score do bureau (régua da política atual) | {dec(v['auc_score_bureau'])} |
| Modelo em validação cruzada por blocos de meses | {dec(m['auc_out_of_fold'])} |
| Modelo treinado com o alvo embaralhado (teste de vazamento) | {dec(v['auc_shuffled_target_mean'])} (de {dec(low)} a {dec(high)}) |

Calibração no teste (o risco previsto bate com o observado?):

{calibration}

Leitura: o modelo prevê um pouco **acima** do observado entre 5% e 15%. É esperado: os contratos do teste
têm só 12 a 15 meses de vida, e o calote ainda cresce até ~18 meses. O modelo foi treinado com contratos
mais longos e estima o risco do contrato inteiro, que é o que a nota mede. Na faixa de decisão (15–20%) o
previsto e o observado ficam próximos.
"""


def section_backtest(engine: Engine, result) -> str:
    h, n = result.historical, result.new_orders
    steps = table(
        ["Passo", "Novos negados nele", "Histórico sem o passo", "Novos sem o passo"],
        [[s.step, s.denied_new_orders, brl(s.historical_gain_if_removed), brl(s.new_orders_gain_if_removed)]
         for s in result.steps_impact],
    )
    bands = table(
        ["Risco previsto", "Contratos", "Calote observado", "Atual", "Proposta"],
        [[b.band, num(b.orders), pct(b.observed_default_rate), brl(b.current_result), brl(b.proposed_result)]
         for b in result.by_risk_band],
    )
    d = engine.decide_new(result.params)
    ours, theirs = d.decision.eq("APROVADO"), d.current_decision.eq("APROVADO")
    effect = lambda m: float(d.expected_profit[m].sum() - d.current_expected_profit[m].sum())
    gain_sources = table(
        ["Grupo", "Pedidos", "Efeito no resultado", "Risco médio de calote"],
        [
            ["Aprovamos quem a regra atual nega", num(int((ours & ~theirs).sum())), brl(effect(ours & ~theirs)),
             pct(float(d.default_risk[ours & ~theirs].mean()))],
            ["Negamos quem a regra atual aprova", num(int((~ours & theirs).sum())),
             f"evita {brl(effect(~ours & theirs))}", pct(float(d.current_risk[~ours & theirs].mean()))],
            ["As duas aprovam", num(int((ours & theirs).sum())), brl(effect(ours & theirs)),
             pct(float(d.default_risk[ours & theirs].mean()))],
        ],
    )
    weighted = lambda risk, amount, m: float((risk[m] * amount[m]).sum() / amount[m].sum())
    portfolio = table(
        ["Carteira aprovada (novos)", "Política atual", "Proposta"],
        [
            ["Aprovação", f"{num(int(theirs.sum()))} ({pct(float(theirs.mean()))})",
             f"{num(int(ours.sum()))} ({pct(float(ours.mean()))})"],
            ["Calote esperado (por pedido)", pct(float(d.current_risk[theirs].mean())), pct(float(d.default_risk[ours].mean()))],
            ["Calote esperado (ponderado pelo valor)", pct(weighted(d.current_risk, d.current_amount, theirs)),
             pct(weighted(d.default_risk, d.approved_amount, ours))],
        ],
    )
    return f"""## 3. Quanto ganhamos e de onde vem?

**Histórico (desfecho real)** — {num(len(engine.hist_grid.orders))} contratos maduros, cada um avaliado por um
modelo que não o viu no treino:

| | Política atual | Proposta |
|---|---|---|
| Aprovados | {num(h.approved_current)} | {num(h.approved_proposed)} |
| Resultado (+15% / +5% / −60%) | {brl(h.current_result)} | {brl(h.proposed_result)} |
| **Ganho** | | **{brl(h.gain)}** |

A proposta evitaria {h.defaults_avoided} calotes que a política atual aprovou.

Por faixa de risco previsto:

{bands}

**Pedidos novos (estimado pelo modelo)** — a melhor previsão da nota de 40%:

| | Política atual | Proposta |
|---|---|---|
| Aprovados | {num(n.current_approved)} | {num(n.approved)} |
| Resultado esperado | {brl(n.current_expected_result)} | {brl(n.expected_result)} |
| **Ganho esperado** | | **{brl(n.expected_gain)}** |

{n.changed_vs_current} dos 2.000 pedidos têm decisão ou valor diferente da política atual.

**De onde vem o ganho nos pedidos novos:**

{gain_sources}

{portfolio}

**Quanto vale cada passo** (quanto o resultado mudaria sem ele; negativo = o passo protege dinheiro):

{steps}

Como ler: no histórico, o desfecho é real; nos pedidos novos, é o modelo julgando a si mesmo. Por isso,
desligar o passo de risco "ganha" nos novos (o modelo acha que todo pedido com lucro esperado positivo
vale a pena) e perde no histórico (na vida real, esses pedidos dão prejuízo). Os filtros de aperto valem
pouco em R$ porque o modelo já enxerga esses sinais; ficam porque explicam a decisão ao analista.
"""


def section_sensitivity(engine: Engine) -> str:
    rows = []
    for cut in [0.08, 0.10, 0.12, 0.15, 0.17, 0.20, 0.25]:
        r = engine.simulate(PolicyParams(risk_cutoff=cut, risk_cutoff_expansion=min(cut, 0.12)), with_steps=False)
        rows.append([pct(cut, 0), brl(r.historical.gain), r.new_orders.approved, brl(r.new_orders.expected_gain)])
    commitment = []
    for cap in [0.15, 0.20, 0.25, 0.30, 0.35]:
        r = engine.simulate(PolicyParams(max_commitment=cap), with_steps=False)
        commitment.append([pct(cap, 0), brl(r.historical.gain), r.new_orders.approved, brl(r.new_orders.expected_gain)])
    expansion = []
    for cut in [0.0, 0.08, 0.10, 0.12, 0.15]:
        r = engine.simulate(PolicyParams(risk_cutoff_expansion=cut), with_steps=False)
        expansion.append([pct(cut, 0), r.new_orders.approved, brl(r.new_orders.expected_gain)])
    headers = ["Valor", "Ganho no histórico", "Aprovados (novos)", "Ganho esperado (novos)"]
    return f"""## 4. O resultado é estável?

Risco máximo de calote (para quem a política atual aprovaria):

{table(headers, rows)}

Teto da parcela sobre a renda efetiva:

{table(headers, commitment)}

Risco máximo para quem a política atual negaria (0% = não expandir):

{table(["Valor", "Aprovados (novos)", "Ganho esperado (novos)"], expansion)}

Leitura: o ganho deve variar pouco perto dos valores escolhidos. Se o melhor resultado estivesse num
extremo da tabela, a régua estaria errada.
"""


def section_amount_rule(engine: Engine) -> str:
    rows = []
    for rule, label in [("full_or_deny", "Valor pedido ou nega"), ("maximize_expected_profit", "Reduzir até caber")]:
        r = engine.simulate(PolicyParams(amount_rule=rule), with_steps=False)
        rows.append([label, brl(r.historical.gain), r.new_orders.approved,
                     brl(r.new_orders.total_approved_amount), brl(r.new_orders.expected_gain)])
    return f"""## 5. Negar ou reduzir o valor?

{table(["Regra", "Ganho no histórico", "Aprovados (novos)", "Volume (novos)", "Ganho esperado (novos)"], rows)}

Ressalva: no histórico, quem teve o valor reduzido ficou com parcela em 30% exatos da renda e deu 56% de
calote; reduções mais fundas quase não existem (5 casos). O ganho de "reduzir" vem do modelo
extrapolando. Por isso o padrão é "valor pedido ou nega" até o cliente confirmar como o desfecho reage
a um valor menor.
"""


def section_pilot(engine: Engine) -> str:
    """Pilot loans are younger than 12 months, so the final model never saw them."""
    grid = engine.pilot_grid
    pilot = grid.orders
    decisions = proposed_policy(grid, PolicyParams())
    frame = decisions.join(pilot[["calote", "meses_desde_pedido"]])
    rows = []
    for name, mask in [
        ("Atual negaria, proposta aprova", frame.current_decision.eq("NEGADO") & frame.decision.eq("APROVADO")),
        ("Atual negaria, proposta nega", frame.current_decision.eq("NEGADO") & frame.decision.eq("NEGADO")),
        ("Atual aprovaria, proposta aprova", frame.current_decision.eq("APROVADO") & frame.decision.eq("APROVADO")),
        ("Atual aprovaria, proposta nega", frame.current_decision.eq("APROVADO") & frame.decision.eq("NEGADO")),
    ]:
        if mask.any():
            rows.append([name, int(mask.sum()), pct(frame.calote[mask].mean())])
    auc = roc_auc_score(frame.calote, grid.current_risk)
    return f"""## 6. A expansão para quem a política atual nega se sustenta?

O piloto (sorteado, out/2025 a mar/2026) é a única evidência sobre quem a política atual nega. Seus
{num(len(pilot))} contratos têm de {frame.meses_desde_pedido.min():.0f} a {frame.meses_desde_pedido.max():.0f} meses de vida:
**o calote observado ainda é parcial** (cerca de metade a três quartos do final). O modelo nunca viu
esses contratos; mesmo assim separa bons e maus com {dec(auc)}.

{table(["Grupo do piloto", "Contratos", "Calote até agora"], rows)}

Leitura: o grupo que a proposta aprova e a atual negaria deve ter calote parecido ou menor que o
grupo que as duas aprovam. Clientes com restrição ativa ficam negados por padrão: o modelo foi
treinado só com contratos sem restrição e o piloto mostrou 19–23% de calote nesse grupo.
"""


def section_patterns(engine: Engine) -> str:
    from src.patterns import compute_patterns

    titles = {
        "risk": "Onde a política atual aprova e perde dinheiro (ou onde ela acerta)",
        "opportunity": "Onde a política atual nega quem pagaria",
        "trap": "Parecem perigosos, mas não são",
    }
    patterns = compute_patterns(engine.orders)
    blocks = []
    for kind, title in titles.items():
        lines = [f"**{title}**", ""]
        for p in (p for p in patterns if p.kind == kind):
            new = f" Pedidos novos no grupo: {num(p.new_orders_affected)}." if p.new_orders_affected is not None else ""
            step = f" Passo da política: {p.policy_step}." if p.policy_step else ""
            lines.append(f"- {p.sentence}{new}{step}")
            if p.caveat:
                lines.append(f"  - Ressalva: {p.caveat}")
        blocks.append("\n".join(lines))
    return "## 8. Padrões que o painel mostra\n\nOs mesmos que a API serve em `/v1/patterns`, calculados por `src/patterns.py` com as\n" \
           "definições do motor. Base: contratos com 12+ meses, ou o piloto quando indicado.\n\n" + "\n\n".join(blocks) + "\n"


def section_leakage() -> str:
    from src.features import MODEL_FEATURES

    return f"""## 7. Há vazamento?

- O modelo usa só esta lista fechada, toda conhecida no dia do pedido: {', '.join(f'`{f}`' for f in MODEL_FEATURES)}
  e `tipo_vinculo`. O extrato termina no mês anterior ao pedido.
- Ficam de fora: decisão, valor aprovado, política aplicada, situação final, parcelas (vazam o desfecho) e
  gênero, CEP, estado civil, idade e profissão (atributos sensíveis ou sem sinal).
- Com o alvo embaralhado o modelo cai para ~0,5 (seção 2): não há atalho escondido nos dados.
- Nenhuma variável sozinha passa de 0,76; a mais forte é a parcela sobre a sobra do mês.
"""


def write_cases(engine: Engine, params: PolicyParams) -> None:
    decisions = engine.decide_new(params)
    changed = decisions[decisions.changed_vs_current]
    picks = pd.concat([
        changed[changed.decision.eq("APROVADO")].sample(min(5, (changed.decision == "APROVADO").sum()), random_state=1),
        changed[changed.decision.eq("NEGADO")].sample(min(5, (changed.decision == "NEGADO").sum()), random_state=1),
    ])
    lines = ["# Casos em que a proposta muda a decisão da política atual", "",
             "Arquivo local (artifacts/, fora do git): contém pedidos individuais.", ""]
    for order_id, row in picks.iterrows():
        o = engine.new_grid.orders.loc[order_id]
        lines.append(f"## {order_id} — atual: {row.current_decision} {brl(row.current_amount)} → "
                     f"proposta: {row.decision} {brl(row.approved_amount)}")
        lines += [f"- Passo {s['order']} ({s['title']}): {s['result']} — {s['detail']}" for s in decision_steps(row, o, params)]
        lines += [f"- Fato: {fact}" for fact in reasons(o)]
        lines.append("")
    config.ARTIFACTS.mkdir(exist_ok=True)
    CASES.write_text("\n".join(lines), encoding="utf-8")


def main():
    engine = Engine()
    params = PolicyParams()
    result = engine.simulate(params)
    sections = [
        "# Avaliação do motor de decisão",
        "",
        "Gerado por `python -m src.evaluate` com os parâmetros padrão. Só números agregados.",
        "Casos individuais para conferência: `artifacts/casos.md` (local, fora do git).",
        "",
        section_ruler(engine),
        section_model(engine),
        section_backtest(engine, result),
        section_sensitivity(engine),
        section_amount_rule(engine),
        section_pilot(engine),
        section_leakage(),
        section_patterns(engine),
    ]
    REPORT.write_text("\n".join(sections), encoding="utf-8", newline="\n")
    write_cases(engine, params)
    print(f"Gravado {REPORT.relative_to(config.ROOT)} e {CASES.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
