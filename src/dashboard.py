from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .config import BET365_BENCHMARK_ACCURACY, DASHBOARD_DIR, MATCH_RESULT_NAMES, OUTPUTS_DIR
from .utils import _normalize_team_name, _round_nested

def build_dashboard_payload(players: pd.DataFrame, matches: pd.DataFrame, event_stats: pd.DataFrame, xg_results: dict, match_results: dict) -> dict:
    shots = xg_results["shots"].copy()
    shots["date"] = shots["kickoff"].dt.strftime("%Y-%m-%d")
    shot_export_columns = [
        "id",
        "match_id",
        "date",
        "team_name",
        "player_name",
        "home_team",
        "away_team",
        "fthg",
        "ftag",
        "x",
        "y",
        "original_x",
        "original_y",
        "was_normalized",
        "is_goal",
        "distance_to_goal",
        "distance_to_goal_m",
        "angle_to_goal",
        "angle_degrees",
        "xg_probability",
        "is_big_chance",
        "is_penalty",
        "is_header",
        "is_right_foot",
        "is_left_foot",
        "shot_type_key",
        "shot_type",
        "zone_key",
        "zone_name",
    ]
    ordered = match_results["ordered_matches"]
    probs = match_results["full_probabilities"]
    est_goals = match_results["full_goal_predictions"]
    benchmark_pct = BET365_BENCHMARK_ACCURACY * 100
    model_pct = match_results["metrics"]["cv_mean_accuracy"] * 100
    benchmark_gap = model_pct - benchmark_pct

    predictions = []
    for row, p, goals in zip(ordered.itertuples(index=False), probs, est_goals):
        predictions.append({
            "match_id": int(row.id),
            "date": row.kickoff.strftime("%Y-%m-%d"),
            "home": row.home_team,
            "away": row.away_team,
            "prob_home": round(float(p[0] * 100), 2),
            "prob_draw": round(float(p[1] * 100), 2),
            "prob_away": round(float(p[2] * 100), 2),
            "est_goals": round(float(goals), 2),
            "actual_result": row.ftr,
            "actual_total_goals": round(float(row.total_goals), 2),
        })

    result_counts = matches["ftr"].value_counts().reindex(["H", "D", "A"]).fillna(0).astype(int)
    angle_bins = pd.cut(shots["angle_to_goal"], bins=np.linspace(0, max(shots["angle_to_goal"].max(), 0.001), 8), include_lowest=True, duplicates="drop")
    angle_group = shots.groupby(angle_bins, observed=False).agg(mean_angle=("angle_to_goal", "mean"), conversion_rate=("is_goal", "mean"), shot_count=("is_goal", "size")).dropna()

    team_home = matches.groupby("home_team").agg(goals_home=("fthg", "mean"), ga_home=("ftag", "mean"))
    team_away = matches.groupby("away_team").agg(goals_away=("ftag", "mean"), ga_away=("fthg", "mean"))
    team_extra = event_stats.groupby("team_name").agg(pass_accuracy=("pass_accuracy", "mean"), big_chances=("big_chances", "mean"))
    cluster_frame = team_home.join(team_away, how="outer").join(team_extra, how="outer").fillna(0)
    cluster_frame["goals_scored_avg"] = (cluster_frame["goals_home"] + cluster_frame["goals_away"]) / 2
    cluster_frame["goals_conceded_avg"] = (cluster_frame["ga_home"] + cluster_frame["ga_away"]) / 2
    scaled = StandardScaler().fit_transform(cluster_frame[["goals_scored_avg", "goals_conceded_avg", "pass_accuracy", "big_chances"]])
    km = KMeans(n_clusters=3, n_init=20, random_state=42)
    labels = km.fit_predict(scaled)
    silhouette = float(silhouette_score(scaled, labels))
    clusters = cluster_frame.reset_index()
    if "home_team" in clusters.columns:
        clusters = clusters.rename(columns={"home_team": "team"})
    elif "away_team" in clusters.columns:
        clusters = clusters.rename(columns={"away_team": "team"})
    elif "index" in clusters.columns:
        clusters = clusters.rename(columns={"index": "team"})
    clusters["team"] = clusters["team"].map(_normalize_team_name)
    clusters["cluster"] = labels.astype(int)

    xg_metrics = xg_results["metrics"].copy()
    xg_metrics["baseline"] = xg_results.get("baseline", {})
    xg_metrics["threshold_analysis"] = xg_results.get("threshold_analysis", {})

    return _round_nested({
        "project_summary": {
            "titulo": "Pipeline ML Premier League 2025-2026 alineado con el taller ML1",
            "benchmark_bet365": benchmark_pct,
            "accuracy_modelo": model_pct,
            "ventaja_sobre_benchmark": benchmark_gap,
            "modelo_supera_benchmark": benchmark_gap > 0,
            "limitaciones": [
                "El predictor usa datos previos al partido para evitar leakage; no usa stats del mismo juego.",
                "El dashboard muestra predicciones sobre partidos reales ya jugados; para futuros fixtures se necesitarían odds futuras.",
                "Los qualifiers completos se recuperan desde el endpoint de tiros del API y se guardan en cache local.",
            ],
            "fuentes_externas": [
                f"Tiros con qualifiers del API: {len(shots)} registros.",
                f"Benchmark Bet365 con validación temporal: {benchmark_pct:.2f}%.",
                "Features del predictor: odds pre-partido + rolling stats de eventos + historial por árbitro.",
                "Comparación de modelos: odds solamente, histórico solamente y combinación de ambos.",
            ],
        },
        "clustering_metrics": {
            "points": clusters[["team", "goals_scored_avg", "goals_conceded_avg", "cluster"]].to_dict(orient="records"),
            "silhouette_score": silhouette,
        },
        "xg_metrics": xg_metrics,
        "match_metrics": match_results["metrics"],
        "xg_threshold_analysis": xg_results.get("threshold_analysis", {}),
        "advanced_metrics": {
            **match_results["advanced_metrics"],
            "xg_random_forest_accuracy": xg_results["advanced_metrics"]["random_forest_accuracy"],
            "xg_random_forest_auc": xg_results["advanced_metrics"]["random_forest_auc"],
            "feature_columns_match": match_results["feature_columns"],
            "feature_columns_match_odds_only": match_results["odds_only_feature_columns"],
            "feature_columns_xg": xg_results["feature_columns"],
        },
        "linear_metrics": match_results["linear_metrics"],
        "match_accuracy": model_pct,
        "benchmark_comparison": {
            "labels": ["Modelo", "Bet365"],
            "values": [model_pct, benchmark_pct],
            "gap_vs_bet365": benchmark_gap,
            "model_beats_bet365": benchmark_gap > 0,
            "model_cv_std": match_results["metrics"]["cv_std_accuracy"] * 100,
        },
        "confusion_matrix": {"labels": MATCH_RESULT_NAMES, "values": match_results["confusion_matrix"]},
        "xg_confusion_matrix": {"labels": ["No gol", "Gol"], "values": xg_results["confusion_matrix"]},
        "xg_roc_curve": xg_results["roc_curve"],
        "eda": {
            "total_goals_per_match": matches["total_goals"].round(2).tolist(),
            "result_distribution": {"labels": ["Local", "Empate", "Visitante"], "values": result_counts.tolist()},
            "distance_to_goal": {
                "no_gol": shots.loc[shots["is_goal"] == 0, "distance_to_goal"].round(4).tolist(),
                "gol": shots.loc[shots["is_goal"] == 1, "distance_to_goal"].round(4).tolist(),
            },
            "angle_vs_goal": {
                "mean_angle": angle_group["mean_angle"].round(4).tolist(),
                "conversion_rate": angle_group["conversion_rate"].round(4).tolist(),
                "shot_count": angle_group["shot_count"].astype(int).tolist(),
            },
            "xg_probability_distribution": shots["xg_probability"].round(4).tolist(),
            "benchmark_comparison": {
                "labels": ["Modelo", "Bet365"],
                "values": [model_pct, benchmark_pct],
                "gap_vs_bet365": benchmark_gap,
                "model_beats_bet365": benchmark_gap > 0,
            },
            "linear_residuals": match_results["holdout_predictions"]["residual_total_goals"].round(4).tolist(),
        },
        "shot_map_global": shots[shot_export_columns].to_dict(orient="records"),
        "shots": shots[shot_export_columns].to_dict(orient="records"),
        "shot_map_by_match": {},
        "match_shot_options": [{"match_id": int(r.id), "date": r.kickoff.strftime("%Y-%m-%d"), "home_team": r.home_team, "away_team": r.away_team, "fthg": int(r.fthg), "ftag": int(r.ftag)} for r in ordered.itertuples(index=False)],
        "predictions": predictions,
        "external_sources": {
            "summary": {
                "active_sources": ["export/players", "export/matches", "export/events", "events?is_shot=true"],
                "recommended_keep": ["events.csv", "matches.csv", "shots con qualifiers del API"],
                "recommended_remove_or_deprioritize": ["WhoScored HTML crudo como fuente operativa"],
            }
        },
        "workshop_checklist": {
            "xg_logistic_regression": True,
            "match_linear_regression": True,
            "match_logistic_regression": True,
            "bet365_benchmark_reproduced": True,
            "event_rolling_features": True,
            "odds_features": True,
            "qualifiers_used": True,
            "deployed_dashboard_ready": True,
        },
    })

