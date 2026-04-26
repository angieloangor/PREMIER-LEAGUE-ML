from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import requests

from .config import API_CACHE_DIR, BASE_URL, DATA_DIR, ENDPOINTS
from .utils import _load_json, _save_json


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def existing_files_are_available() -> bool:
    required_files = [DATA_DIR / f"{name}.csv" for name in ENDPOINTS]
    return all(path.exists() for path in required_files)


def download_dataset(name: str, url: str) -> Path:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    dataframe = pd.read_csv(StringIO(response.text))
    destination = DATA_DIR / f"{name}.csv"
    dataframe.to_csv(destination, index=False)
    return destination


def download_base_datasets(force: bool = False) -> list[Path]:
    ensure_directories()
    if not force and existing_files_are_available():
        return sorted(DATA_DIR.glob("*.csv"))

    destinations: list[Path] = []
    for name, url in ENDPOINTS.items():
        destinations.append(download_dataset(name, url))
    return destinations


def main() -> None:
    ensure_directories()

    if existing_files_are_available():
        print("Los archivos de datos ya existen. No es necesario volver a descargarlos.")
        for csv_path in sorted(DATA_DIR.glob("*.csv")):
            print(f"- {csv_path.name}")
        return

    print("Iniciando descarga de datos base...")
    for name, url in ENDPOINTS.items():
        destination = download_dataset(name, url)
        print(f"{name}.csv descargado en {destination}")

    print("Descarga completada.")


def load_datasets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    players = pd.read_csv(DATA_DIR / "players.csv")
    matches = pd.read_csv(DATA_DIR / "matches.csv")
    events = pd.read_csv(DATA_DIR / "events.csv")
    return players, matches, events

def _fetch_json(url: str):
    with urlopen(url, timeout=120) as response:
        return json.load(response)

def _load_cached_api_rows(cache_name: str, url: str, root_key: str) -> list[dict]:
    API_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = API_CACHE_DIR / cache_name
    if cache_path.exists():
        return _load_json(cache_path)
    payload = _fetch_json(url)
    rows = payload[root_key] if isinstance(payload, dict) else payload
    _save_json(cache_path, rows)
    return rows

def load_api_context() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    shots = pd.DataFrame(
        _load_cached_api_rows(
            "shot_events_with_qualifiers.json",
            f"{BASE_URL}/events?is_shot=true&limit=10000&format=json",
            "events",
        )
    )
    teams = pd.DataFrame(_load_cached_api_rows("teams.json", f"{BASE_URL}/teams", "teams"))
    referees = pd.DataFrame(_load_cached_api_rows("referees.json", f"{BASE_URL}/referees", "referees"))
    return shots, teams, referees

