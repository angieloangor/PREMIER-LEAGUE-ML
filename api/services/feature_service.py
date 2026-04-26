from __future__ import annotations

import io
from typing import Any

import pandas as pd


class FeatureValidationError(ValueError):
    """Raised when input rows do not satisfy the model feature schema."""


def rows_to_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        raise FeatureValidationError("At least one record is required.")
    normalized_records = [
        record.model_dump() if hasattr(record, "model_dump") else dict(record)
        for record in records
    ]
    frame = pd.DataFrame(normalized_records)
    if frame.empty:
        raise FeatureValidationError("Input records produced an empty dataframe.")
    return frame


def csv_bytes_to_frame(payload: bytes, encoding: str = "utf-8") -> pd.DataFrame:
    if not payload:
        raise FeatureValidationError("Uploaded CSV is empty.")
    return pd.read_csv(io.BytesIO(payload), encoding=encoding)


def require_columns(frame: pd.DataFrame, required_columns: list[str]) -> None:
    missing = sorted(column for column in required_columns if column not in frame.columns)
    if missing:
        raise FeatureValidationError(
            "Missing required feature columns.",
            {"missing_columns": missing, "required_columns": required_columns},
        )


def numeric_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    require_columns(frame, columns)
    numeric = frame.loc[:, columns].copy()
    conversion_errors: dict[str, str] = {}
    for column in columns:
        converted = pd.to_numeric(numeric[column], errors="coerce")
        if converted.isna().any():
            conversion_errors[column] = "Column contains non-numeric or null values."
        numeric[column] = converted

    if conversion_errors:
        raise FeatureValidationError("Input contains invalid numeric values.", conversion_errors)
    return numeric
