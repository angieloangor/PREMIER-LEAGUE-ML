from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


AUXILIARY_INDEX_COLUMNS = [
    "threat_index",
    "dominance_index",
    "efficiency_control_index",
    "territorial_pressure_index",
    "clean_dominance_index",
]


def safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.where(b == 0, 0.0, a / b)


def build_candidate_indices(matches: pd.DataFrame) -> pd.DataFrame:
    """
    Construye índices auxiliares ex post a partir de estadísticas reales del partido.

    Estos índices no deben entrar directamente como features del clasificador pre-match.
    Deben usarse como targets auxiliares para el Stage 1.
    """

    df = matches.copy()
    required_cols = [
        "hs",
        "as_",
        "hst",
        "ast",
        "hc",
        "ac",
        "hf",
        "af",
        "hy",
        "ay",
        "hr",
        "ar",
    ]
    missing = [column for column in required_cols if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for auxiliary indices: {missing}")

    raw = pd.DataFrame(index=df.index)
    raw["shots_diff"] = df["hs"].astype(float) - df["as_"].astype(float)
    raw["sot_diff"] = df["hst"].astype(float) - df["ast"].astype(float)
    raw["corners_diff"] = df["hc"].astype(float) - df["ac"].astype(float)
    raw["home_shot_accuracy"] = safe_div(df["hst"], df["hs"])
    raw["away_shot_accuracy"] = safe_div(df["ast"], df["as_"])
    raw["accuracy_diff"] = raw["home_shot_accuracy"] - raw["away_shot_accuracy"]
    raw["card_diff"] = (df["hy"].astype(float) + 2 * df["hr"].astype(float)) - (
        df["ay"].astype(float) + 2 * df["ar"].astype(float)
    )
    raw["foul_diff"] = df["hf"].astype(float) - df["af"].astype(float)

    scaler = StandardScaler()
    z = pd.DataFrame(scaler.fit_transform(raw), columns=raw.columns, index=raw.index)

    indices = pd.DataFrame(index=df.index)
    indices["threat_index"] = (0.70 * z["sot_diff"]) + (0.30 * z["shots_diff"])
    indices["dominance_index"] = (
        0.35 * z["shots_diff"] + 0.50 * z["sot_diff"] + 0.15 * z["corners_diff"]
    )
    indices["efficiency_control_index"] = (
        0.50 * z["sot_diff"] + 0.30 * z["shots_diff"] + 0.20 * z["accuracy_diff"]
    )
    indices["territorial_pressure_index"] = (
        0.45 * z["corners_diff"] + 0.35 * z["shots_diff"] + 0.20 * z["sot_diff"]
    )
    indices["clean_dominance_index"] = (
        0.45 * z["sot_diff"]
        + 0.30 * z["shots_diff"]
        + 0.15 * z["corners_diff"]
        - 0.05 * z["card_diff"]
        - 0.05 * z["foul_diff"]
    )
    return indices
