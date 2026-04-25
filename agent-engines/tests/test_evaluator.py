from __future__ import annotations

from personality.evaluator import PersonalityEvaluator
from personality.presets import get_preset
from personality.style_analyzer import GameStyleMetrics


def test_evaluator_scores_matching_profile_higher() -> None:
    evaluator = PersonalityEvaluator()
    attacker = get_preset("The Attacker")
    fortress = get_preset("The Fortress")
    aggressive_metrics = [
        GameStyleMetrics(
            piece_activity=0.7,
            pawn_break_frequency=0.8,
            king_pressure=0.85,
            sacrifice_frequency=0.7,
            move_complexity=0.72,
            opening_discipline=0.45,
            endgame_presence=0.2,
            tactical_sharpness=0.88,
            positional_control=0.35,
            game_length=0.3,
        )
    ]

    attacker_score = evaluator.score_profile(attacker, aggressive_metrics)
    fortress_score = evaluator.score_profile(fortress, aggressive_metrics)

    assert attacker_score > fortress_score
    assert 0.0 <= attacker_score <= 1.0


def test_evaluator_compares_profiles_by_trait_dimension() -> None:
    evaluator = PersonalityEvaluator()
    comparison = evaluator.compare_profiles(
        get_preset("The Attacker"),
        get_preset("The Fortress"),
    )

    assert comparison["trait_differences"]["aggression"] > 0
    assert 0.0 <= comparison["similarity"] <= 1.0
