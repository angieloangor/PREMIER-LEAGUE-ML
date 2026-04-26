from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PITCH_LENGTH_METERS, PITCH_WIDTH_METERS
from .utils import _normalize_team_name

GOAL_WIDTH_METERS = 7.32


def prepare_matches(matches: pd.DataFrame) -> pd.DataFrame:
    prepared = matches.copy()
    prepared["home_team"] = prepared["home_team"].map(_normalize_team_name)
    prepared["away_team"] = prepared["away_team"].map(_normalize_team_name)
    prepared["kickoff"] = pd.to_datetime(
        prepared["date"].astype(str) + " " + prepared["time"].astype(str),
        dayfirst=True,
        errors="coerce",
    )
    prepared["total_goals"] = prepared["fthg"].astype(float) + prepared["ftag"].astype(float)
    prepared["home_win"] = (prepared["ftr"] == "H").astype(int)
    prepared = prepared.dropna(subset=["kickoff", "ftr"]).sort_values(["kickoff", "id"]).reset_index(drop=True)
    return prepared


def _qualifiers_to_text(value) -> str:
    if isinstance(value, list):
        tokens: list[str] = []
        for item in value:
            if isinstance(item, dict):
                item_type = item.get("type", {})
                if item_type.get("displayName"):
                    tokens.append(str(item_type["displayName"]))
                if item.get("value"):
                    tokens.append(str(item["value"]))
            else:
                tokens.append(str(item))
        return " ".join(tokens).lower()
    if isinstance(value, str):
        return value.lower()
    return ""


def _zone_key_to_name(zone_key: str) -> str:
    return {
        "small_box": "Area chica",
        "penalty_box": "Area grande",
        "outside_box": "Fuera del area",
    }.get(zone_key, "Fuera del area")


def _safe_ratio(numerator, denominator):
    return np.where(pd.Series(denominator).fillna(0).to_numpy() > 0, numerator / denominator, 0.0)


def _rolling_sum(grouped, column: str, window: int) -> pd.Series:
    return grouped[column].transform(lambda series: series.shift(1).rolling(window=window, min_periods=1).sum())


def _rolling_mean(grouped, column: str, window: int) -> pd.Series:
    return grouped[column].transform(lambda series: series.shift(1).rolling(window=window, min_periods=1).mean())


def _add_shot_geometry_features(shots: pd.DataFrame) -> pd.DataFrame:
    shots["x"] = shots["x"].astype(float)
    shots["y"] = shots["y"].astype(float)
    shots["original_x"] = shots["x"]
    shots["original_y"] = shots["y"]
    shots["was_normalized"] = shots["x"] < 50
    shots["x"] = np.where(shots["was_normalized"], 100 - shots["x"], shots["x"])
    shots["y"] = np.where(shots["was_normalized"], 100 - shots["y"], shots["y"])

    shots["distance_to_goal"] = np.sqrt((100 - shots["x"]) ** 2 + (50 - shots["y"]) ** 2)
    shots["angle_to_goal"] = np.abs(np.arctan2(50 - shots["y"], 100 - shots["x"]))

    longitudinal_m = ((100 - shots["x"]) / 100) * PITCH_LENGTH_METERS
    signed_lateral_m = ((shots["y"] - 50) / 100) * PITCH_WIDTH_METERS
    lateral_m = np.abs(signed_lateral_m)

    shots["distance_to_goal_m"] = np.sqrt(longitudinal_m**2 + lateral_m**2)
    shots["signed_lateral_distance_m"] = signed_lateral_m
    shots["lateral_distance_m"] = lateral_m
    shots["angle_degrees"] = np.degrees(np.abs(np.arctan2(lateral_m, longitudinal_m)))

    left_post_distance = np.sqrt(longitudinal_m**2 + (signed_lateral_m - (GOAL_WIDTH_METERS / 2)) ** 2)
    right_post_distance = np.sqrt(longitudinal_m**2 + (signed_lateral_m + (GOAL_WIDTH_METERS / 2)) ** 2)
    denominator = 2 * left_post_distance * right_post_distance
    cos_value = np.where(
        denominator > 0,
        (left_post_distance**2 + right_post_distance**2 - GOAL_WIDTH_METERS**2) / denominator,
        1.0,
    )
    shots["goal_frame_angle"] = np.arccos(np.clip(cos_value, -1.0, 1.0))
    shots["goal_frame_angle_degrees"] = np.degrees(shots["goal_frame_angle"])
    shots["distance_squared"] = shots["distance_to_goal_m"] ** 2
    shots["centrality_to_goal"] = 1 - (np.abs(shots["y"] - 50) / 50)
    shots["shot_angle_distance_interaction"] = shots["goal_frame_angle"] / np.maximum(shots["distance_to_goal_m"], 1e-6)
    return shots


