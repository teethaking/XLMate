from __future__ import annotations

import json

import pytest

from personality.config import FeedbackOutcome, PipelineConfig, TrainingConfig, TrainingFeedback
from personality.profile import PersonalityTraits, PlayStyle
from personality.style_analyzer import AggregateStyleMetrics
from personality.trainer import PersonalityTrainer


SAMPLE_PGN = """[Event \"Test Game\"]
[White \"Attacker\"]
[Black \"Defender\"]
[Result \"1-0\"]
1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O 1-0
"""


class FakeAnalyzer:
    def analyze_game(self, _: str):
        return self._metrics()

    def analyze_corpus(self, _: list[str]) -> AggregateStyleMetrics:
        return self._metrics()

    def style_to_traits(self, _: AggregateStyleMetrics) -> PersonalityTraits:
        return PersonalityTraits(
            aggression=0.7,
            risk_tolerance=0.65,
            positional_play=0.4,
            endgame_focus=0.35,
            time_management=0.55,
            creativity=0.75,
            opening_book_adherence=0.45,
        )

    @staticmethod
    def _metrics() -> AggregateStyleMetrics:
        return AggregateStyleMetrics(
            piece_activity=0.7,
            pawn_break_frequency=0.6,
            king_pressure=0.75,
            sacrifice_frequency=0.55,
            move_complexity=0.7,
            opening_discipline=0.5,
            endgame_presence=0.3,
            tactical_sharpness=0.8,
            positional_control=0.45,
            game_length=0.35,
            games_analyzed=1,
        )


@pytest.mark.asyncio
async def test_trainer_generates_profile_from_games() -> None:
    trainer = PersonalityTrainer(TrainingConfig(engine_type="stockfish"), analyzer=FakeAnalyzer())

    profile = await trainer.train_from_games([SAMPLE_PGN], PlayStyle.AGGRESSIVE)

    assert profile.style is PlayStyle.AGGRESSIVE
    assert profile.traits.aggression > 0.7
    assert profile.engine_overrides["Contempt"] > 0


@pytest.mark.asyncio
async def test_trainer_refines_profile_and_runs_pipeline(tmp_path) -> None:
    trainer = PersonalityTrainer(TrainingConfig(engine_type="stockfish"), analyzer=FakeAnalyzer())
    base_profile = await trainer.train_from_games([SAMPLE_PGN], PlayStyle.TACTICAL)

    refined = await trainer.refine_profile(
        base_profile,
        [
            TrainingFeedback(
                outcome=FeedbackOutcome.LOSS,
                confidence=0.8,
                trait_adjustments={"risk_tolerance": -0.5, "positional_play": 0.3},
            )
        ],
    )

    output_path = tmp_path / "profile.json"
    pipeline_profile = await trainer.run_pipeline(
        PipelineConfig(
            pgn_data=[SAMPLE_PGN],
            target_style=PlayStyle.BALANCED,
            feedback=[TrainingFeedback(outcome=FeedbackOutcome.WIN, confidence=0.5)],
            output_path=str(output_path),
            profile_id="custom-profile",
            name="Custom Profile",
            description="Pipeline-generated profile.",
        )
    )

    assert refined.version == base_profile.version + 1
    assert refined.traits.risk_tolerance < base_profile.traits.risk_tolerance
    assert pipeline_profile.id == "custom-profile"
    assert json.loads(output_path.read_text())["name"] == "Custom Profile"
    assert trainer.last_evaluation_score is not None
