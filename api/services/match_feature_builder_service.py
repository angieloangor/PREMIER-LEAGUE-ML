from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from api.config import Settings
from api.services.feature_service import FeatureValidationError, require_columns
from src.dataops import build_data_artifacts
from src.preprocessing import build_match_features, prepare_matches
from src.utils import _normalize_team_name

RAW_MATCH_REQUIRED_COLUMNS = [
    "date",
    "time",
    "home_team",
    "away_team",
    "referee",
    "b365h",
    "b365d",
    "b365a",
    "bwh",
    "bwd",
    "bwa",
    "maxh",
    "maxd",
    "maxa",
    "avgh",
    "avgd",
    "avga",
]

RAW_MATCH_PLACEHOLDERS = {
    "fthg": 0,
    "ftag": 0,
    "ftr": "D",
    "hthg": 0,
    "htag": 0,
    "htr": "D",
    "hs": 0,
    "as_": 0,
    "hst": 0,
    "ast": 0,
    "hf": 0,
    "af": 0,
    "hc": 0,
    "ac": 0,
    "hy": 0,
    "ay": 0,
    "hr": 0,
    "ar": 0,
    "total_goals": 0.0,
    "goal_diff": 0.0,
}


@lru_cache(maxsize=1)
def _historical_processed_data(project_root: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = Path(project_root)
    matches_path = root / "data" / "processed" / "matches_prepared.csv"
    event_stats_path = root / "data" / "processed" / "event_match_features.csv"
    match_features_path = root / "data" / "processed" / "match_features.csv"

    if not (matches_path.exists() and event_stats_path.exists() and match_features_path.exists()):
        build_data_artifacts()

    matches = pd.read_csv(matches_path)
    event_stats = pd.read_csv(event_stats_path)
    match_features = pd.read_csv(match_features_path)

    matches["kickoff"] = pd.to_datetime(matches["kickoff"], errors="coerce")
    if "kickoff" in event_stats.columns:
        event_stats["kickoff"] = pd.to_datetime(event_stats["kickoff"], errors="coerce")
    if "kickoff" in match_features.columns:
        match_features["kickoff"] = pd.to_datetime(match_features["kickoff"], errors="coerce")
    return matches, event_stats, match_features


class MatchFeatureBuilderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_feature_frame(self, raw_matches: pd.DataFrame) -> pd.DataFrame:
        if raw_matches.empty:
            raise FeatureValidationError("At least one raw match row is required.")

        historical_matches, event_stats, historical_match_features = _historical_processed_data(str(self.settings.project_root))
        prepared_inference = self._prepare_inference_matches(raw_matches, historical_matches)
        combined_matches = pd.concat([historical_matches, prepared_inference], ignore_index=True, sort=False)
        combined_matches = combined_matches.sort_values(["kickoff", "id"]).reset_index(drop=True)

        built_features = build_match_features(combined_matches, event_stats, window=5)
        inference_ids = prepared_inference["id"].tolist()
        built_features = built_features.loc[built_features["id"].isin(inference_ids)].copy()
        built_features["id"] = pd.Categorical(built_features["id"], categories=inference_ids, ordered=True)
        built_features = built_features.sort_values("id").reset_index(drop=True)
        built_features["id"] = built_features["id"].astype(int)

        if len(built_features) != len(raw_matches):
            raise FeatureValidationError("Could not build feature rows for every requested match.")

        return self._fill_missing_with_historical_medians(built_features, historical_match_features)

    def _prepare_inference_matches(self, raw_matches: pd.DataFrame, historical_matches: pd.DataFrame) -> pd.DataFrame:
        require_columns(raw_matches, RAW_MATCH_REQUIRED_COLUMNS)

        template_columns = [column for column in historical_matches.columns if column not in {"kickoff", "home_win"}]
        prepared_raw = pd.DataFrame(index=raw_matches.index, columns=template_columns)

        next_id = int(pd.to_numeric(historical_matches["id"], errors="coerce").max()) + 1
        prepared_raw["id"] = range(next_id, next_id + len(raw_matches))

        for column in template_columns:
            if column in raw_matches.columns:
                prepared_raw[column] = raw_matches[column]

        for column, default_value in RAW_MATCH_PLACEHOLDERS.items():
            if column in prepared_raw.columns:
                prepared_raw[column] = prepared_raw[column].where(prepared_raw[column].notna(), default_value)

        prepared_raw["home_team"] = prepared_raw["home_team"].map(_normalize_team_name)
        prepared_raw["away_team"] = prepared_raw["away_team"].map(_normalize_team_name)

        for column in ["b365h", "b365d", "b365a", "bwh", "bwd", "bwa", "maxh", "maxd", "maxa", "avgh", "avgd", "avga"]:
            prepared_raw[column] = pd.to_numeric(prepared_raw[column], errors="coerce")

        invalid_odds = [
            column for column in ["b365h", "b365d", "b365a", "bwh", "bwd", "bwa", "maxh", "maxd", "maxa", "avgh", "avgd", "avga"]
            if prepared_raw[column].isna().any()
        ]
        if invalid_odds:
            raise FeatureValidationError("Input contains invalid odds values.", {"invalid_columns": invalid_odds})

        prepared_raw["implied_prob_h"] = self._coalesce_numeric(raw_matches, "implied_prob_h", 1.0 / prepared_raw["b365h"])
        prepared_raw["implied_prob_d"] = self._coalesce_numeric(raw_matches, "implied_prob_d", 1.0 / prepared_raw["b365d"])
        prepared_raw["implied_prob_a"] = self._coalesce_numeric(raw_matches, "implied_prob_a", 1.0 / prepared_raw["b365a"])
        prepared_raw["goal_diff"] = pd.to_numeric(prepared_raw["goal_diff"], errors="coerce").fillna(0.0)
        prepared_raw["total_goals"] = pd.to_numeric(prepared_raw["total_goals"], errors="coerce").fillna(0.0)

        prepared = prepare_matches(prepared_raw)
        if len(prepared) != len(raw_matches):
            raise FeatureValidationError(
                "Some rows could not be prepared. Check date/time values.",
                {"required_columns": RAW_MATCH_REQUIRED_COLUMNS},
            )
        return prepared

    def _fill_missing_with_historical_medians(
        self,
        built_features: pd.DataFrame,
        historical_match_features: pd.DataFrame,
    ) -> pd.DataFrame:
        result = built_features.copy()
        common_columns = [column for column in result.columns if column in historical_match_features.columns]
        historical_numeric = historical_match_features.reindex(columns=common_columns).apply(pd.to_numeric, errors="coerce")
        numeric_columns = historical_numeric.columns[historical_numeric.notna().any()].tolist()
        medians = historical_numeric[numeric_columns].median(numeric_only=True).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        for column in medians.index:
            converted = pd.to_numeric(result[column], errors="coerce")
            result[column] = converted.fillna(float(medians[column]))
        return result

    def _coalesce_numeric(self, frame: pd.DataFrame, column: str, fallback: pd.Series) -> pd.Series:
        if column not in frame.columns:
            return fallback.astype(float)
        converted = pd.to_numeric(frame[column], errors="coerce")
        return converted.fillna(fallback).astype(float)
