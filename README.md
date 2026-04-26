# PremierLeagueML

**Integrantes:** Angie Loango, Jorge Zainea
**Repositorio:** [https://github.com/angieloangor/PREMIER-LEAGUE-ML](https://github.com/angieloangor/PREMIER-LEAGUE-ML)
**Dashboard desplegado:** (No desplegado, ejecutar localmente siguiendo instrucciones)
**Dashboard local:** http://localhost:8000/dashboard/

---

Pipeline reproducible de Machine Learning para fútbol con tres capas principales:

- `data/`: datos base, artefactos procesados y documentación DataOps
- `src/`: feature engineering, entrenamiento y selección de modelos
- `api/`: backend FastAPI para servir el predictor de partidos

El repositorio está pensado para trabajo académico y de ingeniería aplicada: datos locales reproducibles, barridos controlados de modelos, dashboard estático y serving con bundles versionados.

## Ejecución Local (Desde la raíz)

Para poner en marcha el sistema completo, siga estos pasos desde la raíz del proyecto:

### 1. Iniciar la API
```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

### 2. Iniciar el Dashboard (en otra terminal)
```bash
python -m http.server 8000
```
Abrir: http://localhost:8000/dashboard/

### 3. Automatización (Windows)
Se incluye el archivo `run_all.bat` que levanta automáticamente ambos servicios en terminales independientes:
```cmd
run_all.bat
```

---

## Índice

- [Arquitectura](#arquitectura)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [CLI Workflow](#cli-workflow)
- [Datos](#datos)
- [EDA y Feature Engineering](#eda-y-feature-engineering)
- [Generación de features](#generación-de-features)
- [Entrenamiento](#entrenamiento)
- [Selección de mejores modelos](#selección-de-mejores-modelos)
- [API](#api)
- [Dashboard](#dashboard)
- [Configuración](#configuración)
- [Tests y CI](#tests-y-ci)

## Arquitectura

Para el taller y para la parte aplicada del proyecto hay tres variantes de modelado que conviene distinguir explícitamente:

1. **Modelo xG del taller**
   - estima probabilidad de gol por tiro;
   - vive en el workflow legacy;
   - es uno de los dos modelos base obligatorios del taller.
2. **Match Predictor baseline del taller**
   - predice el resultado `H / D / A`;
   - usa el enfoque baseline implementado en `src/legacy_models.py`;
   - también hace parte de los dos modelos base obligatorios del taller.
3. **Full ML Match Predictor**
   - es la variante extendida del proyecto;
   - en ambas versiones se prueban familias de modelos más avanzadas, incluyendo enfoques lineales, árboles/boosting y redes neuronales con `torch`, además de búsqueda de hiperparámetros para seleccionar la mejor combinación;
   - incluye un modo básico de dos modelos:
     1. **stage 1**: un regresor estima goles esperados del partido usando solo información disponible antes del kickoff;
     2. **stage 2**: un clasificador usa esas señales prepartido, junto con la salida del stage 1, para predecir el resultado final `H / D / A`.
   - e incluye un modo avanzado de prediccion de victoria de dos pasos, pensando para superar al benckmark propuesto en el taller:
     1. **stage 1**: uno o varios regresores aproximan features sintéticas del partido (índices compuestos informativos) a partir del histórico y las odds prepartido;
     2. **stage 2**: un clasificador usa esas features generadas como señales adicionales para mejorar la predicción del resultado del partido.


En otras palabras:

- `legacy` = los dos modelos base del taller (`xG` + predictor baseline de partido);
- `basic-match-predictor` = la primera versión Full ML de partido con regresor de goles + clasificador;
- `advanced-match-predictor` = la versión Full ML más fuerte, en dos steps con feature generation.

La capa de datos no descarga nada en el flujo estándar. Trabaja con los CSV ya presentes en `data/` y con el cache local de `data/api_cache/`.

## Ensemble de modelos

El predictor de partidos utiliza un **ensemble de múltiples modelos** (provenientes de `stage2_classifier_runs`), combinados mediante **promedio ponderado de probabilidades**.

Esto permite:

- **Mayor estabilidad** en predicciones (reduce variancia de un modelo individual);
- **Mejor accuracy** que usar un único modelo;
- **Superar el benchmark** de Bet365 (49.80% en el conjunto de validación).

El sistema ensemble:

- carga múltiples modelos clasificadores (`top_k` configurable en `config/api/default.yaml`);
- **pondera cada modelo** según su rendimiento (accuracy en validación);
- aplica **fallback automático** si algún modelo falla durante la predicción;
- está transparente en la respuesta de predicción: incluye `mode: "ensemble"` y `ensemble_size`.

### Verificación del ensemble

Puedes consultar el estado del ensemble en la API:

```bash
curl http://localhost:8001/api/v1/ensemble-info
```

Respuesta esperada:

```json
{
  "total_models_loaded": 5,
  "weights": [0.25, 0.25, 0.20, 0.15, 0.15],
  "model_ids": ["model_1", "model_2", "model_3", "model_4", "model_5"]
}
```

En el dashboard, cuando el ensemble está activo, la sección de estado mostrará:

```
Modo API · Ensemble activo (5)
```

## Estructura del repositorio

```text
PremierLeagueML/
|-- api/                  # FastAPI backend y servicios de inferencia
|-- config/               # YAMLs de entrenamiento, API y experimentos
|-- dashboard/            # Frontend estático
|-- data/
|   |-- api_cache/        # cache local para enriquecer eventos
|   |-- docs/             # documentación DataOps
|   `-- processed/        # artefactos procesados
|-- notebooks/            # notebooks de exploración y entrenamiento
|-- outputs/              # métricas, modelos exportados y payloads
|-- scripts/              # CLIs operativos del proyecto
|-- src/
|   |-- models/           # registry, runner y specs de modelos
|   `-- ...               # dataops, preprocessing, pipeline, dashboard
|-- tests/                # smoke tests del proyecto
|-- data_pipeline.py      # shim de compatibilidad
|-- pipeline.py           # shim de compatibilidad
|-- workshop_pipeline.py  # shim de compatibilidad
`-- pyproject.toml
```

## Instalación

### Opción 1: con `pip`

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Opción 2: editable para desarrollo

```bash
python -m pip install --upgrade pip
pip install -e .[dev]
```

Esto además instala estos comandos:

- `plml-ingest`
- `plml-preprocess`
- `plml-train`
- `plml-serve-api`

## Desarrollo Local

Para desarrollo local, puedes usar el script `run_all.bat` que automáticamente levanta ambos servicios:

- **API FastAPI** en `http://localhost:8001`
- **Dashboard** en `http://localhost:8000/dashboard/`

```cmd
# Desde el directorio raíz del proyecto
run_all.bat
```

El script abre dos terminales separadas, una para cada servicio. Presiona cualquier tecla para cerrar el script inicial.

### Predicción por CSV desde el dashboard

El dashboard ahora incluye un botón flotante "CSV Predict" en la esquina inferior derecha. Al abrirlo puedes:

- elegir entre cuatro tipos de predicción
- subir un archivo `.csv`
- enviar la petición a la API en `http://localhost:8001`
- ver un resumen de resultados y una vista previa de las primeras filas
- descargar el archivo resultante con las predicciones incluidas

Si la API no está activa, el modal mostrará un aviso claro: 
"Esta función requiere la API activa. Ejecuta `run_all.bat` o levanta la API en el puerto 8001."

### Formato de CSV esperado

La API usa `POST /predict/batch` y recibe un campo `task`. El dashboard muestra nombres amigables, pero estos son los valores internos:

| Opción en dashboard | task | Columnas mínimas | Salida principal |
| --- | --- | --- | --- |
| xG por tiro | `xg` | `x,y` | `xg_prediction`, `shot_quality_label` |
| Resultado de partido H/D/A | `match_result` | `home_team,away_team` | probabilidades H/D/A y `predicted_result` |
| Goles esperados del partido | `match_goals` | `home_team,away_team` | `expected_goals` |
| Predictor completo de partido | `match_full` | `home_team,away_team` | probabilidades H/D/A, `predicted_result`, `expected_goals` |

El task histórico `match` se mantiene como alias de `match_full`.

#### Ejemplo mínimo para `xG por tiro`

```csv
x,y
88,50
75,40
```

Las columnas `x` y `y` son obligatorias. Otras columnas opcionales pueden faltar y se rellenarán con valores por defecto.

#### Ejemplo mínimo para predicciones de partido

```csv
home_team,away_team
Arsenal,Chelsea
Liverpool,Everton
```

Si el modelo real no está disponible, la respuesta marca `mode=fallback` y el dashboard muestra: "Modo fallback: predicción basada en datos estáticos/reglas simples."

### Servicios individuales

Si prefieres ejecutar servicios individualmente:

```bash
# API FastAPI
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001

# Dashboard (desde dashboard/)
cd dashboard && python -m http.server 8000
```

## CLI Workflow

El flujo recomendado del repo ya no es ejecutar archivos sueltos en la raíz.  
Ahora la operación normal vive en `scripts/`.

### 1. Ingesta de datos

Valida que los CSV base existan o los descarga si lo indicas:

```bash
python -m scripts.ingest_data
```

Forzar descarga:

```bash
python -m scripts.ingest_data --force-download
```

O con entrypoint instalado:

```bash
plml-ingest --force-download
```

### 2. Preprocesamiento de datos

Reconstruye la capa procesada y la documentación DataOps:

```bash
python -m scripts.preprocess_data
```

O:

```bash
plml-preprocess
```

### 3. Entrenamiento custom

La CLI principal de entrenamiento ahora deja explícitas las tres variantes relevantes del proyecto:

#### 3.1 Workflow `legacy`

Es el workflow del taller. Corre los dos modelos base exigidos:

- modelo xG;
- predictor baseline de partido.

Comando:

```bash
python -m scripts.train_custom --workflow legacy
```

Equivalentes de compatibilidad:

```bash
python pipeline.py
python workshop_pipeline.py
```

#### 3.2 Workflow `basic-match-predictor`

Es la primera variante Full ML del predictor de partidos.

Usa dos modelos:

1. un regresor para goles;
2. un clasificador para `H / D / A`.

Comando recomendado:

```bash
python -m scripts.train_custom --workflow basic-match-predictor
```

Config por defecto:

```text
config/experiments/match_predictor_basic.yaml
```

Alias legacy-compatible:

```bash
python -m scripts.train_custom --workflow match-predictor
```

#### 3.3 Workflow `advanced-match-predictor`

Es la variante Full ML más fuerte del proyecto.

Usa dos steps:

1. `stage1_feature_generators`: regresores que aproximan métricas sintéticas del partido a partir de información ex ante;
2. `stage2_classifier_runs`: clasificadores que usan esas features generadas junto con odds e histórico.

Comando recomendado:

```bash
python -m scripts.train_custom --workflow advanced-match-predictor
```

Config por defecto:

```text
config/experiments/match_predictor_advanced.yaml
```

#### 3.4 Ejemplos útiles

Smoke run rápido del predictor básico:

```bash
python -m scripts.train_custom \
  --workflow basic-match-predictor \
  --config config/training/quick_smoke.yaml
```

Sweep controlado del predictor básico:

```bash
python -m scripts.train_custom \
  --workflow basic-match-predictor \
  --session-name basic_match_cli \
  --regressors linear_regression,knn_regressor,random_forest_regressor \
  --classifiers knn_classifier,ridge_classifier,elasticnet_classifier \
  --feature-modes normal,lasso_selected \
  --winner-feature-set winner_default \
  --search-iterations 4 \
  --cv-splits 3 \
  --holdout-ratio 0.2
```

Sweep del predictor avanzado:

```bash
python -m scripts.train_custom \
  --workflow advanced-match-predictor \
  --session-name advanced_match_cli \
  --stage1-top-k 3
```

Si quieres apagar SMOTE en los workflows Full ML:

```bash
python -m scripts.train_custom --workflow basic-match-predictor --no-smote
python -m scripts.train_custom --workflow advanced-match-predictor --no-smote
```

Entrypoint instalado:

```bash
plml-train --workflow basic-match-predictor
```

### 4. Levantar la API

```bash
python -m scripts.serve_api --reload
```

O:

```bash
plml-serve-api --reload
```

### Compatibilidad

Los archivos raíz se mantienen como wrappers mínimos:

- `data_pipeline.py` -> preprocesamiento
- `pipeline.py` -> workflow legacy de entrenamiento
- `workshop_pipeline.py` -> workflow legacy de entrenamiento

Úsalos solo por compatibilidad con notebooks o flujos anteriores.

## Datos

### Datos base

El proyecto espera estos archivos ya presentes:

- `data/players.csv`
- `data/matches.csv`
- `data/events.csv`

Y este cache local:

- `data/api_cache/shot_events_with_qualifiers.json`
- `data/api_cache/teams.json`
- `data/api_cache/referees.json`

### Verificar o descargar datos base

Si necesitas reconstruir o verificar la capa base:

```bash
python -m scripts.ingest_data
```

Ese comando:

- valida que los CSV existan
- reconstruye la capa procesada
- actualiza el catálogo de features
- deja manifest y documentación en `data/docs/`

## EDA y Feature Engineering

El notebook principal de exploracion avanzada es:

```text
notebooks/01_eda_feature_engineering.ipynb
```

Este notebook sigue los criterios del Taller 2 de Machine Learning I y conecta el analisis directamente con los dos modelos obligatorios:

- **Modelo xG**: filtra eventos con `is_shot == true`, revisa conversion de tiros, mapas de disparo, heatmaps, distancia, angulo y qualifiers.
- **Match Predictor**: analiza resultados `H/D/A`, goles totales, home/away goals, Over/Under 2.5 y benchmark implicito de Bet365.
- **Data leakage**: separa variables pre-partido validas de variables post-partido no validas como tiros, corners, faltas y tarjetas del mismo partido.

Features creadas para xG:

- `shot_distance`
- `shot_angle`
- `is_big_chance`
- `is_header`
- `is_right_foot`
- `is_left_foot`
- `is_penalty`
- `is_volley`
- `first_touch`
- `from_corner`
- `is_counter`

Features pre-partido creadas para Match Predictor con ventanas rolling:

- `rolling_home_goals_for_last5`
- `rolling_home_goals_against_last5`
- `rolling_away_goals_for_last5`
- `rolling_away_goals_against_last5`
- `rolling_home_points_last5`
- `rolling_away_points_last5`
- `rolling_home_win_rate_last5`
- `rolling_away_win_rate_last5`

El notebook exporta:

- `data/processed/shots_features.csv`
- `data/processed/matches_features.csv`
- `data/processed/eda_summary.json`

Tambien guarda copias reproducibles de los CSV base en `data/raw/`.

Para ejecutarlo desde cero:

```bash
jupyter notebook notebooks/01_eda_feature_engineering.ipynb
```

O en modo batch:

```bash
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda_feature_engineering.ipynb
```

Para publicar el EDA en el dashboard se genera un payload liviano:

```bash
python scripts/build_dashboard_eda_data.py
```

Ese comando lee `shots_features.csv`, `matches_features.csv` y `eda_summary.json`, y escribe:

```text
dashboard/dashboard_eda_data.json
dashboard/dashboard_eda_data_embedded.js
```

El dashboard usa el JSON cuando se sirve por HTTP y usa el archivo embebido cuando se abre con `file://`. Ambos muestran tarjetas de resumen, conversion por BigChance/penal/parte del cuerpo, distancia vs conversion, qualifiers frecuentes, resultados H/D/A, goles totales, Over/Under 2.5, benchmark Bet365, tabla de data leakage, features creadas e insights accionables.

## Generación de features

La capa procesada se genera en:

- `data/processed/matches_prepared.csv`
- `data/processed/shots_enriched.csv`
- `data/processed/event_match_features.csv`
- `data/processed/match_features.csv`
- `data/processed/feature_catalog.json`
- `data/processed/artifact_manifest.json`

Comando:

```bash
python -m scripts.preprocess_data
```

Documentación resultante:

- [data/README.md](data/README.md)
- [data/docs/feature_catalog.md](data/docs/feature_catalog.md)
- [data/docs/orchestration.md](data/docs/orchestration.md)

## Entrenamiento

### Variante 1: modelos base del taller (`legacy`)

```bash
python -m scripts.train_custom --workflow legacy
```

O equivalente:

```bash
python pipeline.py
```

Esto:

- construye artefactos de datos
- entrena el modelo xG
- entrena el predictor de partidos base
- exporta resultados al dashboard

### Variante 2: Full ML baseline (`basic-match-predictor`)

Esta variante ya no usa el predictor baseline del taller sino el runner de `src/models/`.

La estructura sigue siendo de dos modelos:

1. regresor de goles;
2. clasificador del partido.

Ejemplo CLI:

```bash
python -m scripts.train_custom --workflow basic-match-predictor
```

Esto usa por defecto:

```text
config/experiments/match_predictor_basic.yaml
```

### Variante 3: Full ML avanzado (`advanced-match-predictor`)

Esta es la variante más fuerte y la que hoy alimenta la API.

El AutoML creado sin usar explicitamente AutoML de SkLearn vive en `src/models/` y soporta tanto el modo básico como el avanzado.

Ejemplo desde Jupyter:

```python
from src.dataops import build_data_artifacts
from src.models import run_match_model_experiments

artifacts = build_data_artifacts()
match_features = artifacts["match_features"]

report = run_match_model_experiments(
    match_features=match_features,
    regressors=["linear_regression", "knn_regressor", "random_forest_regressor", "xgboost_regressor"],
    classifiers=["knn_classifier", "ridge_classifier", "elasticnet_classifier", "xgboost_classifier"],
    winner_feature_set="winner_default",
    feature_modes=["normal", "extra", "lasso_selected", "poly2_lasso"],
    search_iterations=8,
    smote=True,
    advance_modeling=True,
    stage1_feature_set="history_only",
    stage1_target_set="candidate_indices",
    stage1_top_k=3,
    stage1_min_r2=0.15,
    include_all=True,
    session_name="cpu_match_sweep",
)
```

Los runs quedan en `outputs/model_runs/<session>/`.

En `advance_modeling=True` la etapa 1 ya no intenta reconstruir todas las variables ex post del partido. En su lugar:

- construye `5` indices auxiliares candidatos a partir de tiros, tiros a puerta, corners, faltas y tarjetas
- entrena un regresor por indice
- conserva solo los mejores `top_k` por indice si superan `R2 >= 0.15`
- pasa la prediccion `approx_<indice>` a la etapa 2 como feature ex ante sintetica
- si `include_all=True`, agrega una pasada extra con el mejor generador de cada indice aprobado y concatena todas las `approx_*` juntas antes del clasificador

La etapa 2 mantiene el mismo barrido de clasificadores y modos de features, con `SMOTE` aplicado solo en clasificacion.

## Selección de mejores modelos

El ranking de bundles del clasificador se hace con:

```python
from src.models.select_best_model import rank_classifier_bundles

ranking = rank_classifier_bundles(
    runs_root="outputs/model_runs/advanced_match_predictor/stage2_classifier_runs",
    top_k=3,
)
```

La API usa esta función para cargar automáticamente el top `3` por defecto.

Para el modo avanzado también existe ranking de regresores:

```python
from src.models.select_best_model import rank_regressor_bundles

ranking = rank_regressor_bundles(
    runs_root="outputs/model_runs/advanced_match_cli/stage1_feature_generators",
    top_k=5,
)
```

## API

La API vive en `api/` y sirve los mejores bundles del predictor de partidos.

En la práctica, la API hoy está pensada para la variante **Full ML avanzada** y carga pipelines `stage1 -> stage2` desde:

```text
outputs/model_runs/advanced_match_predictor/stage2_classifier_runs
```

### Ejecutar localmente

```bash
python -m scripts.serve_api --reload
```

### Endpoints principales

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
- `POST /predict/match` para el dashboard, con payload `{ "home_team": "Arsenal", "away_team": "Chelsea" }`.
- `POST /predict/xg` para el simulador xG del dashboard.
- `POST /predict/batch` para predicciones masivas por CSV desde el modal del dashboard.

Más detalle en [api/README.md](api/README.md).

### Contrato de inferencia

Para los endpoints normales de predicción de partido, el cliente ya no tiene que construir manualmente `last5`, `diff`, variables arbitrales ni otras derivadas.

Ahora el cliente envía el partido en formato crudo pre-partido, parecido a `data/matches.csv`, por ejemplo:

- `date`, `time`
- `home_team`, `away_team`
- `referee`
- `b365h`, `b365d`, `b365a`
- `bwh`, `bwd`, `bwa`
- `maxh`, `maxd`, `maxa`
- `avgh`, `avgd`, `avga`

Con eso la API:

1. toma el histórico local ya disponible en `data/` y `data/processed/`;
2. agrega la fila entrante solo en memoria;
3. reconstruye internamente las rolling features y diferencias con la misma lógica del entrenamiento;
4. ejecuta el pipeline `stage1 -> stage2`.

Los datos enviados por el usuario no se guardan en disco. Solo se usan para construir la fila de inferencia del request actual.

## Dashboard

El dashboard estático vive en `dashboard/`.

La sección **EDA & Feature Engineering** resume los hallazgos del notebook avanzado y los conecta con los modelos:

- xG: desbalance gol/no gol, conversion por BigChance, penal, parte del cuerpo, distancia al arco y qualifiers.
- Match Predictor: distribucion H/D/A, goles totales, Over/Under 2.5 y favorito Bet365 contra resultado real.
- Feature engineering: features xG y rolling features pre-partido calculadas con `shift(1)`.
- Data leakage: tabla visual que separa features pre-partido validas de variables post-partido no validas.

Regenerar los datos livianos de esa sección:

```bash
python scripts/build_dashboard_eda_data.py
```

Esto crea:

- `dashboard/dashboard_eda_data.json` para HTTP.
- `dashboard/dashboard_eda_data_embedded.js` para abrir el dashboard offline con doble click.

Opcion recomendada, servirlo localmente:

```bash
python -m http.server 8000
```

Luego abre:

```text
http://localhost:8000/dashboard/
```

Opcion offline/local:

1. Ejecuta `python scripts/build_dashboard_eda_data.py`.
2. Abre `dashboard/index.html` con doble click.

En modo offline el navegador puede bloquear `fetch()`, por eso el dashboard carga `dashboard_eda_data_embedded.js` antes de `app.js`.

Dashboard conectado a la API:

Terminal 1, API FastAPI:

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

Terminal 2, dashboard estatico:

```bash
python -m http.server 8000
```

Abre:

```text
http://localhost:8000/dashboard/
```

Abre: http://localhost:8000/dashboard/
El dashboard revisa `http://127.0.0.1:8001/health`. Si la API responde, muestra **Modo API**, consulta `/predict/match` desde el simulador de partido, consulta `/predict/xg` desde el simulador de disparo y lee `/api/v1/model-info` para mostrar el catálogo de modelos cargados. Si la API no esta disponible, sigue funcionando con `dashboard_data.js` y `dashboard_eda_data_embedded.js`.

## Configuración

La carpeta `config/` centraliza presets operativos:

- `config/training/base.yaml`
- `config/training/quick_smoke.yaml`
- `config/api/default.yaml`
- `config/experiments/match_predictor_basic.yaml`
- `config/experiments/match_predictor_cpu.yaml`
- `config/experiments/match_predictor_advanced.yaml`

Sirven como punto de partida para documentar:

- hyperparameters por defecto
- presets de smoke tests
- experimento baseline Full ML de partido
- alias de compatibilidad para el experimento CPU anterior
- experimento Full ML avanzado en dos steps
- raíz de modelos de la API
- barridos de experimentos en CPU

## Tests y CI

Los tests están repartidos en:

- `tests/`: smoke tests del proyecto
- `api/tests/`: validaciones unitarias del backend

Cobertura actual mínima:

- integridad de datos locales
- reconstrucción de artefactos procesados
- smoke test de la API
- entrenamiento rápido de un mini run del Match Predictor

Ejecutar tests:

```bash
pytest
```

CI:

- workflow en `.github/workflows/ci.yml`
- instala dependencias
- corre `pytest` en push y pull request
