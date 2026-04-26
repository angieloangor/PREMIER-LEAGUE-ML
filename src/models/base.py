from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Literal


StageType = Literal["regression", "classification"]
SerializerType = Literal["joblib", "pt"]
PreprocessorType = Literal["linear", "tree"]


@dataclass(frozen=True)
class ModelSpec:
    key: str
    stage: StageType
    family: str
    build_estimator: Callable[[], Any]
    param_grid: dict[str, list[Any]]
    serializer: SerializerType = "joblib"
    preprocessor: PreprocessorType = "linear"
    description: str = ""

    @property
    def search_space_size(self) -> int:
        if not self.param_grid:
            return 1
        return len(list(product(*self.param_grid.values())))