def _add_shot_context_flags(shots: pd.DataFrame) -> pd.DataFrame:
    text = shots["qualifier_text"]
    shots["is_big_chance"] = text.str.contains("bigchance", regex=False).astype(int)
    shots["is_header"] = text.str.contains("head", regex=False).astype(int)
    shots["is_right_foot"] = text.str.contains("rightfoot", regex=False).astype(int)
    shots["is_left_foot"] = text.str.contains("leftfoot", regex=False).astype(int)
    shots["is_penalty"] = text.str.contains("penalty", regex=False).astype(int)
    shots["is_counter_attack"] = text.str.contains("fastbreak", regex=False).astype(int)
    shots["from_corner"] = text.str.contains("fromcorner", regex=False).astype(int)
    shots["is_volley"] = text.str.contains("volley", regex=False).astype(int)
    shots["first_touch"] = text.str.contains("firsttouch", regex=False).astype(int)
    shots["zone_small_box"] = text.str.contains("smallbox", regex=False).astype(int)
    shots["zone_box_centre"] = text.str.contains("boxcentre", regex=False).astype(int)
    shots["zone_out_of_box"] = text.str.contains("outofbox", regex=False).astype(int)
    shots["is_assisted"] = text.str.contains("assisted", regex=False).astype(int)
    shots["is_intentional_assist"] = text.str.contains("intentionalassist", regex=False).astype(int)
    shots["is_individual_play"] = text.str.contains("individualplay", regex=False).astype(int)
    shots["is_regular_play"] = text.str.contains("regularplay", regex=False).astype(int)
    shots["is_set_piece"] = text.str.contains("setpiece", regex=False).astype(int)
    shots["is_direct_freekick"] = text.str.contains("directfreekick", regex=False).astype(int)
    shots["is_throwin_set_piece"] = text.str.contains("throwinsetpiece", regex=False).astype(int)
    shots["shot_on_target"] = shots["event_type"].isin(["SavedShot", "Goal"]).astype(int)
    shots["shot_type_key"] = np.select(
        [
            shots["is_penalty"] == 1,
            shots["is_header"] == 1,
            (shots["is_left_foot"] == 1) | (shots["is_right_foot"] == 1),
        ],
        ["penalty", "header", "foot"],
        default="other",
    )
    shots["shot_type"] = shots["shot_type_key"].map(
        {
            "penalty": "Penal",
            "header": "Cabeza",
            "foot": "Pie",
            "other": "Otro",
        }
    )
    return shots


def _add_shot_zone_features(shots: pd.DataFrame) -> pd.DataFrame:
    small_box_mask = (shots["x"] >= 94.5) & shots["y"].between(36.8, 63.2)
    penalty_box_mask = (shots["x"] >= 83.5) & shots["y"].between(21.1, 78.9)
    shots["zone_key"] = np.select(
        [small_box_mask, penalty_box_mask],
        ["small_box", "penalty_box"],
        default="outside_box",
    )
    shots["zone_name"] = shots["zone_key"].map(_zone_key_to_name)
    return shots


