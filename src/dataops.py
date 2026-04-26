from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, DATA_DOCS_DIR, PROCESSED_DATA_DIR
from .data import load_api_context, load_datasets
from .preprocessing import build_event_match_stats, build_match_features, enrich_shots, prepare_matches
from .utils import _save_json


def ensure_dataops_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def _build_feature_catalog() -> dict[str, object]:
    return {
        "shots_enriched": [
            {"name": "distance_to_goal_m", "family": "geometria", "scope": "tiro", "ex_ante": False, "description": "Distancia en metros entre la ubicacion del tiro y el centro de la porteria, tras normalizar la direccion de ataque."},
            {"name": "goal_frame_angle", "family": "geometria", "scope": "tiro", "ex_ante": False, "description": "Angulo efectivo de remate abierto hacia los dos postes desde la posicion del tiro."},
            {"name": "centrality_to_goal", "family": "geometria", "scope": "tiro", "ex_ante": False, "description": "Que tan centrado queda el tiro respecto al arco. Toma valores entre 0 y 1."},
            {"name": "shot_angle_distance_interaction", "family": "geometria", "scope": "tiro", "ex_ante": False, "description": "Interaccion entre angulo y distancia para favorecer tiros cercanos y centrados."},
            {"name": "is_assisted", "family": "contexto_del_tiro", "scope": "tiro", "ex_ante": False, "description": "Indicador de que el remate fue asistido por un companero segun los qualifiers del evento."},
            {"name": "is_individual_play", "family": "contexto_del_tiro", "scope": "tiro", "ex_ante": False, "description": "Indicador de remate generado por accion individual del jugador."},
            {"name": "is_regular_play", "family": "contexto_del_tiro", "scope": "tiro", "ex_ante": False, "description": "Indicador de jugada abierta regular, no asociada a balon parado."},
            {"name": "is_set_piece", "family": "contexto_del_tiro", "scope": "tiro", "ex_ante": False, "description": "Indicador de remate originado en una accion a balon parado."},
            {"name": "score_diff_before_shot", "family": "estado_del_partido", "scope": "tiro", "ex_ante": False, "description": "Diferencia de goles del equipo que remata justo antes del tiro."},
            {"name": "leading_before_shot", "family": "estado_del_partido", "scope": "tiro", "ex_ante": False, "description": "Indicador de que el equipo del tirador ya iba ganando antes del remate."},
            {"name": "trailing_before_shot", "family": "estado_del_partido", "scope": "tiro", "ex_ante": False, "description": "Indicador de que el equipo del tirador iba perdiendo antes del remate."},
            {"name": "shot_number_in_match", "family": "secuencia", "scope": "tiro", "ex_ante": False, "description": "Numero secuencial del tiro dentro de la cronologia completa del partido."},
            {"name": "team_shot_number_in_match", "family": "secuencia", "scope": "tiro", "ex_ante": False, "description": "Numero secuencial del tiro dentro de la cronologia del equipo en ese partido."},
            {"name": "time_since_prev_team_shot_s", "family": "secuencia", "scope": "tiro", "ex_ante": False, "description": "Segundos transcurridos desde el tiro anterior del mismo equipo en el mismo partido."},
            {"name": "player_conversion_last20", "family": "historial_rodante", "scope": "tiro", "ex_ante": True, "description": "Tasa de conversion historica del jugador calculada sobre sus 20 tiros anteriores mediante ventana rodante con shift."},
            {"name": "player_big_chance_rate_last20", "family": "historial_rodante", "scope": "tiro", "ex_ante": True, "description": "Proporcion historica de big chances del jugador sobre sus 20 tiros previos, usando solo informacion pasada."},
            {"name": "team_conversion_last40", "family": "historial_rodante", "scope": "tiro", "ex_ante": True, "description": "Tasa de conversion del equipo calculada sobre sus 40 tiros anteriores, sin usar el tiro actual."},
            {"name": "team_big_chance_rate_last40", "family": "historial_rodante", "scope": "tiro", "ex_ante": True, "description": "Proporcion de big chances del equipo en sus 40 tiros previos, construida solo con historial pasado."},
        ],
        "event_match_features": [
            {"name": "progressive_pass_rate", "family": "estilo_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Proporcion de pases del equipo que avanzan al menos 15 unidades hacia adelante en ese partido."},
            {"name": "shot_accuracy", "family": "ataque_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Relacion entre tiros a puerta y tiros totales del equipo dentro del partido."},
            {"name": "conversion_rate", "family": "ataque_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Relacion entre goles y tiros del equipo en el partido."},
            {"name": "big_chance_rate", "family": "ataque_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Proporcion de tiros clasificados como big chance sobre el total de remates del equipo en ese partido."},
            {"name": "assisted_shot_rate", "family": "ataque_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Proporcion de remates asistidos sobre el total de tiros del equipo en ese partido."},
            {"name": "touches_per_shot", "family": "ataque_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Numero promedio de toques necesarios para producir un remate en ese partido."},
            {"name": "avg_score_diff_before_shot", "family": "contexto_de_equipo", "scope": "equipo_partido", "ex_ante": False, "description": "Promedio del estado del marcador desde el que el equipo remato en ese partido."},
        ],
        "match_features": [
            {"name": "points_diff_last5", "family": "forma_prepartido", "scope": "partido", "ex_ante": True, "description": "Diferencia entre los puntos promedio de local y visitante en sus ultimos 5 partidos, calculada con shift para usar solo historial previo."},
            {"name": "shot_accuracy_diff_last5", "family": "forma_prepartido", "scope": "partido", "ex_ante": True, "description": "Diferencia entre la precision de remate historica de local y visitante en los ultimos 5 partidos previos."},
            {"name": "conversion_rate_diff_last5", "family": "forma_prepartido", "scope": "partido", "ex_ante": True, "description": "Diferencia entre la tasa de conversion historica de ambos equipos en sus ultimos 5 partidos previos."},
            {"name": "big_chance_rate_diff_last5", "family": "forma_prepartido", "scope": "partido", "ex_ante": True, "description": "Diferencia entre la proporcion de big chances de ambos equipos en los ultimos 5 partidos anteriores al encuentro."},
            {"name": "assisted_shot_rate_diff_last5", "family": "forma_prepartido", "scope": "partido", "ex_ante": True, "description": "Diferencia entre la proporcion historica de remates asistidos del local y del visitante en sus ultimos 5 partidos."},
            {"name": "avg_shot_angle_diff_last5", "family": "calidad_de_ocasiones", "scope": "partido", "ex_ante": True, "description": "Diferencia entre el angulo promedio de tiro que generaron ambos equipos en sus ultimos 5 partidos previos."},
            {"name": "avg_score_diff_before_shot_diff_last5", "family": "estado_prepartido", "scope": "partido", "ex_ante": True, "description": "Diferencia entre los estados de marcador desde los que ambos equipos acostumbran rematar, usando solo partidos anteriores."},
            {"name": "market_favorite_strength", "family": "senal_de_mercado", "scope": "partido", "ex_ante": True, "description": "Probabilidad implicita normalizada mas alta de Bet365 antes del partido. Resume la fuerza del favorito de mercado."},
            {"name": "market_entropy_b365", "family": "senal_de_mercado", "scope": "partido", "ex_ante": True, "description": "Entropia de la distribucion implicita de Bet365 antes del partido. Valores bajos indican favorito mas claro."},
            {"name": "home_odds_dispersion", "family": "senal_de_mercado", "scope": "partido", "ex_ante": True, "description": "Dispersion de la cuota local entre casas de apuestas antes del partido."},
            {"name": "ref_avg_yellows_last10", "family": "contexto_arbitral", "scope": "partido", "ex_ante": True, "description": "Promedio rodante de tarjetas amarillas mostradas por el arbitro en sus ultimos 10 partidos previos."},
            {"name": "ref_home_win_rate_last10", "family": "contexto_arbitral", "scope": "partido", "ex_ante": True, "description": "Tasa rodante de victorias locales en los ultimos 10 partidos previos arbitrados por ese juez."},
        ],
    }


