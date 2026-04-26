from __future__ import annotations

import pandas as pd
import pytest

from api.services.feature_service import FeatureValidationError, numeric_frame


def test_numeric_frame_requires_columns():
    frame = pd.DataFrame([{"a": 1.0}])
    with pytest.raises(FeatureValidationError):
        numeric_frame(frame, ["a", "b"])


def test_numeric_frame_rejects_non_numeric_values():
    frame = pd.DataFrame([{"a": "bad"}])
    with pytest.raises(FeatureValidationError):
        numeric_frame(frame, ["a"])
