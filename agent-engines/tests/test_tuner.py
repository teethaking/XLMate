from __future__ import annotations

import pytest

from personality.profile import PersonalityTraits
from personality.tuner import EngineParameterTuner


@pytest.fixture
def sharp_traits() -> PersonalityTraits:
    return PersonalityTraits(
        aggression=0.85,
        risk_tolerance=0.8,
        positional_play=0.4,
        endgame_focus=0.3,
        time_management=0.45,
        creativity=0.9,
        opening_book_adherence=0.35,
    )


def test_tuner_maps_traits_to_stockfish_options(sharp_traits: PersonalityTraits) -> None:
    tuner = EngineParameterTuner()
    options = tuner.traits_to_uci_options(sharp_traits, "stockfish")
    params = tuner.traits_to_search_params(sharp_traits)

    assert options["Contempt"] > 0
    assert options["Aggressiveness"] >= 70
    assert options["MultiPV"] >= 3
    assert params.multi_pv >= 3
    assert pytest.approx(sum(params.time_allocation.values())) == 1.0


def test_tuner_maps_traits_to_lc0_options(sharp_traits: PersonalityTraits) -> None:
    tuner = EngineParameterTuner()
    options = tuner.traits_to_uci_options(sharp_traits, "lc0")

    assert options["Temperature"] > 0.5
    assert options["TempDecayMoves"] >= 5
    assert options["CPuct"] >= 0.5
