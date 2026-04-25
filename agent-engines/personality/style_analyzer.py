from __future__ import annotations

import io

import chess
import chess.pgn
from pydantic import BaseModel, ConfigDict, Field

from personality.profile import PersonalityTraits


class GameStyleMetrics(BaseModel):
    """Normalized style metrics extracted from a single PGN game."""

    model_config = ConfigDict(extra="forbid")

    piece_activity: float = Field(ge=0.0, le=1.0)
    pawn_break_frequency: float = Field(ge=0.0, le=1.0)
    king_pressure: float = Field(ge=0.0, le=1.0)
    sacrifice_frequency: float = Field(ge=0.0, le=1.0)
    move_complexity: float = Field(ge=0.0, le=1.0)
    opening_discipline: float = Field(ge=0.0, le=1.0)
    endgame_presence: float = Field(ge=0.0, le=1.0)
    tactical_sharpness: float = Field(ge=0.0, le=1.0)
    positional_control: float = Field(ge=0.0, le=1.0)
    game_length: float = Field(ge=0.0, le=1.0)


class AggregateStyleMetrics(GameStyleMetrics):
    """Average style metrics over a corpus of games."""

    games_analyzed: int = Field(ge=1)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp a floating-point value to a closed interval."""

    return max(lower, min(upper, value))


class StyleAnalyzer:
    """Analyze chess games to infer personality-related style metrics."""

    def analyze_game(self, pgn: str) -> GameStyleMetrics:
        """Analyze a single game for style metrics."""

        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            raise ValueError("unable to parse PGN data")

        board = game.board()
        total_plies = 0
        checks = 0
        captures = 0
        castles = 0
        risky_moves = 0
        king_pressure_total = 0.0
        activity_total = 0.0
        complexity_total = 0.0
        central_pawn_pushes = 0
        opening_irregularities = 0.0
        development_moves = 0
        repeated_piece_moves = 0
        endgame_seen = False
        seen_origins: dict[chess.Color, set[int]] = {
            chess.WHITE: set(),
            chess.BLACK: set(),
        }

        for ply_index, move in enumerate(game.mainline_moves(), start=1):
            mover = board.turn
            piece = board.piece_at(move.from_square)
            if piece is None:
                raise ValueError("encountered illegal PGN move sequence")

            legal_moves = board.legal_moves.count()
            complexity_total += _clamp(legal_moves / 40.0)
            activity_total += _clamp(legal_moves / 35.0)

            if board.is_capture(move):
                captures += 1
            if board.is_castling(move):
                castles += 1
            if piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
                if move.from_square in seen_origins[mover]:
                    repeated_piece_moves += 1
                else:
                    seen_origins[mover].add(move.from_square)
                    development_moves += 1

            if piece.piece_type == chess.QUEEN and ply_index <= 12:
                opening_irregularities += 0.5
            if piece.piece_type == chess.ROOK and ply_index <= 14:
                opening_irregularities += 0.35
            if piece.piece_type == chess.PAWN:
                file_index = chess.square_file(move.from_square)
                rank_delta = abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square))
                if file_index in {0, 1, 6, 7} and ply_index <= 12:
                    opening_irregularities += 0.2
                if chess.square_file(move.to_square) in {2, 3, 4, 5} and rank_delta >= 1:
                    central_pawn_pushes += 1
                if rank_delta == 2 or board.is_capture(move):
                    central_pawn_pushes += 1

            board.push(move)
            total_plies += 1

            if board.is_check():
                checks += 1

            moved_color = not board.turn
            destination = move.to_square
            attackers = len(board.attackers(board.turn, destination))
            defenders = len(board.attackers(moved_color, destination))
            if attackers > defenders:
                risky_moves += 1

            enemy_king_square = board.king(board.turn)
            if enemy_king_square is not None:
                pressure_squares = [enemy_king_square, *board.attacks(enemy_king_square)]
                attacked = 0
                for square in pressure_squares:
                    if board.is_attacked_by(moved_color, square):
                        attacked += 1
                king_pressure_total += _clamp(attacked / max(1, len(pressure_squares)))

            non_pawn_material = 0
            for candidate in board.piece_map().values():
                if candidate.piece_type not in {chess.KING, chess.PAWN}:
                    non_pawn_material += 1
            if non_pawn_material <= 6:
                endgame_seen = True

        if total_plies == 0:
            raise ValueError("PGN does not contain any moves")

        opening_irregularity_ratio = opening_irregularities / max(1.0, min(total_plies, 12.0))
        tactical_activity = (checks + captures + risky_moves) / total_plies
        positional_base = (
            (development_moves / max(1, total_plies / 2.0))
            + (castles / max(1, total_plies / 20.0))
            + (1.0 - _clamp(opening_irregularity_ratio))
        ) / 3.0

        return GameStyleMetrics(
            piece_activity=_clamp(activity_total / total_plies),
            pawn_break_frequency=_clamp(central_pawn_pushes / total_plies * 1.6),
            king_pressure=_clamp(king_pressure_total / total_plies),
            sacrifice_frequency=_clamp(risky_moves / total_plies * 1.5),
            move_complexity=_clamp(complexity_total / total_plies),
            opening_discipline=_clamp(1.0 - opening_irregularity_ratio),
            endgame_presence=1.0 if endgame_seen else _clamp(total_plies / 80.0),
            tactical_sharpness=_clamp(tactical_activity * 2.0),
            positional_control=_clamp(positional_base),
            game_length=_clamp(total_plies / 80.0),
        )

    def analyze_corpus(self, pgns: list[str]) -> AggregateStyleMetrics:
        """Analyze a collection of games for overall style."""

        if not pgns:
            raise ValueError("at least one PGN game is required")
        metrics = [self.analyze_game(pgn) for pgn in pgns]
        return aggregate_metrics(metrics)

    def style_to_traits(self, metrics: AggregateStyleMetrics) -> PersonalityTraits:
        """Convert aggregate style metrics into personality trait scores."""

        aggression = _clamp(
            (metrics.king_pressure * 0.35)
            + (metrics.tactical_sharpness * 0.3)
            + (metrics.pawn_break_frequency * 0.2)
            + (metrics.move_complexity * 0.15)
        )
        risk_tolerance = _clamp(
            (metrics.sacrifice_frequency * 0.45)
            + (metrics.tactical_sharpness * 0.3)
            + ((1.0 - metrics.opening_discipline) * 0.25)
        )
        positional_play = _clamp(
            (metrics.positional_control * 0.45)
            + (metrics.opening_discipline * 0.3)
            + (metrics.endgame_presence * 0.15)
            + ((1.0 - metrics.tactical_sharpness) * 0.1)
        )
        endgame_focus = _clamp((metrics.endgame_presence * 0.75) + (metrics.game_length * 0.25))
        time_management = _clamp(
            0.45
            + (metrics.opening_discipline * 0.2)
            + (metrics.positional_control * 0.15)
            + (metrics.endgame_presence * 0.1)
            - (metrics.sacrifice_frequency * 0.1)
        )
        creativity = _clamp(
            (metrics.sacrifice_frequency * 0.35)
            + ((1.0 - metrics.opening_discipline) * 0.3)
            + (metrics.move_complexity * 0.2)
            + (metrics.tactical_sharpness * 0.15)
        )
        opening_book_adherence = _clamp(
            (metrics.opening_discipline * 0.75)
            + ((1.0 - metrics.sacrifice_frequency) * 0.25)
        )

        return PersonalityTraits(
            aggression=aggression,
            risk_tolerance=risk_tolerance,
            positional_play=positional_play,
            endgame_focus=endgame_focus,
            time_management=time_management,
            creativity=creativity,
            opening_book_adherence=opening_book_adherence,
        )


def aggregate_metrics(metrics: list[GameStyleMetrics]) -> AggregateStyleMetrics:
    """Average single-game metrics into a corpus-level summary."""

    if not metrics:
        raise ValueError("at least one game metric is required")

    count = len(metrics)
    field_names = GameStyleMetrics.model_fields.keys()
    averaged = {
        field_name: sum(getattr(metric, field_name) for metric in metrics) / count
        for field_name in field_names
    }
    return AggregateStyleMetrics(**averaged, games_analyzed=count)
