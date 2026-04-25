from __future__ import annotations

from personality.profile import PersonalityTraits, SearchPersonalization


def _clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a numeric value to a closed interval."""

    return max(lower, min(upper, value))


def _normalize_time_allocation(opening: float, middlegame: float, endgame: float) -> dict[str, float]:
    """Normalize phase weights so they sum to 1.0."""

    total = opening + middlegame + endgame
    return {
        "opening": opening / total,
        "middlegame": middlegame / total,
        "endgame": endgame / total,
    }


class EngineParameterTuner:
    """Map normalized personality traits to engine and search parameters."""

    def traits_to_uci_options(
        self,
        traits: PersonalityTraits,
        engine_type: str,
    ) -> dict[str, str | int | float]:
        """Convert personality traits to UCI option values."""

        normalized_engine = engine_type.strip().lower()
        if normalized_engine == "stockfish":
            contempt = int(round(((traits.aggression * 0.7) + (traits.risk_tolerance * 0.3) - 0.5) * 160))
            aggressiveness = int(round(_clamp(
                (traits.aggression * 0.55)
                + (traits.risk_tolerance * 0.25)
                + (traits.creativity * 0.2),
                0.0,
                1.0,
            ) * 100))
            multi_pv = max(1, int(round(1 + (traits.creativity * 3))))
            skill_level = int(round(10 + (traits.positional_play * 6) + (traits.endgame_focus * 4)))
            return {
                "Contempt": int(_clamp(contempt, -100, 100)),
                "Aggressiveness": aggressiveness,
                "MultiPV": multi_pv,
                "Skill Level": int(_clamp(skill_level, 0, 20)),
            }

        if normalized_engine == "lc0":
            temperature = round(_clamp(0.1 + (traits.creativity * 0.9) + (traits.risk_tolerance * 0.4), 0.0, 1.5), 3)
            temp_decay_moves = int(round(_clamp(25 - (traits.risk_tolerance * 10) - (traits.creativity * 5), 5, 30)))
            cpuct = round(_clamp(1.2 + (traits.positional_play * 1.2) + (traits.endgame_focus * 0.4) - (traits.aggression * 0.3), 0.5, 3.0), 3)
            fpu_value = round(_clamp(0.2 + (traits.aggression * 0.6) + (traits.risk_tolerance * 0.3), 0.0, 2.0), 3)
            return {
                "Temperature": temperature,
                "TempDecayMoves": temp_decay_moves,
                "CPuct": cpuct,
                "FpuValue": fpu_value,
            }

        raise ValueError(f"unsupported engine type: {engine_type}")

    def traits_to_search_params(self, traits: PersonalityTraits) -> SearchPersonalization:
        """Convert traits to search parameter overrides."""

        contempt = int(round(((traits.aggression * 0.6) + (traits.risk_tolerance * 0.4) - 0.5) * 200))
        move_overhead_ms = int(round(20 + ((1.0 - traits.time_management) * 60)))
        multi_pv = max(1, int(round(1 + (traits.creativity * 3))))
        depth_bias = int(round(((traits.positional_play + traits.endgame_focus) - 1.0) * 4))
        opening = 0.14 + (traits.opening_book_adherence * 0.18)
        middlegame = 0.42 + (traits.aggression * 0.18) + (traits.creativity * 0.06)
        endgame = 0.18 + (traits.endgame_focus * 0.24) + (traits.time_management * 0.05)
        time_allocation = _normalize_time_allocation(opening, middlegame, endgame)

        return SearchPersonalization(
            contempt=int(_clamp(contempt, -100, 100)),
            move_overhead_ms=move_overhead_ms,
            multi_pv=multi_pv,
            depth_bias=int(_clamp(depth_bias, -10, 10)),
            time_allocation=time_allocation,
        )
