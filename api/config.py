from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _resolve_path(raw_value: str | None, project_root: Path, default: Path) -> Path:
    if not raw_value:
        return default
    candidate = Path(raw_value)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate


@dataclass(frozen=True)
class Settings:
    project_root: Path
    outputs_dir: Path
    api_logs_dir: Path
    runs_root: Path
    top_k_models: int
    api_title: str
    api_version: str
    api_prefix: str
    default_host: str
    default_port: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    outputs_dir = project_root / "outputs"
    return Settings(
        project_root=project_root,
        outputs_dir=outputs_dir,
        api_logs_dir=_resolve_path(
            os.getenv("MATCH_API_LOG_DIR"),
            project_root,
            outputs_dir / "api_logs",
        ),
        runs_root=_resolve_path(
            os.getenv("MATCH_API_RUNS_ROOT"),
            project_root,
            outputs_dir / "model_runs" / "advanced_match_predictor" / "stage2_classifier_runs",
        ),
        top_k_models=int(os.getenv("MATCH_API_TOP_K_MODELS", "3")),
        api_title=os.getenv("MATCH_API_TITLE", "PremierLeagueML Match Predictor API"),
        api_version=os.getenv("MATCH_API_VERSION", "1.0.0"),
        api_prefix=os.getenv("MATCH_API_PREFIX", "/api/v1"),
        default_host=os.getenv("MATCH_API_HOST", "0.0.0.0"),
        default_port=int(os.getenv("MATCH_API_PORT", "8000")),
    )
