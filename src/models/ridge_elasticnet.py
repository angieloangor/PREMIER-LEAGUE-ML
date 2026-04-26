from __future__ import annotations

from sklearn.linear_model import ElasticNet, LinearRegression, LogisticRegression, Ridge, RidgeClassifier

from .base import ModelSpec


def get_model_specs() -> dict[str, ModelSpec]:
    return {
        "linear_regression": ModelSpec(
            key="linear_regression",
            stage="regression",
            family="linear",
            build_estimator=lambda: LinearRegression(),
            param_grid={},
            preprocessor="linear",
            description="Plain linear regression for total goals with no hyperparameter search.",
        ),
        "ridge_regressor": ModelSpec(
            key="ridge_regressor",
            stage="regression",
            family="ridge",
            build_estimator=lambda: Ridge(),
            param_grid={
                "model__alpha": [0.01, 0.1, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0],
            },
            preprocessor="linear",
            description="Ridge regression for total goals.",
        ),
        "ridge_classifier": ModelSpec(
            key="ridge_classifier",
            stage="classification",
            family="ridge",
            build_estimator=lambda: RidgeClassifier(),
            param_grid={
                "model__alpha": [0.01, 0.1, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0],
            },
            preprocessor="linear",
            description="Ridge classifier for match result.",
        ),
        "elasticnet_regressor": ModelSpec(
            key="elasticnet_regressor",
            stage="regression",
            family="elasticnet",
            build_estimator=lambda: ElasticNet(max_iter=5000, random_state=42),
            param_grid={
                "model__alpha": [0.0005, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0],
                "model__l1_ratio": [0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95],
            },
            preprocessor="linear",
            description="ElasticNet regression for total goals.",
        ),
        "elasticnet_classifier": ModelSpec(
            key="elasticnet_classifier",
            stage="classification",
            family="elasticnet",
            build_estimator=lambda: LogisticRegression(
                penalty="elasticnet",
                solver="saga",
                max_iter=5000,
                multi_class="auto",
                random_state=42,
            ),
            param_grid={
                "model__C": [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
                "model__l1_ratio": [0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95],
            },
            preprocessor="linear",
            description="Elastic-net multinomial logistic regression for match result.",
        ),
    }
