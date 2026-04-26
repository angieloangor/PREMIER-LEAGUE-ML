from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import TEAM_NAME_MAP

def _normalize_team_name(team: object) -> str:
    clean = str(team or "").strip()
    return TEAM_NAME_MAP.get(clean, clean)

def _round_nested(value):
    if isinstance(value, dict):
        return {key: _round_nested(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_round_nested(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return round(float(value), 4)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value

def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def _save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

