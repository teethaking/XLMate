from __future__ import annotations

from personality.style_analyzer import AggregateStyleMetrics, StyleAnalyzer


SAMPLE_PGN = """[Event \"Test Game\"]
[White \"Attacker\"]
[Black \"Defender\"]
[Result \"1-0\"]
1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O 1-0
"""


def test_style_analyzer_extracts_metrics_from_sample_pgn() -> None:
    analyzer = StyleAnalyzer()
    metrics = analyzer.analyze_game(SAMPLE_PGN)

    assert metrics.tactical_sharpness > 0.25
    assert metrics.sacrifice_frequency > 0.05
    assert metrics.opening_discipline > 0.4


def test_style_analyzer_converts_aggregate_metrics_to_traits() -> None:
    analyzer = StyleAnalyzer()
    aggregate = analyzer.analyze_corpus([SAMPLE_PGN, SAMPLE_PGN])
    traits = analyzer.style_to_traits(aggregate)

    assert isinstance(aggregate, AggregateStyleMetrics)
    assert aggregate.games_analyzed == 2
    assert traits.aggression > 0.5
    assert traits.creativity > 0.3
