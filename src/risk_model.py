"""Risk model: probability that an approved loan ends in default (inadimplente).

    python -m src.risk_model                 # train, validate, save artifacts/
    python -m src.risk_model --maturity 15   # sensitivity: only contracts with >= 15 months

Trained on historical approved loans (current policy + pilot) old enough to show their
outcome. Features are computed at the APPROVED amount, because the outcome depends on it.
Late payment is not predictable in this data (AUC ~0.51), so P(late) is a fixed rate.
"""
import argparse
import json

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import config
from src.features import (
    AMOUNT_FEATURES,
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    features_at,
    load_orders,
    model_matrix,
)

MATURITY_MONTHS = 12
VALIDATION_START = pd.Timestamp("2025-07-01")  # temporal holdout: orders from here on
CV_FOLDS = 5
SHUFFLE_SEEDS = 10
INCREASING = {*AMOUNT_FEATURES, "outras_sobre_renda"}  # risk can only grow with the burden
MODEL_FILE = config.ARTIFACTS / "risk_model.joblib"
OOF_FILE = config.ARTIFACTS / "risk_oof.csv"
METRICS_FILE = config.ARTIFACTS / "risk_metrics.json"
PARAMS = dict(
    objective="binary",
    learning_rate=0.03,
    num_leaves=15,
    min_child_samples=30,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=config.RANDOM_STATE,
    verbose=-1,
)


def training_set(orders: pd.DataFrame, maturity: int = MATURITY_MONTHS) -> pd.DataFrame:
    mature = orders[orders.situacao_final.notna() & (orders.meses_desde_pedido >= maturity)]
    return features_at(mature, mature.valor_aprovado)


def _estimator(n_estimators: int, monotone: bool = True) -> lgb.LGBMClassifier:
    columns = MODEL_FEATURES + CATEGORICAL_FEATURES
    constraints = [1 if monotone and column in INCREASING else 0 for column in columns]
    return lgb.LGBMClassifier(n_estimators=n_estimators, monotone_constraints=constraints, **PARAMS)


def fit(x: pd.DataFrame, y: pd.Series, n_estimators: int) -> lgb.LGBMClassifier:
    return _estimator(n_estimators).fit(x, y)


def predict(model: lgb.LGBMClassifier, df: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(model_matrix(df))[:, 1]


def calibration_table(actual, predicted, edges=(0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0)) -> list[dict]:
    frame = pd.DataFrame({"actual": actual, "predicted": predicted})
    frame["band"] = pd.cut(frame.predicted, list(edges), include_lowest=True)
    rows = []
    for band, group in frame.groupby("band", observed=True):
        rows.append(
            {
                "band": f"{max(band.left, 0):.0%}–{band.right:.0%}",
                "orders": int(len(group)),
                "predicted": float(group.predicted.mean()),
                "observed": float(group.actual.mean()),
            }
        )
    return rows


def temporal_validation(train: pd.DataFrame) -> dict:
    """Train on older orders, test on newer ones: the honest estimate of quality."""
    old = train[train.data_pedido < VALIDATION_START]
    new = train[train.data_pedido >= VALIDATION_START]
    model = _estimator(2000).fit(
        model_matrix(old),
        old.calote,
        eval_X=model_matrix(new),
        eval_y=new.calote,
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    best = max(50, int(model.best_iteration_ or 300))
    predicted = predict(model, new)
    # Leakage check: with a shuffled target nothing should be learnable (AUC ~0.5). Without
    # monotone constraints (they inject the "more burden = more risk" prior) and averaged
    # over seeds: half of the test defaults sit in one extreme cluster, so a single noise
    # model can land far from 0.5 by chance.
    shuffled_aucs = []
    for seed in range(SHUFFLE_SEEDS):
        noise = _estimator(best, monotone=False).fit(
            model_matrix(old), old.calote.sample(frac=1, random_state=seed).to_numpy()
        )
        shuffled_aucs.append(float(roc_auc_score(new.calote, predict(noise, new))))
    return {
        "best_iteration": best,
        "train_orders": int(len(old)),
        "test_orders": int(len(new)),
        "test_period": f"{new.data_pedido.min():%Y-%m} a {new.data_pedido.max():%Y-%m}",
        "auc": float(roc_auc_score(new.calote, predicted)),
        "auc_score_bureau": float(roc_auc_score(new.calote, -new.score)),
        "auc_shuffled_target_mean": float(np.mean(shuffled_aucs)),
        "auc_shuffled_target_range": [min(shuffled_aucs), max(shuffled_aucs)],
        "calibration": calibration_table(new.calote, predicted),
    }


def fold_blocks(train: pd.DataFrame) -> pd.Series:
    """Fold number per order: CV_FOLDS blocks of consecutive months."""
    months = train.data_pedido.dt.to_period("M")
    return pd.Series(pd.factorize(months, sort=True)[0], index=train.index) * CV_FOLDS // months.nunique()


def out_of_fold(train: pd.DataFrame, n_estimators: int) -> pd.Series:
    """Prediction for every mature order from a model that did not see it, used to check
    the historical simulation."""
    blocks = fold_blocks(train)
    oof = pd.Series(np.nan, index=train.index)
    for fold in range(CV_FOLDS):
        held = blocks == fold
        model = fit(model_matrix(train[~held]), train.calote[~held], n_estimators)
        oof[held] = predict(model, train[held])
    return oof


def is_trained() -> bool:
    return MODEL_FILE.exists() and METRICS_FILE.exists()


def train_and_save(maturity: int = MATURITY_MONTHS, save: bool = True) -> dict:
    """Trains, validates and (optionally) saves the model and its metrics in artifacts/.
    Deterministic: the same data always gives the same model."""
    orders = load_orders()
    train = training_set(orders, maturity)
    validation = temporal_validation(train)
    n_estimators = validation["best_iteration"]
    oof = out_of_fold(train, n_estimators)
    final = fit(model_matrix(train), train.calote, n_estimators)

    metrics = {
        "maturity_months": maturity,
        "trained_orders": int(len(train)),
        "trained_until": f"{train.data_pedido.max():%Y-%m-%d}",
        "default_rate": float(train.calote.mean()),
        "late_rate": float(train.situacao_final.isin(["em_atraso", "quitado_com_atraso"]).mean()),
        "temporal_validation": validation,
        "auc_out_of_fold": float(roc_auc_score(train.calote, oof)),
        "features": MODEL_FEATURES + CATEGORICAL_FEATURES,
    }
    if save:
        config.ARTIFACTS.mkdir(exist_ok=True)
        joblib.dump(final, MODEL_FILE)
        oof.rename("p_calote_oof").to_csv(OOF_FILE, index_label="id_pedido")
        METRICS_FILE.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--maturity", type=int, default=MATURITY_MONTHS)
    parser.add_argument("--no-save", action="store_true", help="so mostra as metricas")
    args = parser.parse_args()

    metrics = train_and_save(args.maturity, save=not args.no_save)
    print(json.dumps({k: v for k, v in metrics.items() if k != "features"}, indent=2, ensure_ascii=False))
    if not args.no_save:
        print(f"Gravado {MODEL_FILE.name}, {OOF_FILE.name}, {METRICS_FILE.name} em artifacts/")


if __name__ == "__main__":
    main()