def _add_match_context_features(shots: pd.DataFrame) -> pd.DataFrame:
    shots["minute"] = pd.to_numeric(shots["minute"], errors="coerce").fillna(0).astype(int)
    shots["second"] = pd.to_numeric(shots["second"], errors="coerce").fillna(0).astype(int)
    shots["game_clock_s"] = (shots["minute"] * 60) + shots["second"]
    shots["game_minute_normalized"] = np.clip(shots["minute"] / 95.0, 0, 1.25)
    shots["is_home_team"] = (shots["team_name"] == shots["home_team"]).astype(int)

    by_match = shots.groupby("match_id")
    shots["shot_number_in_match"] = by_match.cumcount() + 1
    shots["time_since_prev_match_shot_s"] = by_match["game_clock_s"].diff().fillna(shots["game_clock_s"])

    by_match_team = shots.groupby(["match_id", "team_name"])
    shots["team_shot_number_in_match"] = by_match_team.cumcount() + 1
    shots["time_since_prev_team_shot_s"] = by_match_team["game_clock_s"].diff().fillna(shots["game_clock_s"])

    by_match_player = shots.groupby(["match_id", "player_name"])
    shots["player_shot_number_in_match"] = by_match_player.cumcount() + 1
    return shots


def _add_score_state_features(shots: pd.DataFrame) -> pd.DataFrame:
    shots["home_goal_event"] = ((shots["is_home_team"] == 1) & (shots["is_goal"] == 1)).astype(int)
    shots["away_goal_event"] = ((shots["is_home_team"] == 0) & (shots["is_goal"] == 1)).astype(int)

    by_match = shots.groupby("match_id")
    shots["home_goals_before_shot"] = by_match["home_goal_event"].cumsum().shift(1, fill_value=0)
    shots["away_goals_before_shot"] = by_match["away_goal_event"].cumsum().shift(1, fill_value=0)
    shots["team_goals_before_shot"] = np.where(
        shots["is_home_team"] == 1,
        shots["home_goals_before_shot"],
        shots["away_goals_before_shot"],
    )
    shots["opponent_goals_before_shot"] = np.where(
        shots["is_home_team"] == 1,
        shots["away_goals_before_shot"],
        shots["home_goals_before_shot"],
    )
    shots["score_diff_before_shot"] = shots["team_goals_before_shot"] - shots["opponent_goals_before_shot"]
    shots["leading_before_shot"] = (shots["score_diff_before_shot"] > 0).astype(int)
    shots["drawing_before_shot"] = (shots["score_diff_before_shot"] == 0).astype(int)
    shots["trailing_before_shot"] = (shots["score_diff_before_shot"] < 0).astype(int)
    return shots


def _add_historical_shot_features(shots: pd.DataFrame) -> pd.DataFrame:
    player_groups = shots.groupby("player_name", group_keys=False)
    shots["player_shots_before"] = player_groups.cumcount()
    shots["player_goals_last20"] = _rolling_sum(player_groups, "is_goal", window=20)
    shots["player_conversion_last20"] = _rolling_mean(player_groups, "is_goal", window=20)
    shots["player_big_chance_rate_last20"] = _rolling_mean(player_groups, "is_big_chance", window=20)
    shots["player_avg_distance_last20"] = _rolling_mean(player_groups, "distance_to_goal_m", window=20)

    team_groups = shots.groupby("team_name", group_keys=False)
    shots["team_shots_before"] = team_groups.cumcount()
    shots["team_goals_last40"] = _rolling_sum(team_groups, "is_goal", window=40)
    shots["team_conversion_last40"] = _rolling_mean(team_groups, "is_goal", window=40)
    shots["team_big_chance_rate_last40"] = _rolling_mean(team_groups, "is_big_chance", window=40)
    shots["team_avg_distance_last40"] = _rolling_mean(team_groups, "distance_to_goal_m", window=40)
    return shots


