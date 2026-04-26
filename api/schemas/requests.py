from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawMatchInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str = Field(..., description="Match date in the same format used by `data/matches.csv`, e.g. `25/04/2026`.")
    time: str = Field(..., description="Kickoff time string, e.g. `15:00`.")
    home_team: str = Field(..., min_length=1, description="Home team name.")
    away_team: str = Field(..., min_length=1, description="Away team name.")
    referee: str = Field(..., min_length=1, description="Referee name.")
    b365h: float = Field(..., gt=0, description="Bet365 home odds.")
    b365d: float = Field(..., gt=0, description="Bet365 draw odds.")
    b365a: float = Field(..., gt=0, description="Bet365 away odds.")
    bwh: float = Field(..., gt=0, description="Bet&Win home odds.")
    bwd: float = Field(..., gt=0, description="Bet&Win draw odds.")
    bwa: float = Field(..., gt=0, description="Bet&Win away odds.")
    maxh: float = Field(..., gt=0, description="Maximum market home odds.")
    maxd: float = Field(..., gt=0, description="Maximum market draw odds.")
    maxa: float = Field(..., gt=0, description="Maximum market away odds.")
    avgh: float = Field(..., gt=0, description="Average market home odds.")
    avgd: float = Field(..., gt=0, description="Average market draw odds.")
    avga: float = Field(..., gt=0, description="Average market away odds.")
    implied_prob_h: float | None = Field(default=None, ge=0, description="Optional precomputed implied home probability.")
    implied_prob_d: float | None = Field(default=None, ge=0, description="Optional precomputed implied draw probability.")
    implied_prob_a: float | None = Field(default=None, ge=0, description="Optional precomputed implied away probability.")


class MatchPredictionRequest(BaseModel):
    model_id: str | None = Field(
        default=None,
        description="Optional model id. If omitted, the API uses the default loaded bundle.",
    )
    records: list[RawMatchInput | dict[str, Any]] = Field(
        ...,
        min_length=1,
        description=(
            "One or more raw pre-match rows using `data/matches.csv`-style fields. "
            "The API builds historical rolling/diff features internally from local data before prediction."
        ),
    )


class TeamMatchPredictionRequest(BaseModel):
    home_team: str = Field(..., min_length=1, description="Home team name.")
    away_team: str = Field(..., min_length=1, description="Away team name.")
    model_id: str | None = Field(
        default=None,
        description="Optional model id. If omitted, the API uses the default loaded bundle.",
    )


class XgPredictionRequest(BaseModel):
    x: float | None = Field(default=None, ge=0, le=100, description="Shot x coordinate in 0-100 scale.")
    y: float | None = Field(default=None, ge=0, le=100, description="Shot y coordinate in 0-100 scale.")
    shot_distance: float | None = Field(default=None, ge=0, description="Distance to goal in normalized units/meters.")
    shot_angle: float | None = Field(default=None, ge=0, description="Angle to goal in radians.")
    is_big_chance: int = Field(default=0, ge=0, le=1)
    is_header: int = Field(default=0, ge=0, le=1)
    is_right_foot: int = Field(default=0, ge=0, le=1)
    is_left_foot: int = Field(default=0, ge=0, le=1)
    is_penalty: int = Field(default=0, ge=0, le=1)
    is_volley: int = Field(default=0, ge=0, le=1)
    first_touch: int = Field(default=0, ge=0, le=1)
    from_corner: int = Field(default=0, ge=0, le=1)
    is_counter: int = Field(default=0, ge=0, le=1)
