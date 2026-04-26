from __future__ import annotations

import pandas as pd


MATCH_META_COLUMNS = {
    "id",
    "date",
    "time",
    "kickoff",
    "home_team",
    "away_team",
    "ftr",
    "htr",
    "referee",
}

MATCH_OBSERVED_MATCH_COLUMNS = {
    "hthg",
    "htag",
    "hs",
    "as_",
    "hst",
    "ast",
    "hf",
    "af",
    "hc",
    "ac",
    "hy",
    "ay",
    "hr",
    "ar",
}

MATCH_TARGET_COLUMNS = {
    "fthg",
    "ftag",
    "total_goals",
    "goal_diff",
    "home_win",
    "result_code",
}

APPROXIMATION_TARGET_COLUMNS = [
    "hthg",
    "htag",
    "hs",
    "as_",
    "hst",
    "ast",
    "hf",
    "af",
    "hc",
    "ac",
    "hy",
    "ay",
    "hr",
    "ar",
]

CANDIDATE_INDEX_COLUMNS = [
    "threat_index",
    "dominance_index",
    "efficiency_control_index",
    "territorial_pressure_index",
    "clean_dominance_index",
]

GOALS_FEATURE_PRESETS = {
    "goals_default": [
        "b365h",
        "b365d",
        "b365a",
        "b365_home_prob",
        "b365_draw_prob",
        "b365_away_prob",
        "implied_prob_sum_b365",
        "market_favorite_strength",
        "market_entropy_b365",
        "home_goals_for_last5",
        "away_goals_for_last5",
        "home_goals_against_last5",
        "away_goals_against_last5",
        "home_points_last5",
        "away_points_last5",
        "points_diff_last5",
        "home_shots_last5",
        "away_shots_last5",
        "home_shots_on_target_last5",
        "away_shots_on_target_last5",
        "home_shot_accuracy_last5",
        "away_shot_accuracy_last5",
        "shot_accuracy_diff_last5",
        "home_conversion_rate_last5",
        "away_conversion_rate_last5",
        "conversion_rate_diff_last5",
        "home_big_chance_rate_last5",
        "away_big_chance_rate_last5",
        "big_chance_rate_diff_last5",
        "home_assisted_shot_rate_last5",
        "away_assisted_shot_rate_last5",
        "assisted_shot_rate_diff_last5",
        "home_avg_shot_angle_last5",
        "away_avg_shot_angle_last5",
        "avg_shot_angle_diff_last5",
        "ref_avg_goals_last10",
        "ref_avg_fouls_last10",
    ],
    "goals_compact": [
        "b365h",
        "b365d",
        "b365a",
        "points_diff_last5",
        "home_shots_on_target_last5",
        "away_shots_on_target_last5",
        "conversion_rate_diff_last5",
        "big_chance_rate_diff_last5",
        "market_entropy_b365",
    ],
}

WINNER_FEATURE_PRESETS = {
    "winner_default": [
        "b365h",
        "b365d",
        "b365a",
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
        "market_entropy_b365",
    ],
    "winner_full": [
        "b365h",
        "b365d",
        "b365a",
        "b365_home_prob",
        "b365_draw_prob",
        "b365_away_prob",
        "market_favorite_strength",
        "market_entropy_b365",
        "odds_gap_home_away",
        "home_odds_dispersion",
        "away_odds_dispersion",
        "home_goals_for_last5",
        "home_goals_against_last5",
        "away_goals_for_last5",
        "away_goals_against_last5",
        "home_points_last5",
        "away_points_last5",
        "points_diff_last5",
        "home_shots_last5",
        "away_shots_last5",
        "home_shots_on_target_last5",
        "away_shots_on_target_last5",
        "home_shot_accuracy_last5",
        "away_shot_accuracy_last5",
        "shot_accuracy_diff_last5",
        "home_conversion_rate_last5",
        "away_conversion_rate_last5",
        "conversion_rate_diff_last5",
        "home_big_chances_last5",
        "away_big_chances_last5",
        "home_big_chance_rate_last5",
        "away_big_chance_rate_last5",
        "big_chance_rate_diff_last5",
        "home_progressive_pass_rate_last5",
        "away_progressive_pass_rate_last5",
        "progressive_pass_rate_diff_last5",
        "home_assisted_shot_rate_last5",
        "away_assisted_shot_rate_last5",
        "assisted_shot_rate_diff_last5",
        "home_avg_shot_distance_last5",
        "away_avg_shot_distance_last5",
        "avg_shot_distance_diff_last5",
        "home_avg_shot_angle_last5",
        "away_avg_shot_angle_last5",
        "avg_shot_angle_diff_last5",
        "home_avg_score_diff_before_shot_last5",
        "away_avg_score_diff_before_shot_last5",
        "avg_score_diff_before_shot_diff_last5",
        "ref_avg_yellows_last10",
        "ref_avg_fouls_last10",
        "ref_avg_goals_last10",
        "ref_home_win_rate_last10",
    ],
}


def historical_ex_ante_features(frame: pd.DataFrame) -> list[str]:
    features: list[str] = []
    for column in available_numeric_features(frame):
        if "_last" in column or "_diff_last" in column:
            features.append(column)
        elif column.startswith("ref_") and "last" in column:
            features.append(column)
    return features


def available_numeric_features(frame: pd.DataFrame) -> list[str]:
    return [
        column
        for column in frame.columns
        if pd.api.types.is_numeric_dtype(frame[column])
        and column not in MATCH_META_COLUMNS
        and column not in MATCH_OBSERVED_MATCH_COLUMNS
        and column not in MATCH_TARGET_COLUMNS
    ]


def resolve_feature_columns(frame: pd.DataFrame, preset_or_columns, stage: str) -> list[str]:
    if isinstance(preset_or_columns, str):
        if preset_or_columns == "all_numeric":
            requested = available_numeric_features(frame)
        elif preset_or_columns == "history_only":
            requested = historical_ex_ante_features(frame)
        elif preset_or_columns == "approximation_targets":
            requested = APPROXIMATION_TARGET_COLUMNS
        elif preset_or_columns == "candidate_indices":
            requested = CANDIDATE_INDEX_COLUMNS
        else:
            registry = GOALS_FEATURE_PRESETS if stage == "regression" else WINNER_FEATURE_PRESETS
            requested = registry[preset_or_columns]
    else:
        requested = list(preset_or_columns)

    return [column for column in requested if column in frame.columns]