def enrich_shots(events: pd.DataFrame, matches: pd.DataFrame, api_shots: pd.DataFrame) -> pd.DataFrame:
    shots = events.loc[events["is_shot"] == 1].copy()
    shots["match_id"] = shots["match_id"].astype(int)
    shots["is_goal"] = shots["is_goal"].astype(int)

    api_shots = api_shots.copy()
    api_shots["id"] = api_shots["id"].astype(int)
    api_shots["qualifier_text"] = api_shots["qualifiers"].map(_qualifiers_to_text)

    shots = shots.merge(api_shots[["id", "qualifier_text"]], on="id", how="left")
    shots["qualifier_text"] = shots["qualifier_text"].fillna("")
    shots["team_name"] = shots["team_name"].map(_normalize_team_name)
    shots["player_name"] = shots["player_name"].fillna("").replace("", "Jugador no identificado")

    shots = shots.merge(
        matches[["id", "kickoff", "home_team", "away_team", "fthg", "ftag"]],
        left_on="match_id",
        right_on="id",
        how="left",
        suffixes=("", "_match"),
    ).drop(columns=["id_match"], errors="ignore")

    shots = shots.sort_values(["kickoff", "match_id", "minute", "second", "id"]).reset_index(drop=True)
    shots = _add_shot_geometry_features(shots)
    shots = _add_shot_context_flags(shots)
    shots = _add_shot_zone_features(shots)
    shots = _add_match_context_features(shots)
    shots = _add_score_state_features(shots)
    shots = _add_historical_shot_features(shots)
    shots["date"] = shots["kickoff"].dt.strftime("%Y-%m-%d")
    return shots


