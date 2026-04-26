# Feature Catalog

Catalogo de variables derivadas exportadas por el pipeline local de datos.

## shots_enriched

- `distance_to_goal_m`: Distancia en metros entre la ubicacion del tiro y el centro de la porteria, tras normalizar la direccion de ataque. (familia: `geometria`, alcance: `tiro`, ex_ante: `False`)
- `goal_frame_angle`: Angulo efectivo de remate abierto hacia los dos postes desde la posicion del tiro. (familia: `geometria`, alcance: `tiro`, ex_ante: `False`)
- `centrality_to_goal`: Que tan centrado queda el tiro respecto al arco. Toma valores entre 0 y 1. (familia: `geometria`, alcance: `tiro`, ex_ante: `False`)
- `shot_angle_distance_interaction`: Interaccion entre angulo y distancia para favorecer tiros cercanos y centrados. (familia: `geometria`, alcance: `tiro`, ex_ante: `False`)
- `is_assisted`: Indicador de que el remate fue asistido por un companero segun los qualifiers del evento. (familia: `contexto_del_tiro`, alcance: `tiro`, ex_ante: `False`)
- `is_individual_play`: Indicador de remate generado por accion individual del jugador. (familia: `contexto_del_tiro`, alcance: `tiro`, ex_ante: `False`)
- `is_regular_play`: Indicador de jugada abierta regular, no asociada a balon parado. (familia: `contexto_del_tiro`, alcance: `tiro`, ex_ante: `False`)
- `is_set_piece`: Indicador de remate originado en una accion a balon parado. (familia: `contexto_del_tiro`, alcance: `tiro`, ex_ante: `False`)
- `score_diff_before_shot`: Diferencia de goles del equipo que remata justo antes del tiro. (familia: `estado_del_partido`, alcance: `tiro`, ex_ante: `False`)
- `leading_before_shot`: Indicador de que el equipo del tirador ya iba ganando antes del remate. (familia: `estado_del_partido`, alcance: `tiro`, ex_ante: `False`)
- `trailing_before_shot`: Indicador de que el equipo del tirador iba perdiendo antes del remate. (familia: `estado_del_partido`, alcance: `tiro`, ex_ante: `False`)
- `shot_number_in_match`: Numero secuencial del tiro dentro de la cronologia completa del partido. (familia: `secuencia`, alcance: `tiro`, ex_ante: `False`)
- `team_shot_number_in_match`: Numero secuencial del tiro dentro de la cronologia del equipo en ese partido. (familia: `secuencia`, alcance: `tiro`, ex_ante: `False`)
- `time_since_prev_team_shot_s`: Segundos transcurridos desde el tiro anterior del mismo equipo en el mismo partido. (familia: `secuencia`, alcance: `tiro`, ex_ante: `False`)
- `player_conversion_last20`: Tasa de conversion historica del jugador calculada sobre sus 20 tiros anteriores mediante ventana rodante con shift. (familia: `historial_rodante`, alcance: `tiro`, ex_ante: `True`)
- `player_big_chance_rate_last20`: Proporcion historica de big chances del jugador sobre sus 20 tiros previos, usando solo informacion pasada. (familia: `historial_rodante`, alcance: `tiro`, ex_ante: `True`)
- `team_conversion_last40`: Tasa de conversion del equipo calculada sobre sus 40 tiros anteriores, sin usar el tiro actual. (familia: `historial_rodante`, alcance: `tiro`, ex_ante: `True`)
- `team_big_chance_rate_last40`: Proporcion de big chances del equipo en sus 40 tiros previos, construida solo con historial pasado. (familia: `historial_rodante`, alcance: `tiro`, ex_ante: `True`)

## event_match_features

- `progressive_pass_rate`: Proporcion de pases del equipo que avanzan al menos 15 unidades hacia adelante en ese partido. (familia: `estilo_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)
- `shot_accuracy`: Relacion entre tiros a puerta y tiros totales del equipo dentro del partido. (familia: `ataque_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)
- `conversion_rate`: Relacion entre goles y tiros del equipo en el partido. (familia: `ataque_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)
- `big_chance_rate`: Proporcion de tiros clasificados como big chance sobre el total de remates del equipo en ese partido. (familia: `ataque_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)
- `assisted_shot_rate`: Proporcion de remates asistidos sobre el total de tiros del equipo en ese partido. (familia: `ataque_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)
- `touches_per_shot`: Numero promedio de toques necesarios para producir un remate en ese partido. (familia: `ataque_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)
- `avg_score_diff_before_shot`: Promedio del estado del marcador desde el que el equipo remato en ese partido. (familia: `contexto_de_equipo`, alcance: `equipo_partido`, ex_ante: `False`)

## match_features

- `points_diff_last5`: Diferencia entre los puntos promedio de local y visitante en sus ultimos 5 partidos, calculada con shift para usar solo historial previo. (familia: `forma_prepartido`, alcance: `partido`, ex_ante: `True`)
- `shot_accuracy_diff_last5`: Diferencia entre la precision de remate historica de local y visitante en los ultimos 5 partidos previos. (familia: `forma_prepartido`, alcance: `partido`, ex_ante: `True`)
- `conversion_rate_diff_last5`: Diferencia entre la tasa de conversion historica de ambos equipos en sus ultimos 5 partidos previos. (familia: `forma_prepartido`, alcance: `partido`, ex_ante: `True`)
- `big_chance_rate_diff_last5`: Diferencia entre la proporcion de big chances de ambos equipos en los ultimos 5 partidos anteriores al encuentro. (familia: `forma_prepartido`, alcance: `partido`, ex_ante: `True`)
- `assisted_shot_rate_diff_last5`: Diferencia entre la proporcion historica de remates asistidos del local y del visitante en sus ultimos 5 partidos. (familia: `forma_prepartido`, alcance: `partido`, ex_ante: `True`)
- `avg_shot_angle_diff_last5`: Diferencia entre el angulo promedio de tiro que generaron ambos equipos en sus ultimos 5 partidos previos. (familia: `calidad_de_ocasiones`, alcance: `partido`, ex_ante: `True`)
- `avg_score_diff_before_shot_diff_last5`: Diferencia entre los estados de marcador desde los que ambos equipos acostumbran rematar, usando solo partidos anteriores. (familia: `estado_prepartido`, alcance: `partido`, ex_ante: `True`)
- `market_favorite_strength`: Probabilidad implicita normalizada mas alta de Bet365 antes del partido. Resume la fuerza del favorito de mercado. (familia: `senal_de_mercado`, alcance: `partido`, ex_ante: `True`)
- `market_entropy_b365`: Entropia de la distribucion implicita de Bet365 antes del partido. Valores bajos indican favorito mas claro. (familia: `senal_de_mercado`, alcance: `partido`, ex_ante: `True`)
- `home_odds_dispersion`: Dispersion de la cuota local entre casas de apuestas antes del partido. (familia: `senal_de_mercado`, alcance: `partido`, ex_ante: `True`)
- `ref_avg_yellows_last10`: Promedio rodante de tarjetas amarillas mostradas por el arbitro en sus ultimos 10 partidos previos. (familia: `contexto_arbitral`, alcance: `partido`, ex_ante: `True`)
- `ref_home_win_rate_last10`: Tasa rodante de victorias locales en los ultimos 10 partidos previos arbitrados por ese juez. (familia: `contexto_arbitral`, alcance: `partido`, ex_ante: `True`)
