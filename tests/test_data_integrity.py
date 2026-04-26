from __future__ import annotations

import json

from src.data import existing_files_are_available, load_datasets
from src.dataops import build_data_artifacts


def test_local_raw_datasets_are_available():
    assert existing_files_are_available() is True


def test_load_datasets_returns_non_empty_frames():
    players, matches, events = load_datasets()
    assert not players.empty
    assert not matches.empty
    assert not events.empty
    assert {"id"}.issubset(players.columns)
    assert {"id", "date"}.issubset(matches.columns)
    assert {"match_id", "event_type"}.issubset(events.columns)


def test_build_data_artifacts_updates_manifest_and_processed_outputs():
    results = build_data_artifacts()
    assert not results["shots"].empty
    assert not results["match_features"].empty

    manifest_path = results["docs"]["manifest_json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "artifacts" in manifest
    assert manifest["artifacts"]["match_features"]["rows"] == int(results["match_features"].shape[0])
