from __future__ import annotations

from personality.profile import PersonalityProfile
from personality.style_analyzer import GameStyleMetrics, aggregate_metrics, StyleAnalyzer


class PersonalityEvaluator:
    """Evaluate how closely a profile matches observed game behavior."""

    def __init__(self, analyzer: StyleAnalyzer | None = None) -> None:
        self._analyzer = analyzer or StyleAnalyzer()

    def score_profile(
        self,
        profile: PersonalityProfile,
        game_results: list[GameStyleMetrics],
    ) -> float:
        """Score how well the profile's traits match observed style metrics."""

        if not game_results:
            return 0.0
        observed = self._analyzer.style_to_traits(aggregate_metrics(game_results))
        deltas = []
        for field_name in type(profile.traits).model_fields:
            deltas.append(abs(getattr(profile.traits, field_name) - getattr(observed, field_name)))
        return max(0.0, 1.0 - (sum(deltas) / len(deltas)))

    def compare_profiles(
        self,
        profile_a: PersonalityProfile,
        profile_b: PersonalityProfile,
    ) -> dict[str, object]:
        """Compare two profiles across trait dimensions."""

        differences = {
            field_name: round(
                getattr(profile_a.traits, field_name) - getattr(profile_b.traits, field_name),
                4,
            )
            for field_name in type(profile_a.traits).model_fields
        }
        average_distance = sum(abs(value) for value in differences.values()) / len(differences)
        return {
            "profile_a": profile_a.id,
            "profile_b": profile_b.id,
            "trait_differences": differences,
            "similarity": round(max(0.0, 1.0 - average_distance), 4),
        }
