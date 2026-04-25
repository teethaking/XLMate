from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from personality.profile import PlayStyle


class FeedbackOutcome(str, Enum):
    """Supported outcomes when refining a trained profile."""

    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"


class TrainingFeedback(BaseModel):
    """Structured post-game feedback for profile refinement."""

    model_config = ConfigDict(extra="forbid")

    outcome: FeedbackOutcome
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    trait_adjustments: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None


class TrainingConfig(BaseModel):
    """Configuration for the personality training pipeline."""

    model_config = ConfigDict(extra="forbid")

    engine_type: str = Field(default="stockfish", min_length=1)
    style_blend_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    learning_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    profile_name_template: str = Field(default="Trained {style} Agent", min_length=1)
    description_template: str = Field(
        default="Learned personality profile emphasizing {style} play patterns.",
        min_length=1,
    )


class PipelineConfig(BaseModel):
    """Inputs for the full analyze-train-evaluate-save pipeline."""

    model_config = ConfigDict(extra="forbid")

    pgn_data: list[str] = Field(min_length=1)
    target_style: PlayStyle
    feedback: list[TrainingFeedback] = Field(default_factory=list)
    profile_id: str | None = None
    name: str | None = None
    description: str | None = None
    output_path: str | None = None
