# Source Layout

Este paquete contiene la version modular del pipeline de ML para Premier League.

- `config.py`: rutas, endpoints, constantes del proyecto y normalizacion de nombres.
- `data.py`: descarga de CSV, lectura de datasets y cache de contexto del API.
- `dataops.py`: construccion de artifacts `data/processed`, manifest y documentacion de features.
- `preprocessing.py`: preparacion de partidos, enriquecimiento de tiros y features temporales.
- `legacy_models.py`: entrenamiento/evaluacion del pipeline original de xG y prediccion de partidos.
- `models/`: paquete nuevo para correr combinaciones de modelos del Match Predictor con busqueda de hiperparametros y guardado de artefactos.
- `dashboard.py`: construccion del payload y export de artefactos para `dashboard/`.
- `pipeline.py`: orquestador de alto nivel usado por los wrappers raiz.
- `utils.py`: helpers compartidos para JSON, rounding y nombres de equipos.

Los archivos raiz `workshop_pipeline.py`, `data_pipeline.py` y `pipeline.py` siguen funcionando como wrappers para mantener compatibilidad con notebooks, scripts y el dashboard existente.
