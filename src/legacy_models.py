from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import MATCH_RESULT_NAMES

def _split_time_ordered_frame(dataframe: pd.DataFrame, holdout_ratio: float = 0.2):
    split_index = max(int(len(dataframe) * (1 - holdout_ratio)), 1)
    if split_index >= len(dataframe):
        split_index = len(dataframe) - 1
    return dataframe.iloc[:split_index].copy(), dataframe.iloc[split_index:].copy()

def _build_rf_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=7,
                    min_samples_leaf=3,
                    random_state=42,
                    class_weight="balanced_subsample",
                    # Single-threaded for compatibility in restricted Windows sandboxes.
                    n_jobs=1,
                ),
            ),
        ]
    )

def train_xg_models(shots: pd.DataFrame) -> dict[str, object]:
    feature_columns = [
        "distance_to_goal",
        "angle_to_goal",
        "is_big_chance",
        "is_header",
        "is_right_foot",
        "is_left_foot",
        "is_penalty",
        "is_counter_attack",
        "from_corner",
        "is_volley",
        "first_touch",
        "zone_small_box",
        "zone_box_centre",
        "zone_out_of_box",
        "centrality_to_goal",
        "is_regular_play",
        "player_conversion_last20",
    ]
    ordered = shots.sort_values(["kickoff", "match_id", "minute", "second", "id"]).reset_index(drop=True)
    train_df, test_df = _split_time_ordered_frame(ordered, holdout_ratio=0.2)

    logistic = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", max_iter=5000)),
        ]
    )
    rf = _build_rf_pipeline()

    X_train = train_df[feature_columns]
    X_test = test_df[feature_columns]
    y_train = train_df["is_goal"]
    y_test = test_df["is_goal"]

    logistic.fit(X_train, y_train)
    rf.fit(X_train, y_train)

    prob = logistic.predict_proba(X_test)[:, 1]
    pred = logistic.predict(X_test)
    rf_prob = rf.predict_proba(X_test)[:, 1]
    rf_pred = rf.predict(X_test)
    naive_pred = np.zeros(len(y_test), dtype=int)
    fpr, tpr, _ = roc_curve(y_test, prob)

    scored = ordered.copy()
    scored["xg_probability"] = logistic.predict_proba(ordered[feature_columns])[:, 1]

    coef = np.abs(logistic.named_steps["model"].coef_[0])
    importance = pd.DataFrame({"feature": feature_columns, "importance": coef}).sort_values("importance", ascending=False)

    threshold_metrics = {}
    for threshold in [0.3, 0.5, 0.7]:
        y_pred_threshold = (prob >= threshold).astype(int)
        threshold_metrics[str(threshold)] = {
            "accuracy": float(accuracy_score(y_test, y_pred_threshold)),
            "precision": float(precision_score(y_test, y_pred_threshold, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred_threshold, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred_threshold, zero_division=0)),
        }

    return {
        "feature_columns": feature_columns,
        "metrics": {
            "accuracy": float(accuracy_score(y_test, pred)),
            "precision": float(precision_score(y_test, pred, zero_division=0)),
            "recall": float(recall_score(y_test, pred, zero_division=0)),
            "f1": float(f1_score(y_test, pred, zero_division=0)),
            "auc_roc": float(roc_auc_score(y_test, prob)),
            "naive_accuracy": float(accuracy_score(y_test, naive_pred)),
            "naive_auc_roc": 0.5,
            "baseline_always_no_goal_accuracy": float(accuracy_score(y_test, naive_pred)),
        },
        "baseline": {
            "always_no_goal": {
                "accuracy": float(accuracy_score(y_test, naive_pred)),
                "auc_roc": 0.5,
            }
        },
        "threshold_analysis": threshold_metrics,
        "advanced_metrics": {
            "random_forest_accuracy": float(accuracy_score(y_test, rf_pred)),
            "random_forest_auc": float(roc_auc_score(y_test, rf_prob)),
        },
        "roc_curve": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
        "confusion_matrix": confusion_matrix(y_test, pred, labels=[0, 1]).tolist(),
        "test_results": {
            "y_true": y_test.astype(int).tolist(),
            "y_pred": pred.astype(int).tolist(),
            "y_prob": prob.tolist(),
        },
        "feature_importance": importance.to_dict(orient="records"),
        "shots": scored,
    }

def _bet365_pred(frame: pd.DataFrame) -> np.ndarray:
    odds = frame[["b365h", "b365d", "b365a"]].astype(float).to_numpy()
    return np.array(["H", "D", "A"])[np.argmin(odds, axis=1)]

