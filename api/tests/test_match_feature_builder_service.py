from __future__ import annotations

import pandas as pd

from api.config import get_settings
from api.services.match_feature_builder_service import MatchFeatureBuilderService


def test_build_feature_frame_from_raw_match_row():
    service = MatchFeatureBuilderService(get_settings())
    raw_frame = pd.DataFrame(
        [
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
                "avga": 3.48,
            }
        ]
    )

    feature_frame = service.build_feature_frame(raw_frame)

    assert len(feature_frame) == 1
    assert {"home_goals_for_last5", "away_goals_for_last5", "points_diff_last5", "ref_avg_goals_last10"} <= set(feature_frame.columns)
    assert feature_frame.loc[0, "home_team"] == "Liverpool"
    assert feature_frame.loc[0, "away_team"] == "Arsenal"
