from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from personality.profile import PersonalityProfile, PersonalityTraits, PlayStyle, SearchPersonalization


def _created_at() -> datetime:
    """Return a timezone-aware creation timestamp for preset materialization."""

    return datetime.now(timezone.utc)


def _profile(
    *,
    profile_id: str,
    name: str,
    description: str,
    style: PlayStyle,
    traits: PersonalityTraits,
    engine_overrides: dict[str, str | int | float],
    search_params: SearchPersonalization,
) -> PersonalityProfile:
    """Build a preset profile with normalized defaults."""

    return PersonalityProfile(
        id=profile_id,
        name=name,
        description=description,
        style=style,
        traits=traits,
        engine_overrides=engine_overrides,
        search_params=search_params,
        created_at=_created_at(),
    )


_PRESET_BUILDERS: dict[str, Callable[[], PersonalityProfile]] = {
    "the attacker": lambda: _profile(
        profile_id="the-attacker",
        name="The Attacker",
        description="High-pressure play focused on initiative, attacks, and active complications.",
        style=PlayStyle.AGGRESSIVE,
        traits=PersonalityTraits(
            aggression=0.9,
            risk_tolerance=0.82,
            positional_play=0.3,
            endgame_focus=0.45,
            time_management=0.48,
            creativity=0.8,
            opening_book_adherence=0.42,
        ),
        engine_overrides={"Contempt": 55, "Aggressiveness": 88, "MultiPV": 2},
        search_params=SearchPersonalization(
            contempt=55,
            move_overhead_ms=42,
            multi_pv=2,
            depth_bias=-1,
            time_allocation={"opening": 0.14, "middlegame": 0.64, "endgame": 0.22},
        ),
    ),
    "the fortress": lambda: _profile(
        profile_id="the-fortress",
        name="The Fortress",
        description="Low-risk, resilient play that values structure, king safety, and technical endings.",
        style=PlayStyle.DEFENSIVE,
        traits=PersonalityTraits(
            aggression=0.18,
            risk_tolerance=0.15,
            positional_play=0.88,
            endgame_focus=0.86,
            time_management=0.72,
            creativity=0.33,
            opening_book_adherence=0.76,
        ),
        engine_overrides={"Contempt": -30, "Aggressiveness": 20, "MultiPV": 1},
        search_params=SearchPersonalization(
            contempt=-30,
            move_overhead_ms=26,
            multi_pv=1,
            depth_bias=2,
            time_allocation={"opening": 0.2, "middlegame": 0.43, "endgame": 0.37},
        ),
    ),
    "the tactician": lambda: _profile(
        profile_id="the-tactician",
        name="The Tactician",
        description="Sharp calculation with resourceful ideas, material imbalances, and dynamic play.",
        style=PlayStyle.TACTICAL,
        traits=PersonalityTraits(
            aggression=0.62,
            risk_tolerance=0.78,
            positional_play=0.48,
            endgame_focus=0.44,
            time_management=0.52,
            creativity=0.9,
            opening_book_adherence=0.38,
        ),
        engine_overrides={"Contempt": 35, "Aggressiveness": 76, "MultiPV": 3},
        search_params=SearchPersonalization(
            contempt=35,
            move_overhead_ms=38,
            multi_pv=3,
            depth_bias=0,
            time_allocation={"opening": 0.13, "middlegame": 0.61, "endgame": 0.26},
        ),
    ),
    "the grandmaster": lambda: _profile(
        profile_id="the-grandmaster",
        name="The Grandmaster",
        description="Balanced, principled play with stable technique and strong resource management.",
        style=PlayStyle.BALANCED,
        traits=PersonalityTraits(
            aggression=0.55,
            risk_tolerance=0.46,
            positional_play=0.68,
            endgame_focus=0.72,
            time_management=0.86,
            creativity=0.58,
            opening_book_adherence=0.7,
        ),
        engine_overrides={"Contempt": 10, "Aggressiveness": 58, "MultiPV": 2},
        search_params=SearchPersonalization(
            contempt=10,
            move_overhead_ms=22,
            multi_pv=2,
            depth_bias=1,
            time_allocation={"opening": 0.18, "middlegame": 0.5, "endgame": 0.32},
        ),
    ),
    "the berserker": lambda: _profile(
        profile_id="the-berserker",
        name="The Berserker",
        description="All-out attacking instincts with minimal restraint and a willingness to burn time and material.",
        style=PlayStyle.AGGRESSIVE,
        traits=PersonalityTraits(
            aggression=1.0,
            risk_tolerance=1.0,
            positional_play=0.08,
            endgame_focus=0.18,
            time_management=0.16,
            creativity=0.74,
            opening_book_adherence=0.22,
        ),
        engine_overrides={"Contempt": 90, "Aggressiveness": 100, "MultiPV": 4},
        search_params=SearchPersonalization(
            contempt=90,
            move_overhead_ms=58,
            multi_pv=4,
            depth_bias=-2,
            time_allocation={"opening": 0.11, "middlegame": 0.69, "endgame": 0.2},
        ),
    ),
}

_STYLE_TO_PRESET = {
    PlayStyle.AGGRESSIVE: "the attacker",
    PlayStyle.DEFENSIVE: "the fortress",
    PlayStyle.POSITIONAL: "the grandmaster",
    PlayStyle.TACTICAL: "the tactician",
    PlayStyle.BALANCED: "the grandmaster",
}


def list_presets() -> list[PersonalityProfile]:
    """Return all built-in presets as independent profile instances."""

    return [builder() for builder in _PRESET_BUILDERS.values()]


def get_preset(name: str) -> PersonalityProfile:
    """Load a built-in preset by human-readable name or identifier."""

    normalized = name.strip().lower().replace("_", " ")
    for preset in list_presets():
        if normalized in {preset.name.lower(), preset.id.replace("-", " "), preset.id}:
            return preset
    if normalized in _PRESET_BUILDERS:
        return _PRESET_BUILDERS[normalized]()
    raise KeyError(f"unknown personality preset: {name}")


def get_style_anchor(style: PlayStyle) -> PersonalityTraits:
    """Return preset traits used as anchor targets during training."""

    preset = get_preset(_STYLE_TO_PRESET[style])
    return preset.traits.model_copy(deep=True)
