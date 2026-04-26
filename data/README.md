# Capa de datos

Esta carpeta funciona como la capa de datos reproducible del proyecto.

- `players.csv`, `matches.csv`, `events.csv`: fuentes base locales.
- `api_cache/`: contexto auxiliar cacheado para enriquecer tiros sin depender de descargas en cada corrida.
- `processed/`: artefactos derivados listos para modelado.
- `docs/`: documentación generada del pipeline de datos.

## Orquestación

Flujo recomendado:

1. `python -m scripts.ingest_data`
2. `python -m scripts.preprocess_data`

Compatibilidad:

- `python data_pipeline.py` llama al mismo preprocesamiento.
- `python pipeline.py` y `python workshop_pipeline.py` reutilizan la misma lógica antes de entrenar.

## Regla ex ante

Para el **modelo de partidos** la regla es estricta:

- las variables que entran al entrenamiento deben ser **ex ante**, es decir, conocidas antes del inicio del partido objetivo;
- las métricas derivadas de eventos del partido, como `shot_accuracy`, `conversion_rate`, `big_chance_rate` y `touches_per_shot`, **no entran directamente** al modelo del mismo partido;
- esas métricas solo pueden usarse convertidas a historial rodante:
  - `*_last5`
  - `*_last10`
  - promedios con `shift(1)` y ventanas rolling.

## Confirmación de no leakage en el pipeline actual

La construcción de features del predictor de partidos usa dos capas:

### 1. `event_match_features.csv`

Aquí sí existen métricas observadas dentro del partido, por ejemplo:

- `shot_accuracy`
- `conversion_rate`
- `big_chance_rate`
- `assisted_shot_rate`
- `touches_per_shot`

Estas variables describen el rendimiento **del equipo dentro de ese partido**.  
Por lo tanto, **no son ex ante** y **no deben entrar directamente al modelo prepartido**.

### 2. `match_features.csv`

Estas métricas se transforman a historia previa mediante ventanas rolling y `shift(1)` en `src/preprocessing.py`.

Ejemplos ex ante válidos:

- `home_shot_accuracy_last5`
- `away_shot_accuracy_last5`
- `shot_accuracy_diff_last5`
- `home_conversion_rate_last5`
- `away_conversion_rate_last5`
- `conversion_rate_diff_last5`
- `home_big_chance_rate_last5`
- `away_big_chance_rate_last5`
- `big_chance_rate_diff_last5`
- `home_touches_per_shot_last5`
- `away_touches_per_shot_last5`
- `touches_per_shot_diff_last5`

Estas columnas sí son válidas porque usan únicamente partidos anteriores.

## Ajuste aplicado al runner

El runner de `src/models/` ya fue ajustado para evitar leakage en modos automáticos:

- `normal`: usa solo presets base ex ante
- `extra`: usa solo numéricas ex ante
- `lasso_selected`: usa solo numéricas ex ante
- `poly2_lasso`: parte del preset base ex ante

Se excluyeron explícitamente del pool automático columnas observadas del mismo partido, como:

- `hthg`, `htag`
- `hs`, `as_`, `hst`, `ast`
- `hf`, `af`, `hc`, `ac`
- `hy`, `ay`, `hr`, `ar`
- y también los targets finales (`fthg`, `ftag`, `ftr` derivados)

Con eso:

- los presets base ya eran ex ante;
- los modos `extra` y `lasso_selected` dejaron de poder colar estadísticas del partido objetivo.

## Artefactos procesados

- `processed/matches_prepared.csv`: tabla de partidos normalizada y ordenada temporalmente.
- `processed/shots_enriched.csv`: tabla a nivel de tiro para el modelo xG.
- `processed/event_match_features.csv`: agregados observados a nivel equipo-partido.
- `processed/match_features.csv`: tabla de modelado prepartido con variables ex ante y señales de mercado.
- `processed/feature_catalog.json`: catálogo en español de las variables derivadas.
- `processed/artifact_manifest.json`: manifest con timestamp, fuentes y esquema.

## Notas importantes

- En el modelo xG sí existen variables intrapartido porque el problema ocurre al nivel del tiro.
- En el predictor de ganador de partido, la capa válida es `match_features.csv` filtrada a variables ex ante.
- Si se agregan nuevas features al predictor, deben seguir la misma regla: historial previo o señales conocidas antes del kickoff.
