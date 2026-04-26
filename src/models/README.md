# Match Predictor Models

Este paquete contiene el entrenamiento, el registry y la logica de seleccion de bundles del predictor de partidos.

## Archivos principales

- `runner.py`: orquesta entrenamiento, evaluacion y export de artefactos.
- `registry.py`: define el catalogo de modelos disponibles.
- `select_best_model.py`: rankea bundles de regresion y clasificacion a partir de `run_summary.json`.
- `feature_sets.py`: presets de columnas y reglas para armar datasets.
- `ridge_elasticnet.py`, `knn.py`, `randomforest.py`, `xgboost.py`, `catboost.py`, `lightgbm.py`, `torch_nn.py`: wrappers/model specs por familia.
- `torch_nn_model.py`: arquitecturas tabulares para PyTorch.

## Modos de entrenamiento

### 1. Modo basico

Pipeline clasico:

1. un regresor estima goles totales;
2. un clasificador predice resultado final.

Ese modo genera bundles autocontenidos donde en la misma carpeta suelen vivir:

- `run_summary.json`
- `regressor.joblib` o `regressor.pt`
- `classifier.joblib` o `classifier.pt`

### 2. Modo avanzado

Este es el pipeline relevante hoy para produccion.

Se entrena en dos pasos desacoplados:

1. `stage1_feature_generators`
   - cada regresor usa solo informacion ex ante/historica;
   - el objetivo ya no son goles, sino indices sinteticos del partido;
   - ejemplos de target: `dominance_index`, `threat_index`, `efficiency_control_index`, `clean_dominance_index`;
   - la salida esperada es una o varias features generadas, normalmente con nombre `approx_<metric>`.
2. `stage2_classifier_runs`
   - cada clasificador consume features ex ante;
   - ademas consume la feature aproximada generada por el mejor modelo de `stage1` para ese target;
   - el bundle final guarda el `classifier` y referencia explicitamente el generador de `stage1` usado.

En otras palabras: el bundle ganador de clasificacion ya no es un modelo aislado. Es un pipeline `stage1 -> stage2`.

## Estructura de outputs

### Stage 1

Raiz:

```text
outputs/model_runs/advanced_match_predictor/stage1_feature_generators/
```

Organizacion:

```text
<target_metric>/<regressor_run_name>/
```

Cada carpeta contiene:

- `run_summary.json`
- `regressor.joblib` o `regressor.pt`
- `regression_search_results.csv`

### Stage 2

Raiz:

```text
outputs/model_runs/advanced_match_predictor/stage2_classifier_runs/
```

Organizacion:

```text
<target_metric>__<stage1_run_name>__<stage2_classifier_name+feature_mode>/
```

Cada carpeta contiene:

- `run_summary.json`
- `classifier.joblib` o `classifier.pt`
- `classification_search_results.csv`

Importante: en el modo avanzado la carpeta de `stage2` no tiene por que contener `regressor.*`. El artefacto de `stage1` se resuelve usando la informacion del `run_summary.json`.

## Que trae `run_summary.json` en stage2

El `run_summary.json` del clasificador es la pieza de integracion para inferencia. Ahi queda:

- `target_metric`: indice que se aproxima en `stage1`.
- `feature_mode`: preset de features del clasificador.
- `generator_model`:
  - `run_name`
  - `name`
  - `feature_columns`
  - `generated_feature_columns`
  - metricas como `cv_r2` y `test_r2`
  - `artifact_path` como referencia del artefacto original
- `classifier`:
  - `name`
  - hiperparametros ganadores
  - `feature_columns`
  - `artifact_path`
- `classifier_metrics`

Para la API, el `artifact_path` absoluto del summary debe tratarse solo como pista. La resolucion portable correcta debe hacerse desde la estructura relativa de `outputs/`.

## Contrato actual para inferencia

Cuando se usa el pipeline avanzado, la inferencia correcta es:

1. tomar las columnas de entrada requeridas por `generator_model.feature_columns`;
2. ejecutar el regresor de `stage1`;
3. producir las columnas listadas en `generator_model.generated_feature_columns`;
4. combinar esas columnas con las features base del clasificador;
5. ejecutar `stage2`.

Eso implica dos reglas practicas:

- las features requeridas por `stage1` y `stage2` deben salir del `run_summary.json` del bundle ganador;
- no se debe asumir una feature fija como `stage1_pred_total_goals`, porque en el pipeline avanzado la feature inyectada depende del `target_metric`.

## Relacion con `select_best_model.py`

`select_best_model.py` sigue siendo la base para rankear corridas:

- `rank_regressor_bundles(...)` ordena generadores de `stage1`;
- `rank_classifier_bundles(...)` ordena bundles de `stage2`.

En produccion conviene rankear `stage2`, quedarse con el top `k`, y desde cada carpeta seleccionada leer su `run_summary.json` para resolver el `stage1` asociado.

## Ejemplo de ejecucion

```python
from src.dataops import build_data_artifacts
from src.models import run_match_model_experiments

artifacts = build_data_artifacts()
match_features = artifacts["match_features"]

report = run_match_model_experiments(
    match_features=match_features,
    regressors=[
        "linear_regression",
        "knn_regressor",
        "ridge_regressor",
        "elasticnet_regressor",
        "random_forest_regressor",
        "xgboost_regressor",
    ],
    classifiers=[
        "knn_classifier",
        "ridge_classifier",
        "elasticnet_classifier",
        "random_forest_classifier",
        "xgboost_classifier",
        "catboost_classifier",
        "lightgbm_classifier",
    ],
    winner_feature_set="winner_default",
    feature_modes=["normal", "extra", "lasso_selected", "poly2_lasso"],
    search_iterations=10,
    smote=True,
    advance_modeling=True,
    stage1_feature_set="history_only",
    stage1_target_set="candidate_indices",
    stage1_top_k=3,
    stage1_min_r2=0.15,
    include_all=True,
    session_name="advanced_match_predictor",
)
```

## Notas operativas

- `stage1_top_k` define cuantos generadores por target pasan a competir en `stage2`.
- `stage1_min_r2` filtra generadores debiles antes de entrenar clasificadores.
- `include_all=True` agrega corridas que combinan simultaneamente los mejores generadores por indice.
- Si se cambian nombres de targets o de features generadas, la API debe leerlos desde `run_summary.json`; no conviene hardcodearlos.
