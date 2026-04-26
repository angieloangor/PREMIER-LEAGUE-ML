from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    details: Any | None = Field(default=None, description="Optional structured details.")
    request_id: str | None = Field(default=None, description="Request correlation id.")
