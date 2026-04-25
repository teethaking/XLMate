from __future__ import annotations

from personality.presets import get_preset, list_presets


def test_builtin_presets_are_available() -> None:
    presets = list_presets()

    assert len(presets) >= 5
    assert {preset.name for preset in presets} >= {
        "The Attacker",
        "The Fortress",
        "The Tactician",
        "The Grandmaster",
        "The Berserker",
    }


def test_preset_trait_expectations_hold() -> None:
    attacker = get_preset("The Attacker")
    fortress = get_preset("the-fortress")
    berserker = get_preset("the berserker")

    assert attacker.traits.aggression > attacker.traits.positional_play
    assert fortress.traits.positional_play > fortress.traits.aggression
    assert fortress.traits.endgame_focus > 0.8
    assert berserker.traits.aggression == 1.0
    assert berserker.search_params.multi_pv >= 4
