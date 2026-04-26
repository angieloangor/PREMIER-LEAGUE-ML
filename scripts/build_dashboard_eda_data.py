from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

SHOTS_PATH = PROCESSED_DIR / "shots_features.csv"
MATCHES_PATH = PROCESSED_DIR / "matches_features.csv"
SUMMARY_PATH = PROCESSED_DIR / "eda_summary.json"
OUTPUT_PATH = DASHBOARD_DIR / "dashboard_eda_data.json"
EMBEDDED_OUTPUT_PATH = DASHBOARD_DIR / "dashboard_eda_data_embedded.js"

XG_FEATURES = [
    "shot_distance",
    "shot_angle",
    "is_big_chance",
    "is_header",
    "is_right_foot",
    "is_left_foot",
    "is_penalty",
    "is_volley",
    "first_touch",
    "from_corner",
    "is_counter",
]

MATCH_ROLLING_FEATURES = [
    "rolling_home_goals_for_last5",
    "rolling_home_goals_against_last5",
    "rolling_away_goals_for_last5",
    "rolling_away_goals_against_last5",
    "rolling_home_points_last5",
    "rolling_away_points_last5",
    "rolling_home_win_rate_last5",
    "rolling_away_win_rate_last5",
]

LEAKAGE_TABLE = [
    {
        "feature": "Odds pre-partido (B365H, B365D, B365A)",
        "tipo": "pre-partido valida",
        "razon": "Estan disponibles antes del kickoff y funcionan como benchmark de mercado.",
    },
    {
        "feature": "Equipo local, equipo visitante y arbitro",
        "tipo": "pre-partido valida",
        "razon": "Son datos conocidos antes del partido; requieren encoding si entran al modelo.",
    },
    {
        "feature": "Rolling goals, points y win rate last5",
        "tipo": "pre-partido valida",
        "razon": "Se calculan con shift(1), usando solo partidos anteriores.",
    },
    {
        "feature": "Shots y shots on target del partido actual",
        "tipo": "post-partido leakage",
        "razon": "Describen lo que ya ocurrio durante el partido objetivo.",
    },
    {
        "feature": "Corners del partido actual",
        "tipo": "post-partido leakage",
        "razon": "No existen antes del kickoff y filtrarian informacion del resultado.",
    },
    {
        "feature": "Fouls, yellow cards y red cards del partido actual",
        "tipo": "post-partido leakage",
        "razon": "Son eventos observados durante el partido y no son validos para prediccion real.",
    },
    {
        "feature": "FTHG, FTAG, total_goals y goal_diff",
        "tipo": "post-partido leakage",
        "razon": "Son targets o derivadas directas del resultado final.",
    },
]


def warn(message: str) -> None:
    warnings.warn(message, stacklevel=2)
    print(f"WARNING: {message}")


