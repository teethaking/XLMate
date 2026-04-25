from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import re

from personality.config import FeedbackOutcome, PipelineConfig, TrainingConfig, TrainingFeedback
from personality.evaluator import PersonalityEvaluator
from personality.presets import get_style_anchor
from personality.profile import PersonalityProfile, PersonalityTraits, PlayStyle
from personality.style_analyzer import GameStyleMetrics, StyleAnalyzer
from personality.tuner import EngineParameterTuner


def _clamp(value: float) -> float:
    """Clamp trait values into the normalized 0.0-1.0 interval."""

    return max(0.0, min(1.0, value))


def _slugify(value: str) -> str:
    """Convert a human-readable label to an identifier slug."""

    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-") or "personality-profile"


def _blend_traits(
    observed: PersonalityTraits,
    anchor: PersonalityTraits,
    weight: float,
) -> PersonalityTraits:
    """Blend observed traits with a style anchor profile."""

    values: dict[str, float] = {}
    for field_name in type(observed).model_fields:
        observed_value = getattr(observed, field_name)
        anchor_value = getattr(anchor, field_name)
        values[field_name] = _clamp((observed_value * (1.0 - weight)) + (anchor_value * weight))
    return PersonalityTraits(**values)


def _shift_traits_toward(
    traits: PersonalityTraits,
    target: PersonalityTraits,
    amount: float,
) -> PersonalityTraits:
    """Move a trait vector toward a target vector by a bounded amount."""

    values: dict[str, float] = {}
    for field_name in type(traits).model_fields:
        current_value = getattr(traits, field_name)
        target_value = getattr(target, field_name)
        values[field_name] = _clamp(current_value + ((target_value - current_value) * amount))
    return PersonalityTraits(**values)


class PersonalityTrainer:
    """Pipeline for training and refining agent personalities from game data."""

    def __init__(
        self,
        config: TrainingConfig,
        *,
        analyzer: StyleAnalyzer | None = None,
        evaluator: PersonalityEvaluator | None = None,
        tuner: EngineParameterTuner | None = None,
    ) -> None:
        self.config = config
        self._analyzer = analyzer or StyleAnalyzer()
        self._evaluator = evaluator or PersonalityEvaluator(self._analyzer)
        self._tuner = tuner or EngineParameterTuner()
        self.last_evaluation_score: float | None = None

    async def train_from_games(
        self,
        pgn_data: list[str],
        target_style: PlayStyle,
    ) -> PersonalityProfile:
        """Analyze games to extract personality traits and generate a profile."""

        if not pgn_data:
            raise ValueError("at least one PGN game is required")
        await asyncio.sleep(0)

        aggregate_metrics = self._analyzer.analyze_corpus(pgn_data)
        observed_traits = self._analyzer.style_to_traits(aggregate_metrics)
        target_anchor = get_style_anchor(target_style)
        traits = _blend_traits(observed_traits, target_anchor, self.config.style_blend_weight)
        style_label = target_style.value.replace("_", " ").title()
        timestamp = datetime.now(timezone.utc)
        profile_id = f"{_slugify(style_label)}-{timestamp.strftime('%Y%m%d%H%M%S')}"
        return PersonalityProfile(
            id=profile_id,
            name=self.config.profile_name_template.format(style=style_label),
            description=self.config.description_template.format(style=style_label.lower()),
            style=target_style,
            traits=traits,
            engine_overrides=self._tuner.traits_to_uci_options(traits, self.config.engine_type),
            search_params=self._tuner.traits_to_search_params(traits),
            created_at=timestamp,
        )

    async def refine_profile(
        self,
        profile: PersonalityProfile,
        feedback: list[TrainingFeedback],
    ) -> PersonalityProfile:
        """Refine a profile based on outcome and manual trait feedback."""

        if not feedback:
            return profile.model_copy(deep=True)
        await asyncio.sleep(0)

        traits = profile.traits.model_copy(deep=True)
        style_anchor = get_style_anchor(profile.style)
        balanced_anchor = get_style_anchor(PlayStyle.BALANCED)

        for item in feedback:
            step = self.config.learning_rate * item.confidence
            if item.outcome is FeedbackOutcome.WIN:
                traits = _shift_traits_toward(traits, style_anchor, step)
            elif item.outcome is FeedbackOutcome.LOSS:
                traits = _shift_traits_toward(traits, balanced_anchor, step)
            else:
                traits = _shift_traits_toward(traits, balanced_anchor, step * 0.5)

            updates = traits.model_dump()
            for trait_name, delta in item.trait_adjustments.items():
                if trait_name not in updates:
                    raise ValueError(f"unknown trait adjustment: {trait_name}")
                updates[trait_name] = _clamp(updates[trait_name] + (delta * step))
            traits = PersonalityTraits(**updates)

        updated = profile.model_copy(deep=True)
        updated.traits = traits
        updated.engine_overrides = self._tuner.traits_to_uci_options(traits, self.config.engine_type)
        updated.search_params = self._tuner.traits_to_search_params(traits)
        updated.version += 1
        return updated

    async def run_pipeline(self, pipeline_config: PipelineConfig) -> PersonalityProfile:
        """Run analyze, train, evaluate, and optional save steps."""

        metrics: list[GameStyleMetrics] = [
            self._analyzer.analyze_game(pgn) for pgn in pipeline_config.pgn_data
        ]
        profile = await self.train_from_games(
            pipeline_config.pgn_data,
            pipeline_config.target_style,
        )
        if pipeline_config.profile_id is not None:
            profile.id = pipeline_config.profile_id.strip()
        if pipeline_config.name is not None:
            profile.name = pipeline_config.name.strip()
        if pipeline_config.description is not None:
            profile.description = pipeline_config.description.strip()
        if pipeline_config.feedback:
            profile = await self.refine_profile(profile, pipeline_config.feedback)

        self.last_evaluation_score = self._evaluator.score_profile(profile, metrics)

        if pipeline_config.output_path:
            output_path = Path(pipeline_config.output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

        return profile
