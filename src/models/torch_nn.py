from __future__ import annotations

import copy
import random
from dataclasses import dataclass

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError as exc:  # pragma: no cover - depends on local environment
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None
    _TORCH_IMPORT_ERROR = exc
else:
    _TORCH_IMPORT_ERROR = None


ACTIVATIONS = {
    "relu": lambda: nn.ReLU(),
    "gelu": lambda: nn.GELU(),
    "tanh": lambda: nn.Tanh(),
    "leaky_relu": lambda: nn.LeakyReLU(negative_slope=0.01),
}


@dataclass
class EpochResult:
    train_loss: float
    val_loss: float


def _require_torch() -> None:
    if torch is None:
        raise ImportError("PyTorch no esta instalado. Instala `torch` para usar los modelos NN.") from _TORCH_IMPORT_ERROR


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def create_feedforward_network(
    input_dim: int,
    output_dim: int,
    hidden_layers: tuple[int, ...],
    activation: str,
    dropout: float,
    batch_norm: bool,
) -> nn.Module:
    layers: list[nn.Module] = []
    previous_dim = input_dim
    activation_factory = ACTIVATIONS[activation]

    for hidden_dim in hidden_layers:
        layers.append(nn.Linear(previous_dim, hidden_dim))
        if batch_norm:
            layers.append(nn.BatchNorm1d(hidden_dim))
        layers.append(activation_factory())
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        previous_dim = hidden_dim

    layers.append(nn.Linear(previous_dim, output_dim))
    return nn.Sequential(*layers)


class _BaseTorchEstimator(BaseEstimator):
    def __init__(
        self,
        hidden_layers: tuple[int, ...] = (128, 64),
        activation: str = "relu",
        dropout: float = 0.1,
        batch_norm: bool = False,
        learning_rate: float = 1e-3,
        batch_size: int = 64,
        epochs: int = 100,
        patience: int = 12,
        weight_decay: float = 0.0,
        validation_fraction: float = 0.15,
        random_state: int = 42,
        device: str = "auto",
        verbose: bool = False,
    ) -> None:
        self.hidden_layers = hidden_layers
        self.activation = activation
        self.dropout = dropout
        self.batch_norm = batch_norm
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience
        self.weight_decay = weight_decay
        self.validation_fraction = validation_fraction
        self.random_state = random_state
        self.device = device
        self.verbose = verbose

    def _build_model(self, input_dim: int, output_dim: int) -> nn.Module:
        return create_feedforward_network(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_layers=tuple(self.hidden_layers),
            activation=self.activation,
            dropout=self.dropout,
            batch_norm=self.batch_norm,
        )

    def _split_validation(self, X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if len(X) < 10:
            return X, X, y, y

        split_index = max(int(len(X) * (1 - self.validation_fraction)), 1)
        split_index = min(split_index, len(X) - 1)
        return X[:split_index], X[split_index:], y[:split_index], y[split_index:]

    def _build_loader(self, X: np.ndarray, y: np.ndarray, shuffle: bool) -> DataLoader:
        features = torch.tensor(X, dtype=torch.float32)
        targets = self._target_tensor(y)
        dataset = TensorDataset(features, targets)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=shuffle)

    def _fit_model(self, X: np.ndarray, y: np.ndarray, output_dim: int) -> None:
        _require_torch()
        _set_seed(self.random_state)

        device = _resolve_device(self.device)
        self.device_ = device
        X_train, X_val, y_train, y_val = self._split_validation(X, y)
        train_loader = self._build_loader(X_train, y_train, shuffle=True)
        val_loader = self._build_loader(X_val, y_val, shuffle=False)

        model = self._build_model(X.shape[1], output_dim).to(device)
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        criterion = self._criterion()

        best_state = copy.deepcopy(model.state_dict())
        best_val_loss = float("inf")
        epochs_without_improvement = 0
        history: list[EpochResult] = []

        for epoch in range(1, self.epochs + 1):
            train_loss = self._run_epoch(train_loader, model, optimizer, criterion, device, training=True)
            val_loss = self._run_epoch(val_loader, model, optimizer, criterion, device, training=False)
            history.append(EpochResult(train_loss=train_loss, val_loss=val_loss))

            if self.verbose and (epoch == 1 or epoch % 10 == 0 or epoch == self.epochs):
                print(
                    f"[torch] epoch={epoch:03d} train_loss={train_loss:.4f} "
                    f"val_loss={val_loss:.4f}"
                )

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = copy.deepcopy(model.state_dict())
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= self.patience:
                    break

        model.load_state_dict(best_state)
        self.model_ = model
        self.training_history_ = [result.__dict__ for result in history]

    def _run_epoch(
        self,
        loader: DataLoader,
        model: nn.Module,
        optimizer,
        criterion,
        device: str,
        training: bool,
    ) -> float:
        if training:
            model.train()
        else:
            model.eval()

        running_loss = 0.0
        total_rows = 0

        for batch_X, batch_y in loader:
            batch_X = batch_X.to(device)
            batch_y = batch_y.to(device)

            if training:
                optimizer.zero_grad()

            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)

            if training:
                loss.backward()
                optimizer.step()

            rows = batch_X.shape[0]
            running_loss += float(loss.item()) * rows
            total_rows += rows

        return running_loss / max(total_rows, 1)

    def _predict_tensor(self, X: np.ndarray) -> torch.Tensor:
        check_is_fitted(self, "model_")
        features = torch.tensor(X, dtype=torch.float32).to(self.device_)
        self.model_.eval()
        with torch.no_grad():
            outputs = self.model_(features)
        return outputs.cpu()


