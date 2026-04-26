# API del predictor de partidos

Backend profesional en FastAPI para servir los mejores paquetes de modelos entrenados del directorio `outputs/`.

## Qué carga

- Por defecto, la API toma como raíz `outputs/model_runs/advanced_match_predictor/stage2_classifier_runs`.
- Desde esa carpeta usa `src/models/select_best_model.py` para rankear automáticamente los bundles de `stage2`.
- Carga hasta `3` pipelines usando ese ranking; el `rank = 1` queda como modelo por defecto.
- Cada pipeline se reconstruye así:
  - `run_summary.json` del bundle de `stage2`;
  - `classifier.joblib` o `classifier.pt` de esa misma carpeta;
  - `regressor.joblib` o `regressor.pt` del `stage1` referenciado por el `run_summary`.

## Qué espera la API

La API de predicción de partidos ahora espera filas crudas de pre-partido, con una estructura equivalente a la capa `data/matches.csv` para las variables disponibles antes del kickoff.

Columnas mínimas esperadas por fila:

- `date`
- `time`
- `home_team`
- `away_team`
- `referee`
- `b365h`, `b365d`, `b365a`
- `bwh`, `bwd`, `bwa`
- `maxh`, `maxd`, `maxa`
- `avgh`, `avgd`, `avga`

La API usa el histórico local en `data/` y `data/processed/` para reconstruir internamente las variables rolling y diferenciales.  
Los datos enviados por el usuario se usan solo dentro del request; no se persisten.

Flujo interno:

1. valida el payload crudo;
2. toma `matches_prepared.csv` y `event_match_features.csv` del proyecto;
3. agrega la fila entrante solo en memoria;
4. reconstruye `match_features` para esa fila usando el mismo pipeline de `src/preprocessing.py`;
5. rellena faltantes residuales con medianas históricas locales cuando aplica;
6. ejecuta `stage1`;
7. crea las features generadas declaradas en `run_summary.json` como `generated_feature_columns`;
8. arma el input final del `stage2`;
9. retorna predicciones y probabilidades.

Esto evita pedirle al cliente decenas de variables derivadas y mantiene la inferencia alineada con el entrenamiento.

Compatibilidad: si un cliente ya envía filas en formato `match_features`, la API también las acepta.

## Endpoints principales

- `GET /health`
- `GET /ready`
- `GET /api/v1/models`
- `GET /api/v1/model-info`
- `GET /api/v1/models/{model_id}`
- `GET /api/v1/models_variables`
- `GET /api/v1/models_variables/{model_id}`
- `POST /api/v1/matches/predict-goals`
- `POST /api/v1/matches/predict-winner`
- `POST /api/v1/matches/predict-full`
- `POST /api/v1/matches/predict-full-csv`
- `POST /predict/match`
- `POST /predict/xg`

Los endpoints `/predict/match` y `/predict/xg` estan pensados para el dashboard. `/predict/match` recibe solo `home_team` y `away_team`: intenta encontrar ese fixture en `data/matches.csv`, reconstruye internamente sus features con el mismo flujo de la API normal y, si no puede, responde con fallback estatico/mercado sin romper la UI. `/predict/xg` usa un fallback logistico documentado cuando no hay artefacto xG registrado en la API.

## Ejecución local

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

## Example JSON request

```json
{
  "model_id": "dominance_index__random_forest_regressor+dominance_index+feature_generator__catboost_classifier+extra",
  "records": [
    {
      "date": "27/04/2026",
      "time": "20:00",
      "home_team": "Liverpool",
      "away_team": "Arsenal",
      "referee": "A Taylor",
      "b365h": 2.1,
      "b365d": 3.2,
      "b365a": 3.5,
      "bwh": 2.15,
      "bwd": 3.25,
      "bwa": 3.45,
      "maxh": 2.2,
      "maxd": 3.35,
      "maxa": 3.6,
      "avgh": 2.13,
      "avgd": 3.22,
      "avga": 3.48
    }
  ]
}
```

Si quieres inspeccionar qué variables usa cada pipeline ya construido:

- `GET /api/v1/models` devuelve solo el catálogo compacto.
- `GET /api/v1/models_variables` devuelve las columnas de `stage1` y `stage2`.