def export_outputs(payload: dict) -> dict[str, Path]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    dashboard_json = OUTPUTS_DIR / "dashboard_data.json"
    dashboard_js = DASHBOARD_DIR / "dashboard_data.js"
    dashboard_inline_json = DASHBOARD_DIR / "dashboard_data.json"
    metrics_json = OUTPUTS_DIR / "model_metrics.json"
    dashboard_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    dashboard_js.write_text(f"window.DASHBOARD_DATA = {json.dumps(payload, ensure_ascii=False, indent=2)};\n", encoding="utf-8")
    dashboard_inline_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics_json.write_text(json.dumps({
        "workshop_checklist": payload["workshop_checklist"],
        "xg_metrics": payload["xg_metrics"],
        "xg_baseline": {
            "always_no_goal_accuracy": payload["xg_metrics"].get("naive_accuracy"),
            "always_no_goal_auc_roc": payload["xg_metrics"].get("naive_auc_roc"),
        },
        "xg_threshold_analysis": payload.get("xg_threshold_analysis", {}),
        "match_logistic_metrics": payload["match_metrics"],
        "match_linear_metrics": payload["linear_metrics"],
        "bet365_benchmark": {
            "holdout_accuracy": payload["match_metrics"].get("bet365_holdout_accuracy"),
            "cv_accuracy": payload["match_metrics"].get("bet365_cv_accuracy"),
        },
        "advanced_metrics": payload["advanced_metrics"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "dashboard_json": dashboard_json,
        "dashboard_js": dashboard_js,
        "dashboard_inline_json": dashboard_inline_json,
        "model_metrics": metrics_json,
    }