class TorchTabularRegressor(_BaseTorchEstimator, RegressorMixin):
    def _criterion(self):
        return nn.MSELoss()

    def _target_tensor(self, y: np.ndarray) -> torch.Tensor:
        return torch.tensor(y, dtype=torch.float32).unsqueeze(1)

    def fit(self, X, y):
        X, y = check_X_y(X, y, accept_sparse=False, ensure_all_finite="allow-nan")
        self.n_features_in_ = X.shape[1]
        self._fit_model(X.astype(np.float32), y.astype(np.float32), output_dim=1)
        return self

    def predict(self, X):
        X = check_array(X, accept_sparse=False, ensure_all_finite="allow-nan")
        outputs = self._predict_tensor(X.astype(np.float32)).numpy().reshape(-1)
        return outputs


class TorchTabularClassifier(_BaseTorchEstimator, ClassifierMixin):
    def _criterion(self):
        if self.class_weight_ is None:
            return nn.CrossEntropyLoss()
        weights = torch.tensor(self.class_weight_, dtype=torch.float32, device=self.device_)
        return nn.CrossEntropyLoss(weight=weights)

    def _target_tensor(self, y: np.ndarray) -> torch.Tensor:
        return torch.tensor(y, dtype=torch.long)

    def fit(self, X, y):
        X, y = check_X_y(X, y, accept_sparse=False, ensure_all_finite="allow-nan")
        classes, encoded = np.unique(y, return_inverse=True)
        self.classes_ = classes
        self.n_features_in_ = X.shape[1]

        class_counts = np.bincount(encoded)
        self.class_weight_ = (len(encoded) / (len(classes) * np.maximum(class_counts, 1))).astype(np.float32)

        self._fit_model(X.astype(np.float32), encoded.astype(np.int64), output_dim=len(classes))
        return self

    def predict_proba(self, X):
        X = check_array(X, accept_sparse=False, ensure_all_finite="allow-nan")
        logits = self._predict_tensor(X.astype(np.float32))
        probabilities = torch.softmax(logits, dim=1).numpy()
        return probabilities

    def predict(self, X):
        probabilities = self.predict_proba(X)
        labels = np.argmax(probabilities, axis=1)
        return self.classes_[labels]
