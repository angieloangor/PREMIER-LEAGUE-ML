from __future__ import annotations

from pathlib import Path

from api.config import get_settings


def test_runs_root_is_configured():
    settings = get_settings()
    assert isinstance(settings.runs_root, Path)
    assert settings.outputs_dir.name == "outputs"
