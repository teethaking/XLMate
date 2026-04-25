from __future__ import annotations

from datetime import datetime, timezone

import pytest

from personality.profile import PersonalityProfile, PersonalityTraits, PlayStyle, SearchPersonalization


def test_profile_creation_and_serialization_round_trip() -> None:
    profile = PersonalityProfile(
        id="profile-1",
        name="Profile 1",
        description="Balanced profile.",
        style=PlayStyle.BALANCED,
        traits=PersonalityTraits(aggression=0.6, creativity=0.7),
        engine_overrides={"Contempt": 12},
        search_params=SearchPersonalization(time_allocation={"opening": 2, "middlegame": 5, "endgame": 3}),
        created_at=datetime.now(timezone.utc),
    )

    payload = profile.model_dump(mode="json")
    restored = PersonalityProfile.model_validate(payload)

    assert restored.id == "profile-1"
    assert restored.traits.aggression == pytest.approx(0.6)
    assert restored.search_params.time_allocation["middlegame"] == pytest.approx(0.5)


def test_trait_bounds_are_validated() -> None:
    with pytest.raises(ValueError):
        PersonalityTraits(aggression=1.1)

    with pytest.raises(ValueError):
        SearchPersonalization(time_allocation={"opening": 1.0, "middlegame": 0.0})
