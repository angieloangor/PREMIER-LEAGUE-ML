from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DATA_DOCS_DIR = DATA_DIR / "docs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
API_CACHE_DIR = DATA_DIR / "api_cache"
BASE_URL = "https://premier.72-60-245-2.sslip.io"

MATCH_RESULT_NAMES = ["Local", "Empate", "Visitante"]
BET365_BENCHMARK_ACCURACY = 0.498
PITCH_LENGTH_METERS = 105.0
PITCH_WIDTH_METERS = 68.0
TEAM_NAME_MAP = {
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Man Utd": "Man United",
    "Man Utd.": "Man United",
    "Nottm Forest": "Nottingham Forest",
    "Nott'm Forest": "Nottingham Forest",
    "Tottenham Hotspur": "Tottenham",
    "Spurs": "Tottenham",
    "Wolverhampton Wanderers": "Wolves",
    "Wolverhampton": "Wolves",
}

ENDPOINTS = {
    "players": "https://premier.72-60-245-2.sslip.io/export/players",
    "matches": "https://premier.72-60-245-2.sslip.io/export/matches",
    "events": "https://premier.72-60-245-2.sslip.io/export/events",
}
