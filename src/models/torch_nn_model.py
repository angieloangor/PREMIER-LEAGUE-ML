from __future__ import annotations

from .torch_nn import TorchTabularClassifier, TorchTabularRegressor
from .base import ModelSpec


def get_model_specs() -> dict[str, ModelSpec]:
    return {
        "torch_regressor": ModelSpec(
            key="torch_regressor",
            stage="regression",
            family="torch_nn",
            build_estimator=lambda: TorchTabularRegressor(verbose=False),
            param_grid={
                "model__hidden_layers": [(64, 32), (128, 64), (128, 64, 32), (256, 128, 64)],
                "model__activation": ["relu", "gelu", "tanh"],
                "model__dropout": [0.0, 0.1, 0.2, 0.3],
                "model__batch_norm": [False, True],
                "model__learning_rate": [3e-4, 5e-4, 1e-3, 2e-3],
                "model__batch_size": [32, 64, 128],
                "model__weight_decay": [0.0, 1e-5, 1e-4, 1e-3, 1e-2],
                "model__epochs": [80, 100],
                "model__patience": [10, 14, 18],
            },
            serializer="pt",
            preprocessor="linear",
            description="PyTorch MLP regressor for total goals.",
        ),
        "torch_classifier": ModelSpec(
            key="torch_classifier",
            stage="classification",
            family="torch_nn",
            build_estimator=lambda: TorchTabularClassifier(verbose=False),
            param_grid={
                "model__hidden_layers": [(64, 32), (128, 64), (128, 64, 32), (256, 128, 64)],
                "model__activation": ["relu", "gelu", "tanh"],
                "model__dropout": [0.0, 0.1, 0.2, 0.3],
                "model__batch_norm": [False, True],
                "model__learning_rate": [3e-4, 5e-4, 1e-3, 2e-3],
                "model__batch_size": [32, 64, 128],
                "model__weight_decay": [0.0, 1e-5, 1e-4, 1e-3, 1e-2],
                "model__epochs": [80, 100],
                "model__patience": [10, 14, 18],
            },
            serializer="pt",
            preprocessor="linear",
            description="PyTorch MLP classifier for match result.",
        ),
    }
