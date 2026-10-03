from strategy_engine import Evaluation, weighted_score


def make_evaluation(**overrides):
    values = {
        "feasibility": 8,
        "scalability": 7,
        "risk_mitigation": 9,
        "expected_impact": 8,
        "evidence_quality": 6,
        "fatal_flaw": None,
        "rationale": "The approach has a clear mechanism and realistic implementation path.",
        "improvement": "Add a measurable pilot gate before production rollout.",
    }
    values.update(overrides)
    return Evaluation(**values)


def test_weighted_score_is_calculated_locally():
    assert weighted_score(make_evaluation()) == 7.9


def test_weighted_score_changes_predictably():
    assert weighted_score(make_evaluation(expected_impact=10)) == 8.4