def _write_feature_catalog_docs(catalog: dict[str, object]) -> dict[str, Path]:
    catalog_json_path = PROCESSED_DATA_DIR / "feature_catalog.json"
    orchestration_json_path = PROCESSED_DATA_DIR / "artifact_manifest.json"
    feature_markdown_path = DATA_DOCS_DIR / "feature_catalog.md"
    orchestration_markdown_path = DATA_DOCS_DIR / "orchestration.md"

    _save_json(catalog_json_path, catalog)

    feature_lines = [
        "# Feature Catalog",
        "",
        "Catalogo de variables derivadas exportadas por el pipeline local de datos.",
        "",
    ]
    for dataset_name, entries in catalog.items():
        feature_lines.append(f"## {dataset_name}")
        feature_lines.append("")
        for entry in entries:
            feature_lines.append(
                f"- `{entry['name']}`: {entry['description']} "
                f"(familia: `{entry['family']}`, alcance: `{entry['scope']}`, ex_ante: `{entry['ex_ante']}`)"
            )
        feature_lines.append("")
    feature_markdown_path.write_text("\n".join(feature_lines).strip() + "\n", encoding="utf-8")

    orchestration_lines = [
        "# Data Orchestration",
        "",
        "This project uses local raw datasets already committed in `data/`.",
        "",
        "1. `data/events.csv`, `data/matches.csv`, `data/players.csv` are treated as the raw layer.",
        "2. `data/api_cache/shot_events_with_qualifiers.json` enriches shot events with qualifier context.",
        "3. `python data_pipeline.py` builds the processed layer in `data/processed/`.",
        "4. `python pipeline.py` reuses the same processed feature logic before training models and refreshing dashboard outputs.",
        "",
        "Processed artifacts are deterministic and are regenerated from local files only. No data download is required for the standard workflow.",
        "",
    ]
    orchestration_markdown_path.write_text("\n".join(orchestration_lines), encoding="utf-8")
    return {
        "catalog_json": catalog_json_path,
        "feature_markdown": feature_markdown_path,
        "orchestration_markdown": orchestration_markdown_path,
        "manifest_json": orchestration_json_path,
    }