def build_event_match_stats(events: pd.DataFrame, enriched_shots: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    enriched = events.copy()
    enriched["match_id"] = enriched["match_id"].astype(int)
    enriched["team_name"] = enriched["team_name"].map(_normalize_team_name)
    enriched["event_type"] = enriched["event_type"].fillna("")
    enriched["outcome"] = enriched["outcome"].fillna("")
    enriched["x"] = pd.to_numeric(enriched["x"], errors="coerce")
    enriched["end_x"] = pd.to_numeric(enriched["end_x"], errors="coerce")
    enriched = enriched.merge(
        enriched_shots[
            [
                "id",
                "is_big_chance",
                "is_penalty",
                "shot_on_target",
                "distance_to_goal_m",
                "goal_frame_angle",
                "score_diff_before_shot",
                "is_assisted",
            ]
        ],
        on="id",
        how="left",
    )
    enriched[["is_big_chance", "is_penalty", "shot_on_target", "is_assisted"]] = enriched[
        ["is_big_chance", "is_penalty", "shot_on_target", "is_assisted"]
    ].fillna(0)

    enriched["is_pass"] = (enriched["event_type"] == "Pass").astype(int)
    enriched["successful_pass"] = ((enriched["event_type"] == "Pass") & (enriched["outcome"] == "Successful")).astype(int)
    enriched["progressive_pass"] = (
        (enriched["event_type"] == "Pass")
        & (enriched["end_x"].fillna(enriched["x"]) - enriched["x"].fillna(0) >= 15)
    ).astype(int)
    enriched["final_third_pass"] = (
        (enriched["event_type"] == "Pass") & (enriched["end_x"].fillna(0) >= 66)
    ).astype(int)
    enriched["is_shot"] = enriched["is_shot"].astype(int)
    enriched["is_goal"] = enriched["is_goal"].astype(int)
    enriched["is_touch"] = enriched["is_touch"].astype(int)

    grouped = enriched.groupby(["match_id", "team_name"], as_index=False).agg(
        passes_attempted=("is_pass", "sum"),
        passes_completed=("successful_pass", "sum"),
        progressive_passes=("progressive_pass", "sum"),
        final_third_passes=("final_third_pass", "sum"),
        shots=("is_shot", "sum"),
        shots_on_target=("shot_on_target", "sum"),
        big_chances=("is_big_chance", "sum"),
        penalties=("is_penalty", "sum"),
        assisted_shots=("is_assisted", "sum"),
        goals=("is_goal", "sum"),
        touches=("is_touch", "sum"),
        avg_shot_distance=("distance_to_goal_m", "mean"),
        avg_shot_angle=("goal_frame_angle", "mean"),
        avg_score_diff_before_shot=("score_diff_before_shot", "mean"),
    )
    grouped["pass_accuracy"] = _safe_ratio(grouped["passes_completed"], grouped["passes_attempted"])
    grouped["progressive_pass_rate"] = _safe_ratio(grouped["progressive_passes"], grouped["passes_attempted"])
    grouped["shot_accuracy"] = _safe_ratio(grouped["shots_on_target"], grouped["shots"])
    grouped["conversion_rate"] = _safe_ratio(grouped["goals"], grouped["shots"])
    grouped["big_chance_rate"] = _safe_ratio(grouped["big_chances"], grouped["shots"])
    grouped["assisted_shot_rate"] = _safe_ratio(grouped["assisted_shots"], grouped["shots"])
    grouped["touches_per_shot"] = np.where(grouped["shots"] > 0, grouped["touches"] / grouped["shots"], grouped["touches"])
    grouped["avg_shot_distance"] = grouped["avg_shot_distance"].fillna(0.0)
    grouped["avg_shot_angle"] = grouped["avg_shot_angle"].fillna(0.0)
    grouped["avg_score_diff_before_shot"] = grouped["avg_score_diff_before_shot"].fillna(0.0)

    grouped = grouped.merge(
        matches[["id", "home_team", "away_team", "kickoff"]].rename(columns={"id": "match_id"}),
        on="match_id",
        how="left",
    )
    grouped["opponent"] = np.where(grouped["team_name"] == grouped["home_team"], grouped["away_team"], grouped["home_team"])
    grouped["is_home"] = (grouped["team_name"] == grouped["home_team"]).astype(int)
    return grouped.sort_values(["kickoff", "match_id", "team_name"]).reset_index(drop=True)


def _build_team_history(matches: pd.DataFrame, event_stats: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    home_rows = matches[["id", "kickoff", "home_team", "fthg", "ftag", "ftr"]].copy()
    home_rows.columns = ["match_id", "kickoff", "team", "goals_for", "goals_against", "ftr"]
    home_rows["is_home"] = 1

    away_rows = matches[["id", "kickoff", "away_team", "ftag", "fthg", "ftr"]].copy()
    away_rows.columns = ["match_id", "kickoff", "team", "goals_for", "goals_against", "ftr"]
    away_rows["is_home"] = 0

    long_matches = pd.concat([home_rows, away_rows], ignore_index=True)
    long_matches["points"] = np.select(
        [
            (long_matches["is_home"] == 1) & (long_matches["ftr"] == "H"),
            (long_matches["is_home"] == 0) & (long_matches["ftr"] == "A"),
            long_matches["ftr"] == "D",
        ],
        [3, 3, 1],
        default=0,
    )
    history = long_matches.merge(
        event_stats.drop(columns=["kickoff", "home_team", "away_team", "opponent", "is_home"], errors="ignore"),
        left_on=["match_id", "team"],
        right_on=["match_id", "team_name"],
        how="left",
    )
    history = history.sort_values(["team", "kickoff", "match_id"]).reset_index(drop=True)

    rolling_columns = [
        "goals_for",
        "goals_against",
        "points",
        "pass_accuracy",
        "progressive_passes",
        "progressive_pass_rate",
        "shots",
        "shots_on_target",
        "shot_accuracy",
        "conversion_rate",
        "big_chances",
        "big_chance_rate",
        "assisted_shot_rate",
        "touches",
        "touches_per_shot",
        "avg_shot_distance",
        "avg_shot_angle",
        "avg_score_diff_before_shot",
    ]
    grouped = history.groupby("team", group_keys=False)
    for column in rolling_columns:
        history[f"{column}_last{window}"] = grouped[column].transform(
            lambda series: series.shift(1).rolling(window=window, min_periods=1).mean()
        )
    return history


def _build_referee_history(matches: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    frame = matches[["id", "kickoff", "referee", "hy", "ay", "hf", "af", "home_win", "total_goals"]].copy()
    frame["total_yellows"] = frame["hy"].astype(float) + frame["ay"].astype(float)
    frame["total_fouls"] = frame["hf"].astype(float) + frame["af"].astype(float)
    frame = frame.sort_values(["referee", "kickoff", "id"]).reset_index(drop=True)
    grouped = frame.groupby("referee", group_keys=False)
    targets = {
        "total_yellows": "ref_avg_yellows_last10",
        "total_fouls": "ref_avg_fouls_last10",
        "total_goals": "ref_avg_goals_last10",
        "home_win": "ref_home_win_rate_last10",
    }
    for source, target in targets.items():
        frame[target] = grouped[source].transform(
            lambda series: series.shift(1).rolling(window=window, min_periods=1).mean()
        )
    return frame[["id", *targets.values()]]


def build_match_features(matches: pd.DataFrame, event_stats: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    history = _build_team_history(matches, event_stats, window=window)
    suffix = f"_last{window}"
    rolling_columns = [column for column in history.columns if column.endswith(suffix)]

    home = history.loc[history["is_home"] == 1, ["match_id", *rolling_columns]].copy()
    away = history.loc[history["is_home"] == 0, ["match_id", *rolling_columns]].copy()
    home = home.rename(columns={"match_id": "id", **{column: f"home_{column}" for column in rolling_columns}})
    away = away.rename(columns={"match_id": "id", **{column: f"away_{column}" for column in rolling_columns}})

    feature_matches = matches.merge(home, on="id", how="left").merge(away, on="id", how="left")
    feature_matches = feature_matches.merge(_build_referee_history(matches), on="id", how="left")

    implied_sets = {}
    for prefix in ["b365", "bw", "max", "avg"]:
        feature_matches[f"{prefix}_home_prob"] = 1 / feature_matches[f"{prefix}h"].astype(float)
        feature_matches[f"{prefix}_draw_prob"] = 1 / feature_matches[f"{prefix}d"].astype(float)
        feature_matches[f"{prefix}_away_prob"] = 1 / feature_matches[f"{prefix}a"].astype(float)
        implied_sets[prefix] = feature_matches[
            [f"{prefix}_home_prob", f"{prefix}_draw_prob", f"{prefix}_away_prob"]
        ].to_numpy()

    feature_matches["odds_gap_home_away"] = feature_matches["b365a"].astype(float) - feature_matches["b365h"].astype(float)
    feature_matches["implied_prob_sum_b365"] = (
        feature_matches["b365_home_prob"] + feature_matches["b365_draw_prob"] + feature_matches["b365_away_prob"]
    )
    normalized_b365 = implied_sets["b365"] / np.maximum(implied_sets["b365"].sum(axis=1, keepdims=True), 1e-9)
    feature_matches["market_favorite_strength"] = normalized_b365.max(axis=1)
    feature_matches["market_entropy_b365"] = -np.sum(normalized_b365 * np.log(np.clip(normalized_b365, 1e-9, 1)), axis=1)
    feature_matches["home_odds_dispersion"] = feature_matches[["b365h", "bwh", "maxh", "avgh"]].astype(float).std(axis=1)
    feature_matches["away_odds_dispersion"] = feature_matches[["b365a", "bwa", "maxa", "avga"]].astype(float).std(axis=1)

    diff_bases = [
        "goals_for",
        "goals_against",
        "points",
        "pass_accuracy",
        "progressive_pass_rate",
        "shots",
        "shots_on_target",
        "shot_accuracy",
        "conversion_rate",
        "big_chances",
        "big_chance_rate",
        "assisted_shot_rate",
        "touches_per_shot",
        "avg_shot_distance",
        "avg_shot_angle",
        "avg_score_diff_before_shot",
    ]
    for base in diff_bases:
        feature_matches[f"{base}_diff_last{window}"] = (
            feature_matches[f"home_{base}_last{window}"] - feature_matches[f"away_{base}_last{window}"]
        )

    feature_matches["result_code"] = feature_matches["ftr"].map({"H": 0, "D": 1, "A": 2}).astype(int)
    return feature_matches.sort_values(["kickoff", "id"]).reset_index(drop=True)