def read_csv_if_exists(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        warn(f"No se encontro {name}: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        warn(f"No se pudo leer {name}: {exc}")
        return pd.DataFrame()


def read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        warn(f"No se encontro eda_summary.json: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(f"No se pudo leer eda_summary.json: {exc}")
        return {}


def require_columns(df: pd.DataFrame, columns: list[str], frame_name: str) -> bool:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        warn(f"{frame_name}: faltan columnas {missing}")
        return False
    return True


def finite_number(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(number):
        return default
    return number


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if pd.isna(value):
        return None
    return value


def conversion_by_flag(df: pd.DataFrame, column: str, labels: dict[int, str]) -> list[dict[str, Any]]:
    if not require_columns(df, [column, "is_goal"], "shots_features"):
        return []
    temp = df[[column, "is_goal"]].copy()
    temp[column] = pd.to_numeric(temp[column], errors="coerce").fillna(0).astype(int)
    temp["is_goal"] = pd.to_numeric(temp["is_goal"], errors="coerce").fillna(0).astype(int)
    grouped = (
        temp.groupby(column, as_index=False)
        .agg(shots=("is_goal", "size"), goals=("is_goal", "sum"), conversion_rate=("is_goal", "mean"))
        .sort_values(column)
    )
    return [
        {
            "label": labels.get(int(row[column]), str(row[column])),
            "value": int(row[column]),
            "shots": int(row["shots"]),
            "goals": int(row["goals"]),
            "conversion_rate": float(row["conversion_rate"]),
        }
        for _, row in grouped.iterrows()
    ]


def conversion_by_category(df: pd.DataFrame, column: str, top_n: int | None = None) -> list[dict[str, Any]]:
    if not require_columns(df, [column, "is_goal"], "shots_features"):
        return []
    temp = df[[column, "is_goal"]].copy()
    temp[column] = temp[column].fillna("Unknown").astype(str)
    temp["is_goal"] = pd.to_numeric(temp["is_goal"], errors="coerce").fillna(0).astype(int)
    grouped = (
        temp.groupby(column, as_index=False)
        .agg(shots=("is_goal", "size"), goals=("is_goal", "sum"), conversion_rate=("is_goal", "mean"))
        .sort_values(["shots", "conversion_rate"], ascending=[False, False])
    )
    if top_n:
        grouped = grouped.head(top_n)
    return [
        {
            "label": str(row[column]),
            "shots": int(row["shots"]),
            "goals": int(row["goals"]),
            "conversion_rate": float(row["conversion_rate"]),
        }
        for _, row in grouped.iterrows()
    ]


def conversion_by_bins(df: pd.DataFrame, column: str, bins: int = 8) -> list[dict[str, Any]]:
    if not require_columns(df, [column, "is_goal"], "shots_features"):
        return []
    temp = df[[column, "is_goal"]].copy()
    temp[column] = pd.to_numeric(temp[column], errors="coerce")
    temp["is_goal"] = pd.to_numeric(temp["is_goal"], errors="coerce").fillna(0).astype(int)
    temp = temp.dropna(subset=[column])
    if temp.empty:
        return []

    try:
        temp["bin"] = pd.cut(temp[column], bins=bins, duplicates="drop")
    except ValueError as exc:
        warn(f"No se pudieron crear bins para {column}: {exc}")
        return []

    grouped = (
        temp.groupby("bin", observed=False)
        .agg(mean_value=(column, "mean"), shots=("is_goal", "size"), goals=("is_goal", "sum"), conversion_rate=("is_goal", "mean"))
        .dropna(subset=["mean_value"])
        .reset_index()
    )
    return [
        {
            "label": f"{row['bin'].left:.1f}-{row['bin'].right:.1f}",
            "mean_value": float(row["mean_value"]),
            "shots": int(row["shots"]),
            "goals": int(row["goals"]),
            "conversion_rate": float(row["conversion_rate"]),
        }
        for _, row in grouped.iterrows()
    ]


def qualifier_tokens(text: Any) -> set[str]:
    raw = str(text or "").lower()
    tokens = set(re.findall(r"[a-z][a-z0-9_]{2,}", raw))
    ignored = {
        "zone",
        "center",
        "relatedeventid",
        "oppositerelatedevent",
        "goalmouthy",
        "goalmouthz",
        "blockedx",
        "blockedy",
    }
    return {token for token in tokens if token not in ignored and not token.isdigit()}


def qualifier_tables(shots: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not require_columns(shots, ["qualifier_text", "is_goal"], "shots_features"):
        return [], []

    rows: list[dict[str, Any]] = []
    for shot_id, text, is_goal in shots[["id", "qualifier_text", "is_goal"]].itertuples(index=False, name=None):
        for token in qualifier_tokens(text):
            rows.append({"id": shot_id, "qualifier": token, "is_goal": int(is_goal)})

    if not rows:
        return [], []

    long_df = pd.DataFrame(rows)
    frequency = (
        long_df.groupby("qualifier", as_index=False)
        .agg(shots=("id", "nunique"))
        .sort_values("shots", ascending=False)
        .head(15)
    )
    conversion = (
        long_df.groupby("qualifier", as_index=False)
        .agg(shots=("id", "nunique"), goals=("is_goal", "sum"), conversion_rate=("is_goal", "mean"))
        .query("shots >= 20")
        .sort_values(["conversion_rate", "shots"], ascending=[False, False])
        .head(15)
    )
    return (
        [{"qualifier": str(row["qualifier"]), "shots": int(row["shots"])} for _, row in frequency.iterrows()],
        [
            {
                "qualifier": str(row["qualifier"]),
                "shots": int(row["shots"]),
                "goals": int(row["goals"]),
                "conversion_rate": float(row["conversion_rate"]),
            }
            for _, row in conversion.iterrows()
        ],
    )


def counts_table(series: pd.Series, order: list[Any] | None = None, labels: dict[Any, str] | None = None) -> list[dict[str, Any]]:
    counts = series.value_counts(dropna=False)
    if order:
        counts = counts.reindex(order).fillna(0).astype(int)
    rows = []
    for key, value in counts.items():
        label = labels.get(key, key) if labels else key
        rows.append({"label": str(label), "value": int(value)})
    return rows


def bet365_tables(matches: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float | None]:
    required = ["b365h", "b365d", "b365a", "ftr"]
    if not require_columns(matches, required, "matches_features"):
        return [], [], None
    temp = matches[required].copy()
    for col in ["b365h", "b365d", "b365a"]:
        temp[col] = pd.to_numeric(temp[col], errors="coerce")
    temp = temp.dropna(subset=["b365h", "b365d", "b365a", "ftr"])
    if temp.empty:
        return [], [], None
    temp["bet365_pred"] = temp[["b365h", "b365d", "b365a"]].idxmin(axis=1).map({"b365h": "H", "b365d": "D", "b365a": "A"})
    accuracy = float((temp["bet365_pred"] == temp["ftr"]).mean())

    crosstab = pd.crosstab(temp["bet365_pred"], temp["ftr"]).reindex(index=["H", "D", "A"], columns=["H", "D", "A"], fill_value=0)
    favorite_vs_actual = [
        {"favorite": pred, "actual": actual, "matches": int(crosstab.loc[pred, actual])}
        for pred in ["H", "D", "A"]
        for actual in ["H", "D", "A"]
    ]

    confusion = pd.crosstab(temp["ftr"], temp["bet365_pred"]).reindex(index=["H", "D", "A"], columns=["H", "D", "A"], fill_value=0)
    confusion_rows = [
        {"actual": actual, "predicted": pred, "matches": int(confusion.loc[actual, pred])}
        for actual in ["H", "D", "A"]
        for pred in ["H", "D", "A"]
    ]
    return favorite_vs_actual, confusion_rows, accuracy


def build_payload() -> dict[str, Any]:
    shots = read_csv_if_exists(SHOTS_PATH, "shots_features.csv")
    matches = read_csv_if_exists(MATCHES_PATH, "matches_features.csv")
    summary = read_summary(SUMMARY_PATH)

    top_qualifiers_frequency, top_qualifiers_conversion = qualifier_tables(shots)
    favorite_vs_actual, bet365_confusion_matrix, bet365_accuracy = bet365_tables(matches)

    shot_goals = int(pd.to_numeric(shots.get("is_goal", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not shots.empty else 0
    total_shots = int(len(shots))
    shot_conversion_rate = finite_number(summary.get("shot_conversion_rate"))
    if shot_conversion_rate is None and total_shots:
        shot_conversion_rate = shot_goals / total_shots

    total_goals = summary.get("total_goals")
    if total_goals is None and "total_goals" in matches.columns:
        total_goals = int(pd.to_numeric(matches["total_goals"], errors="coerce").fillna(0).sum())

    summary_cards = {
        "total_matches": int(summary.get("total_matches", len(matches))),
        "total_events": int(summary.get("total_events", 0)),
        "total_shots": total_shots or int(summary.get("total_shots", 0)),
        "total_goals": int(total_goals or 0),
        "shot_conversion_rate": shot_conversion_rate,
        "bet365_accuracy": bet365_accuracy if bet365_accuracy is not None else finite_number(summary.get("bet365_accuracy")),
        "home_win_rate": finite_number(summary.get("home_win_rate")),
        "draw_rate": finite_number(summary.get("draw_rate")),
        "away_win_rate": finite_number(summary.get("away_win_rate")),
        "xg_naive_baseline_accuracy": 1 - shot_conversion_rate if shot_conversion_rate is not None else None,
    }

    result_order = ["H", "D", "A"]
    result_labels = {"H": "Home", "D": "Draw", "A": "Away"}
    over_under = []
    if "total_goals" in matches.columns:
        total_goals_numeric = pd.to_numeric(matches["total_goals"], errors="coerce")
        over_under = counts_table(
            pd.Series(np.where(total_goals_numeric > 2.5, "Over 2.5", "Under 2.5")),
            order=["Under 2.5", "Over 2.5"],
        )

    payload = {
        "summary_cards": summary_cards,
        "shot_eda": {
            "goals_vs_no_goals": counts_table(
                pd.to_numeric(shots.get("is_goal", pd.Series(dtype=float)), errors="coerce").fillna(0).astype(int).map({0: "No gol", 1: "Gol"}),
                order=["No gol", "Gol"],
            )
            if not shots.empty
            else [],
            "conversion_by_big_chance": conversion_by_flag(shots, "is_big_chance", {0: "No BigChance", 1: "BigChance"}),
            "conversion_by_penalty": conversion_by_flag(shots, "is_penalty", {0: "No penal", 1: "Penal"}),
            "conversion_by_body_part": conversion_by_category(shots, "body_part"),
            "conversion_by_shot_distance_bins": conversion_by_bins(shots, "shot_distance", bins=8),
            "conversion_by_angle_bins": conversion_by_bins(shots, "shot_angle", bins=8),
            "top_qualifiers_frequency": top_qualifiers_frequency,
            "top_qualifiers_conversion_min_20": top_qualifiers_conversion,
        },
        "match_eda": {
            "result_distribution_HDA": counts_table(matches["ftr"], order=result_order, labels=result_labels) if "ftr" in matches.columns else [],
            "total_goals_distribution": counts_table(pd.to_numeric(matches["total_goals"], errors="coerce").dropna().astype(int).sort_values()) if "total_goals" in matches.columns else [],
            "over_under_2_5": over_under,
            "bet365_favorite_vs_actual": favorite_vs_actual,
            "bet365_confusion_matrix": bet365_confusion_matrix,
            "bet365_accuracy": bet365_accuracy if bet365_accuracy is not None else finite_number(summary.get("bet365_accuracy")),
        },
        "feature_engineering": {
            "xg_features": XG_FEATURES,
            "match_predictor_features": MATCH_ROLLING_FEATURES,
            "data_leakage_table": [{**row, "razón": row["razon"]} for row in LEAKAGE_TABLE],
        },
        "insights": [
            "El dataset de tiros esta fuertemente desbalanceado: solo cerca del 11% termina en gol.",
            "BigChance aumenta notablemente la conversion, por eso se usa como feature xG.",
            "La distancia al arco tiene relacion inversa con la probabilidad de gol.",
            "Bet365 funciona como benchmark fuerte cercano al 50%.",
            "Las estadisticas del partido actual no deben usarse para prediccion real porque generan data leakage.",
            "Las rolling features usan shift(1), asi que solo incorporan informacion previa al partido.",
        ],
    }
    return to_jsonable(payload)


def main() -> None:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    embedded_json_text = json.dumps(payload, ensure_ascii=True, indent=2)
    OUTPUT_PATH.write_text(json_text, encoding="utf-8")
    EMBEDDED_OUTPUT_PATH.write_text(
        "window.DASHBOARD_EDA_DATA = " + embedded_json_text + ";\n",
        encoding="utf-8",
    )
    print(f"Dashboard EDA data generated: {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Embedded EDA data generated: {EMBEDDED_OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Summary cards: {payload.get('summary_cards', {})}")


if __name__ == "__main__":
    main()