def train_match_models(match_features: pd.DataFrame) -> dict[str, object]:
    ordered = match_features.sort_values(["kickoff", "id"]).reset_index(drop=True)
    train_df, test_df = _split_time_ordered_frame(ordered, holdout_ratio=0.2)
    odds_only_columns = ["b365h", "b365d", "b365a"]
    historical_only_columns = [
        "home_goals_for_last5",
        "home_goals_against_last5",
        "away_goals_for_last5",
        "away_goals_against_last5",
        "home_shots_on_target_last5",
        "away_shots_on_target_last5",
        "away_big_chances_last5",
        "points_diff_last5",
        "pass_accuracy_diff_last5",
        "conversion_rate_diff_last5",
        "big_chance_rate_diff_last5",
    ]
    feature_columns = [*odds_only_columns, *historical_only_columns, "market_entropy_b365"]

    # Match predictor features classification:
    # - seguras pre-partido: b365h, b365d, b365a (odds disponibles antes del kick-off)
    # - seguras pre-partido: rolling history de goles, tiros a puerta y big chances
    # - leakage claro: ninguno de los features usados en `feature_columns`
    # Nota: `build_match_features` calcula atributos adicionales para EDA y dashboard,
    # pero el modelo de partido final se evalúa con odds, histórico y la combinación de ambos.
    odds_only_classifier = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=5000, C=10)),
        ]
    )
    historical_only_classifier = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=5000, C=10)),
        ]
    )
    classifier = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=5000, C=10)),
        ]
    )
    regressor = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LinearRegression()),
        ]
    )
    rf = _build_rf_pipeline()
    cv = TimeSeriesSplit(n_splits=5)

    X_full = ordered[feature_columns]
    X_full_odds = ordered[odds_only_columns]
    X_full_hist = ordered[historical_only_columns]
    y_full = ordered["result_code"]
    y_goals = ordered["total_goals"]
    X_train = train_df[feature_columns]
    X_train_odds = train_df[odds_only_columns]
    X_train_hist = train_df[historical_only_columns]
    X_test = test_df[feature_columns]
    X_test_odds = test_df[odds_only_columns]
    X_test_hist = test_df[historical_only_columns]
    y_train = train_df["result_code"]
    y_test = test_df["result_code"]
    y_train_goals = train_df["total_goals"]
    y_test_goals = test_df["total_goals"]

    cv_cls = cross_validate(
        classifier,
        X_full,
        y_full,
        cv=cv,
        scoring={
            "accuracy": "accuracy",
            "precision_weighted": make_scorer(precision_score, average="weighted", zero_division=0),
            "recall_weighted": make_scorer(recall_score, average="weighted", zero_division=0),
            "f1_weighted": make_scorer(f1_score, average="weighted", zero_division=0),
        },
        n_jobs=None,
    )
    cv_cls_odds = cross_validate(
        odds_only_classifier,
        X_full_odds,
        y_full,
        cv=cv,
        scoring={"accuracy": "accuracy"},
        n_jobs=None,
    )
    cv_cls_hist = cross_validate(
        historical_only_classifier,
        X_full_hist,
        y_full,
        cv=cv,
        scoring={"accuracy": "accuracy"},
        n_jobs=None,
    )
    cv_reg = cross_validate(
        regressor,
        X_full,
        y_goals,
        cv=cv,
        scoring={"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"},
        n_jobs=None,
    )

    classifier.fit(X_train, y_train)
    odds_only_classifier.fit(X_train_odds, y_train)
    historical_only_classifier.fit(X_train_hist, y_train)
    regressor.fit(X_train, y_train_goals)
    rf.fit(X_train, y_train)

    class_pred = classifier.predict(X_test)
    odds_only_pred = odds_only_classifier.predict(X_test_odds)
    hist_pred = historical_only_classifier.predict(X_test_hist)
    reg_pred = regressor.predict(X_test)
    rf_accuracy = float(accuracy_score(y_test, rf.predict(X_test)))
    odds_only_holdout_accuracy = float(accuracy_score(y_test, odds_only_pred))
    historical_only_holdout_accuracy = float(accuracy_score(y_test, hist_pred))
    combined_holdout_accuracy = float(accuracy_score(y_test, class_pred))
    bet365_holdout = float((_bet365_pred(test_df) == test_df["ftr"].to_numpy()).mean())

    bet_cv_scores = []
    for _, test_idx in cv.split(ordered):
        fold = ordered.iloc[test_idx]
        bet_cv_scores.append(float((_bet365_pred(fold) == fold["ftr"].to_numpy()).mean()))
    bet365_cv = float(np.mean(bet_cv_scores))
    full_cv_accuracy = float(np.mean(cv_cls["test_accuracy"]))
    odds_only_cv_accuracy = float(np.mean(cv_cls_odds["test_accuracy"]))
    historical_only_cv_accuracy = float(np.mean(cv_cls_hist["test_accuracy"]))

    class_codes = [0, 1, 2]
    class_labels = MATCH_RESULT_NAMES
    precision_per_class = precision_score(y_test, class_pred, labels=class_codes, average=None, zero_division=0)
    recall_per_class = recall_score(y_test, class_pred, labels=class_codes, average=None, zero_division=0)
    f1_per_class = f1_score(y_test, class_pred, labels=class_codes, average=None, zero_division=0)
    support_per_class = [(y_test == code).sum() for code in class_codes]
    class_metrics = [
        {
            "result": label,
            "precision": float(precision_per_class[idx]),
            "recall": float(recall_per_class[idx]),
            "f1": float(f1_per_class[idx]),
            "support": int(support_per_class[idx]),
        }
        for idx, label in enumerate(class_labels)
    ]

    return {
        "feature_columns": feature_columns,
        "odds_only_feature_columns": odds_only_columns,
        "historical_only_feature_columns": historical_only_columns,
        "holdout_predictions": test_df.assign(
            predicted_result=pd.Series(class_pred, index=test_df.index).map({0: "H", 1: "D", 2: "A"}),
            predicted_total_goals=reg_pred,
            residual_total_goals=test_df["total_goals"] - reg_pred,
        ),
        "confusion_matrix": confusion_matrix(y_test, class_pred, labels=[0, 1, 2]).tolist(),
        "metrics": {
            "accuracy": float(accuracy_score(y_test, class_pred)),
            "precision_weighted": float(precision_score(y_test, class_pred, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_test, class_pred, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_test, class_pred, average="weighted", zero_division=0)),
            "precision_macro": float(precision_score(y_test, class_pred, average="macro", zero_division=0)),
            "recall_macro": float(recall_score(y_test, class_pred, average="macro", zero_division=0)),
            "f1_macro": float(f1_score(y_test, class_pred, average="macro", zero_division=0)),
            "class_metrics": class_metrics,
            "cv_mean_accuracy": full_cv_accuracy,
            "cv_std_accuracy": float(np.std(cv_cls["test_accuracy"])),
            "cv_precision_mean": float(np.mean(cv_cls["test_precision_weighted"])),
            "cv_recall_mean": float(np.mean(cv_cls["test_recall_weighted"])),
            "cv_f1_mean": float(np.mean(cv_cls["test_f1_weighted"])),
            "bet365_holdout_accuracy": bet365_holdout,
            "bet365_cv_accuracy": bet365_cv,
            "odds_only_holdout_accuracy": odds_only_holdout_accuracy,
            "historical_only_holdout_accuracy": historical_only_holdout_accuracy,
            "combined_holdout_accuracy": combined_holdout_accuracy,
            "historical_only_cv_accuracy": historical_only_cv_accuracy,
            "odds_only_cv_accuracy": odds_only_cv_accuracy,
        },
        "linear_metrics": {
            "mae": float(mean_absolute_error(y_test_goals, reg_pred)),
            "rmse": float(np.sqrt(np.mean((y_test_goals - reg_pred) ** 2))),
            "r2": float(regressor.score(X_test, y_test_goals)),
            "cv_mae_mean": float(-np.mean(cv_reg["test_mae"])),
            "cv_rmse_mean": float(-np.mean(cv_reg["test_rmse"])),
            "cv_r2_mean": float(np.mean(cv_reg["test_r2"])),
        },
        "advanced_metrics": {
            "random_forest_accuracy": rf_accuracy,
            "model_comparison": {
                "bet365_holdout_accuracy": bet365_holdout,
                "odds_only_holdout_accuracy": odds_only_holdout_accuracy,
                "historical_only_holdout_accuracy": historical_only_holdout_accuracy,
                "combined_holdout_accuracy": combined_holdout_accuracy,
                "odds_only_cv_accuracy": odds_only_cv_accuracy,
                "historical_only_cv_accuracy": historical_only_cv_accuracy,
                "combined_cv_accuracy": full_cv_accuracy,
                "delta_vs_odds_only_cv": full_cv_accuracy - odds_only_cv_accuracy,
            },
            "ablation": {
                "odds_only_holdout_accuracy": odds_only_holdout_accuracy,
                "odds_plus_form_holdout_accuracy": combined_holdout_accuracy,
                "odds_only_cv_accuracy": odds_only_cv_accuracy,
                "odds_plus_form_cv_accuracy": full_cv_accuracy,
                "delta_cv_accuracy": full_cv_accuracy - odds_only_cv_accuracy,
            },
        },
        "linear_test_results": test_df.assign(
            actual_goals=test_df["total_goals"],
            predicted_goals=reg_pred,
            residuals=(test_df["total_goals"] - reg_pred),
        )[["actual_goals", "predicted_goals", "residuals"]].to_dict(orient="records"),
        "classifier": classifier.fit(X_full, y_full),
        "regressor": regressor.fit(X_full, y_goals),
        "ordered_matches": ordered,
        "full_probabilities": classifier.fit(X_full, y_full).predict_proba(X_full),
        "full_goal_predictions": regressor.fit(X_full, y_goals).predict(X_full),
    }
