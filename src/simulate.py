"""Simulation of a policy in reais, current vs proposed, measured two ways:

- realized: mature historical loans (>= 12 months), official scoring (+15% / +5% / -60%)
  applied to what really happened. Risk comes from models that did not see each loan.
  Deny = 0; a smaller amount keeps the real outcome (conservative: no credit for the cut).
- estimated: the 2,000 new orders, expected result from the final model. This is the best
  estimate of the 40% objective score.

    python -m src.simulate     # prints the default policy simulation
"""
import json
from functools import cached_property

import joblib
import numpy as np
import pandas as pd

import config
from src import risk_model
from src.features import load_orders, model_matrix
from src.policy import (
    STEP_CAPACITY,
    STEP_DOMAIN,
    STEP_RISK,
    STEP_STRAIN,
    RiskGrid,
    current_policy,
    proposed_policy,
    step_title,
)
from src.schemas import (
    HistoricalResult,
    NewOrdersResult,
    PolicyParams,
    RiskBand,
    SimulationResult,
    StepImpact,
)

# Result per real for each final status. em_atraso still ends in default 20-32% of the
# time (analysis/findings_auditoria.md): valued at its expectation, not as a late payer.
OUTCOME_RATE = {
    "quitado_em_dia": 0.15,
    "em_dia": 0.15,
    "quitado_com_atraso": 0.05,
    "em_atraso": 0.25 * -0.60 + 0.75 * 0.05,
    "inadimplente": -0.60,
}
RISK_BANDS = [0, 0.05, 0.10, 0.15, 0.20, 0.30, 1.0]


def official_result(amounts, statuses) -> float:
    """Organizer's scoring: sum of approved amount x result rate of the final status."""
    return float(sum(amount * OUTCOME_RATE[status] for amount, status in zip(amounts, statuses) if amount > 0))
STEPS_MEASURED = [STEP_DOMAIN, STEP_STRAIN, STEP_CAPACITY, STEP_RISK]


def _concat(grids: list[RiskGrid]) -> RiskGrid:
    return RiskGrid(
        pd.concat([g.orders for g in grids]),
        np.vstack([g.amounts for g in grids]),
        np.vstack([g.risk for g in grids]),
        np.vstack([g.commitment for g in grids]),
        np.concatenate([g.current_risk for g in grids]),
    )