def _export_dataframe(dataframe: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False)
    return path


def build_data_artifacts() -> dict[str, object]:
    ensure_dataops_directories()
    players, matches_raw, events = load_datasets()
    api_shots, _, _ = load_api_context()

    matches = prepare_matches(matches_raw)
    shots = enrich_shots(events, matches, api_shots)
    event_stats = build_event_match_stats(events, shots, matches)
    match_features = build_match_features(matches, event_stats, window=5)

    artifact_paths = {
        "players_raw": DATA_DIR / "players.csv",
        "matches_raw": DATA_DIR / "matches.csv",
        "events_raw": DATA_DIR / "events.csv",
        "matches_prepared": _export_dataframe(matches, PROCESSED_DATA_DIR / "matches_prepared.csv"),
        "shots_enriched": _export_dataframe(shots, PROCESSED_DATA_DIR / "shots_enriched.csv"),
        "event_match_features": _export_dataframe(event_stats, PROCESSED_DATA_DIR / "event_match_features.csv"),
        "match_features": _export_dataframe(match_features, PROCESSED_DATA_DIR / "match_features.csv"),
    }

    catalog = _build_feature_catalog()
    docs = _write_feature_catalog_docs(catalog)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "orchestrator": "python data_pipeline.py",
        "raw_inputs": {
            "players": str(artifact_paths["players_raw"]),
            "matches": str(artifact_paths["matches_raw"]),
            "events": str(artifact_paths["events_raw"]),
            "shot_cache": str(DATA_DIR / "api_cache" / "shot_events_with_qualifiers.json"),
        },
        "artifacts": {
            name: {
                "path": str(path),
                "rows": int(dataframe.shape[0]),
                "columns": dataframe.columns.tolist(),
            }
            for name, path, dataframe in [
                ("matches_prepared", artifact_paths["matches_prepared"], matches),
                ("shots_enriched", artifact_paths["shots_enriched"], shots),
                ("event_match_features", artifact_paths["event_match_features"], event_stats),
                ("match_features", artifact_paths["match_features"], match_features),
            ]
        },
    }
    _save_json(docs["manifest_json"], manifest)

    return {
        "players": players,
        "matches": matches,
        "events": events,
        "shots": shots,
        "event_stats": event_stats,
        "match_features": match_features,
        "artifact_paths": artifact_paths,
        "docs": docs,
        "manifest": manifest,
    }


def main() -> None:
    results = build_data_artifacts()
    print("Data pipeline local ejecutado correctamente.")
    print(f"Shots enriquecidos: {results['shots'].shape[0]}")
    print(f"Features por partido: {results['match_features'].shape[0]}")
    print(f"Artifacts: {results['artifact_paths']['shots_enriched']}")
