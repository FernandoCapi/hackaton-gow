"""Baseline model: dataset -> LightGBM -> metrics, predictions and factors in artifacts/.

    python -m src.train
"""
import json

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn import metrics as skm
from sklearn.model_selection import train_test_split

import config
from src.db import load_dataset

TOP_FACTORS_PER_ROW = 3
PROFILED_FACTORS = 8
MAX_CATEGORIES = 50


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    excluded = {config.TARGET, config.ID_COLUMN, config.DATE_COLUMN, *config.DROP_COLUMNS}
    features = df[[c for c in df.columns if c not in excluded]].copy()

    for column in list(features.columns):
        series = features[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            print(f"  ignorada (data; derive a feature no SQL): {column}")
            features = features.drop(columns=column)
        elif pd.api.types.is_bool_dtype(series):
            features[column] = series.astype(int)
        elif not pd.api.types.is_numeric_dtype(series):
            as_number = pd.to_numeric(series, errors="coerce")
            if as_number.notna().sum() == series.notna().sum():
                features[column] = as_number.astype(float)
            elif series.nunique() > MAX_CATEGORIES:
                print(f"  ignorada (texto com {series.nunique()} valores distintos): {column}")
                features = features.drop(columns=column)
            else:
                features[column] = series.astype("category")
    return features


def encode_target(target: pd.Series) -> pd.Series:
    if config.TASK == "regression":
        return pd.to_numeric(target, errors="coerce").astype(float)
    labeled = target.dropna()
    classes = sorted(labeled.unique())
    if len(classes) != 2:
        raise SystemExit(f"TARGET precisa ser binario; encontrado: {classes[:10]}")
    print(f"  alvo: {classes[0]} -> 0, {classes[1]} -> 1")
    return target.map({classes[0]: 0.0, classes[1]: 1.0})


def split_labeled(df: pd.DataFrame, target: pd.Series) -> pd.Series:
    """Returns a 'train' / 'test' / 'unlabeled' label per row."""
    split = pd.Series("unlabeled", index=df.index)
    labeled = target.dropna().index
    if config.DATE_COLUMN:
        ordered = df.loc[labeled].sort_values(config.DATE_COLUMN).index
        cut = int(len(ordered) * (1 - config.TEST_SIZE))
        train_index, test_index = ordered[:cut], ordered[cut:]
    else:
        train_index, test_index = train_test_split(
            labeled,
            test_size=config.TEST_SIZE,
            random_state=config.RANDOM_STATE,
            stratify=target.loc[labeled] if config.TASK == "classification" else None,
        )
    split.loc[train_index] = "train"
    split.loc[test_index] = "test"
    return split


def fit(features, target, split):
    estimator = lgb.LGBMClassifier if config.TASK == "classification" else lgb.LGBMRegressor
    model = estimator(
        n_estimators=600,
        learning_rate=0.03,
        num_leaves=15,
        min_child_samples=20,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        random_state=config.RANDOM_STATE,
        verbose=-1,
    )
    train, test = split == "train", split == "test"
    model.fit(
        features[train],
        target[train],
        eval_X=features[test],
        eval_y=target[test],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    return model


def predict(model, features) -> np.ndarray:
    if config.TASK == "classification":
        return model.predict_proba(features)[:, 1]
    return model.predict(features)


def evaluate(actual, predicted) -> dict:
    if config.TASK == "regression":
        return {
            "mae": float(skm.mean_absolute_error(actual, predicted)),
            "rmse": float(skm.root_mean_squared_error(actual, predicted)),
            "r2": float(skm.r2_score(actual, predicted)),
        }
    top = max(1, int(len(actual) * 0.10))
    top_index = np.argsort(-predicted)[:top]
    base_rate = float(np.mean(actual))
    precision_top = float(np.mean(np.asarray(actual)[top_index]))
    return {
        "roc_auc": float(skm.roc_auc_score(actual, predicted)),
        "average_precision": float(skm.average_precision_score(actual, predicted)),
        "f1_at_0.5": float(skm.f1_score(actual, predicted >= 0.5)),
        "base_rate": base_rate,
        "precision_top_10pct": precision_top,
        "lift_top_10pct": precision_top / base_rate if base_rate else None,
    }


def contributions(model, features) -> pd.DataFrame:
    """Per-row SHAP values, computed natively by LightGBM (last column is the bias)."""
    values = model.booster_.predict(features, pred_contrib=True)
    return pd.DataFrame(values[:, :-1], columns=features.columns, index=features.index)


def factor_table(contrib: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in contrib.columns:
        direction = "varia por categoria"
        if pd.api.types.is_numeric_dtype(features[column]):
            correlation = np.corrcoef(features[column].fillna(features[column].median()), contrib[column])[0, 1]
            if np.isnan(correlation) or abs(correlation) < 0.1:
                direction = "efeito nao linear"
            else:
                direction = "quanto maior, maior o score" if correlation > 0 else "quanto maior, menor o score"
        rows.append(
            {"feature": column, "importance": float(contrib[column].abs().mean()), "direction": direction}
        )
    table = pd.DataFrame(rows).sort_values("importance", ascending=False).reset_index(drop=True)
    table["importance_pct"] = 100 * table["importance"] / table["importance"].sum()
    return table


def factor_profiles(features, target, top_features) -> dict:
    """Average outcome per group of each top factor. Aggregated: safe to share with an LLM."""
    profiles = {}
    labeled = target.notna()
    for column in top_features:
        series = features.loc[labeled, column]
        if pd.api.types.is_numeric_dtype(series) and series.nunique() > 6:
            groups = pd.qcut(series, 4, duplicates="drop").astype(str)
        else:
            groups = series.astype(str)
        summary = (
            pd.DataFrame({"group": groups, "outcome": target[labeled]})
            .groupby("group", observed=True)["outcome"]
            .agg(["count", "mean"])
            .sort_values("count", ascending=False)
            .head(8)
        )
        profiles[column] = [
            {"group": group, "count": int(row["count"]), "average_outcome": float(row["mean"])}
            for group, row in summary.iterrows()
        ]
    return profiles


def top_reasons(contrib: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    def describe(row_id):
        strongest = contrib.loc[row_id].nlargest(TOP_FACTORS_PER_ROW)
        return "; ".join(
            f"{name}={features.at[row_id, name]}" for name, value in strongest.items() if value > 0
        )

    return pd.Series({row_id: describe(row_id) for row_id in contrib.index})


def main():
    config.ARTIFACTS.mkdir(exist_ok=True)
    df = load_dataset()
    print(f"dataset: {len(df)} linhas, {df.shape[1]} colunas")

    target = encode_target(df[config.TARGET])
    features = prepare_features(df)
    split = split_labeled(df, target)
    model = fit(features, target, split)

    scores = pd.Series(predict(model, features), index=df.index)
    test = split == "test"
    results = {
        "task": config.TASK,
        "target": config.TARGET,
        "split": "temporal" if config.DATE_COLUMN else "aleatorio",
        "rows": {name: int(count) for name, count in split.value_counts().items()},
        "features": list(features.columns),
        "test_metrics": evaluate(target[test].to_numpy(), scores[test].to_numpy()),
    }

    contrib = contributions(model, features[split != "train"])
    factors = factor_table(contrib, features.loc[contrib.index])
    profiles = factor_profiles(features, target, factors["feature"].head(PROFILED_FACTORS))

    predictions = pd.DataFrame(
        {
            config.ID_COLUMN: df[config.ID_COLUMN],
            "score": scores,
            "actual": target,
            "split": split,
            "top_factors": top_reasons(contrib, features),
        }
    ).sort_values("score", ascending=False)

    joblib.dump(model, config.ARTIFACTS / "model.joblib")
    predictions.to_csv(config.ARTIFACTS / "predictions.csv", index=False)
    factors.to_csv(config.ARTIFACTS / "factors.csv", index=False)
    (config.ARTIFACTS / "factor_profiles.json").write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (config.ARTIFACTS / "metrics.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(json.dumps(results["test_metrics"], indent=2))
    print("principais fatores:")
    print(factors.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
