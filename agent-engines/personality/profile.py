from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


_TIME_ALLOCATION_PHASES = ("opening", "middlegame", "endgame")


def _default_time_allocation() -> dict[str, float]:
    """Return the baseline phase allocation for searches."""

    return {
        "opening": 0.15,
        "middlegame": 0.55,
        "endgame": 0.30,
    }


class PlayStyle(str, Enum):
    """Supported high-level playing styles."""

    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    POSITIONAL = "positional"
    TACTICAL = "tactical"
    BALANCED = "balanced"


class PersonalityTraits(BaseModel):
    """Core personality dimensions normalized to the 0.0-1.0 range."""

    model_config = ConfigDict(extra="forbid")

    aggression: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)
    positional_play: float = Field(default=0.5, ge=0.0, le=1.0)
    endgame_focus: float = Field(default=0.5, ge=0.0, le=1.0)
    time_management: float = Field(default=0.5, ge=0.0, le=1.0)
    creativity: float = Field(default=0.5, ge=0.0, le=1.0)
    opening_book_adherence: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchPersonalization(BaseModel):
    """Search-time options derived from a personality profile."""

    model_config = ConfigDict(extra="forbid")

    contempt: int = Field(default=0, ge=-100, le=100)
    move_overhead_ms: int = Field(default=30, ge=0)
    multi_pv: int = Field(default=1, ge=1)
    depth_bias: int = Field(default=0, ge=-10, le=10)
    time_allocation: dict[str, float] = Field(default_factory=_default_time_allocation)

    @field_validator("time_allocation")
    @classmethod
    def validate_time_allocation(cls, value: dict[str, float]) -> dict[str, float]:
        """Ensure all phases are present and normalize the weights."""

        if set(value) != set(_TIME_ALLOCATION_PHASES):
            raise ValueError(
                "time_allocation must contain opening, middlegame, and endgame"
            )
        normalized = {phase: float(weight) for phase, weight in value.items()}
        if any(weight < 0 for weight in normalized.values()):
            raise ValueError("time_allocation weights must be non-negative")
        total = sum(normalized.values())
        if total <= 0:
            raise ValueError("time_allocation must sum to a positive value")
        return {
            phase: normalized[phase] / total
            for phase in _TIME_ALLOCATION_PHASES
        }


class PersonalityProfile(BaseModel):
    """Complete agent personality profile and engine configuration overlay."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    style: PlayStyle
    traits: PersonalityTraits
    engine_overrides: dict[str, str | int | float] = Field(default_factory=dict)
    search_params: SearchPersonalization = Field(default_factory=SearchPersonalization)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, ge=1)

    @field_validator("id", "name", "description")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        """Trim required string fields and reject blank values."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized
