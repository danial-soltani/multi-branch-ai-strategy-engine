from strategy_engine import StrategicApproach


def candidate(name: str, median_score: float, score_spread: float) -> dict:
    return {
        "approach": StrategicApproach(
            name=name,
            perspective="test perspective",
            summary="A sufficiently detailed strategy summary for deterministic ranking tests.",
            key_mechanism="A measurable operating mechanism used for testing.",
        ),
        "evaluations": [],
        "median_score": median_score,
        "score_spread": score_spread,
        "fatal_flaws": [],
    }


def rank(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            item["median_score"],
            -item["score_spread"],
        ),
        reverse=True,
    )


def test_higher_median_score_ranks_first():
    ranked = rank([
        candidate("Lower", 7.8, 0.2),
        candidate("Higher", 8.1, 0.8),
    ])
    assert ranked[0]["approach"].name == "Higher"


def test_lower_disagreement_breaks_a_tie():
    ranked = rank([
        candidate("Unstable", 8.0, 1.4),
        candidate("Stable", 8.0, 0.3),
    ])
    assert ranked[0]["approach"].name == "Stable"