class Engine:
    """Loads data and model once; every simulation afterwards is array arithmetic."""

    def __init__(self, maturity: int = risk_model.MATURITY_MONTHS):
        self.maturity = maturity
        self.orders = load_orders()
        self.model = joblib.load(risk_model.MODEL_FILE)
        self.metrics = json.loads(risk_model.METRICS_FILE.read_text(encoding="utf-8"))

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(model_matrix(frame))[:, 1]

    @cached_property
    def new_grid(self) -> RiskGrid:
        new = self.orders[self.orders.tipo_base.eq("novo")]
        return RiskGrid.build(new, self.predict)

    @cached_property
    def hist_grid(self) -> RiskGrid:
        """Grid for mature historical loans, each scored by a model trained without it."""
        mature = self.orders[self.orders.situacao_final.notna() & (self.orders.meses_desde_pedido >= self.maturity)]
        train = risk_model.training_set(self.orders, self.maturity)
        blocks = risk_model.fold_blocks(train)
        n_estimators = self.metrics["temporal_validation"]["best_iteration"]
        grids = []
        for fold in sorted(blocks.unique()):
            held = blocks == fold
            model = risk_model.fit(model_matrix(train[~held]), train.calote[~held], n_estimators)
            grids.append(RiskGrid.build(mature[held.to_numpy()], lambda f, m=model: m.predict_proba(model_matrix(f))[:, 1]))
        return _concat(grids)

    @cached_property
    def pilot_grid(self) -> RiskGrid:
        """Approved pilot loans: the only evidence about clients the current policy denies.
        Younger than the training maturity, so the final model never saw them; their default
        is still partial (6-12 months)."""
        o = self.orders
        pilot = o[o.politica_aplicada.eq("piloto") & o.decisao.eq("aprovado")]
        return RiskGrid.build(pilot, self.predict)

    def pilot_gains(self, params: PolicyParams) -> int:
        """Pilot clients the current policy would deny, the proposal approves, and who have
        not defaulted so far."""
        decisions = proposed_policy(self.pilot_grid, params)
        paid = self.pilot_grid.orders.calote.to_numpy() == 0
        gained = decisions.current_decision.eq("NEGADO").to_numpy() & decisions.decision.eq("APROVADO").to_numpy()
        return int((gained & paid).sum())

    @cached_property
    def outcome_rate(self) -> np.ndarray:
        return self.hist_grid.orders.situacao_final.map(OUTCOME_RATE).to_numpy()

    # --- measures ---------------------------------------------------------------------

    def realized(self, decisions: pd.DataFrame) -> tuple[float, float]:
        rate = self.outcome_rate
        proposed = float((decisions.approved_amount.to_numpy() * rate).sum())
        current = float((decisions.current_amount.to_numpy() * rate).sum())
        return proposed, current

    @staticmethod
    def estimated(decisions: pd.DataFrame) -> tuple[float, float]:
        return float(decisions.expected_profit.sum()), float(decisions.current_expected_profit.sum())

    def decide_new(self, params: PolicyParams, disabled: frozenset = frozenset()) -> pd.DataFrame:
        return proposed_policy(self.new_grid, params, disabled)

    def decide_hist(self, params: PolicyParams, disabled: frozenset = frozenset()) -> pd.DataFrame:
        return proposed_policy(self.hist_grid, params, disabled)

    def simulate(self, params: PolicyParams, with_steps: bool = True) -> SimulationResult:
        hist = self.decide_hist(params)
        new = self.decide_new(params)
        hist_proposed, hist_current = self.realized(hist)
        new_proposed, new_current = self.estimated(new)
        defaulted = self.hist_grid.orders.calote.to_numpy() == 1
        approved = hist.decision.eq("APROVADO").to_numpy()
        current_approved = hist.current_decision.eq("APROVADO").to_numpy()

        band_index = np.digitize(self.hist_grid.risk[:, 0], RISK_BANDS[1:-1])
        rate = self.outcome_rate
        by_band = []
        for index, (low, high) in enumerate(zip(RISK_BANDS[:-1], RISK_BANDS[1:])):
            mask = band_index == index
            if not mask.any():
                continue
            by_band.append(
                RiskBand(
                    band=f"{low * 100:.0f}–{high * 100:.0f}%",
                    orders=int(mask.sum()),
                    observed_default_rate=float(defaulted[mask].mean()),
                    current_result=round(float((hist.current_amount.to_numpy() * rate)[mask].sum()), 2),
                    proposed_result=round(float((hist.approved_amount.to_numpy() * rate)[mask].sum()), 2),
                )
            )

        return SimulationResult(
            params=params,
            historical=HistoricalResult(
                current_result=round(hist_current, 2),
                proposed_result=round(hist_proposed, 2),
                gain=round(hist_proposed - hist_current, 2),
                approved_current=int(current_approved.sum()),
                approved_proposed=int(approved.sum()),
                defaults_avoided=int((defaulted & current_approved & ~approved).sum()),
                good_customers_gained=self.pilot_gains(params),
            ),
            new_orders=NewOrdersResult(
                approved=int(new.decision.eq("APROVADO").sum()),
                denied=int(new.decision.eq("NEGADO").sum()),
                total_approved_amount=round(float(new.approved_amount.sum()), 2),
                current_approved=int(new.current_decision.eq("APROVADO").sum()),
                changed_vs_current=int(new.changed_vs_current.sum()),
                expected_result=round(new_proposed, 2),
                current_expected_result=round(new_current, 2),
                expected_gain=round(new_proposed - new_current, 2),
            ),
            by_risk_band=by_band,
            steps_impact=self.steps_impact(params, hist_proposed, new_proposed, new) if with_steps else [],
        )

    def steps_impact(self, params, hist_result, new_result, new_decisions) -> list[StepImpact]:
        impacts = []
        for step in STEPS_MEASURED:
            without = frozenset({step})
            hist_without, _ = self.realized(self.decide_hist(params, without))
            new_without, _ = self.estimated(self.decide_new(params, without))
            impacts.append(
                StepImpact(
                    step=step_title(step, params),
                    denied_new_orders=int(new_decisions.denied_at.eq(step).sum()),
                    historical_gain_if_removed=round(hist_without - hist_result, 2),
                    new_orders_gain_if_removed=round(new_without - new_result, 2),
                )
            )
        return impacts


def main():
    engine = Engine()
    hist = engine.hist_grid.orders
    check = current_policy(hist).join(hist[["decisao", "valor_aprovado", "politica_aplicada"]])
    atual = check[check.politica_aplicada == "atual"]
    print(f"politica atual reproduzida: {(atual.current_decision.str.lower() == atual.decisao).mean():.1%} "
          f"das decisoes, valor dif. max R$ {(atual.current_amount - atual.valor_aprovado).abs().max():.2f}")
    result = engine.simulate(PolicyParams())
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
