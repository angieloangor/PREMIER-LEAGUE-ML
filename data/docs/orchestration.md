# Data Orchestration

This project uses local raw datasets already committed in `data/`.

1. `data/events.csv`, `data/matches.csv`, `data/players.csv` are treated as the raw layer.
2. `data/api_cache/shot_events_with_qualifiers.json` enriches shot events with qualifier context.
3. `python data_pipeline.py` builds the processed layer in `data/processed/`.
4. `python pipeline.py` reuses the same processed feature logic before training models and refreshing dashboard outputs.

Processed artifacts are deterministic and are regenerated from local files only. No data download is required for the standard workflow.
