import pytest
from pydantic import ValidationError

from strategy_engine import Evaluation, Settings


BASE = {
    "feasibility": 8,
    "scalability": 7,
    "risk_mitigation": 9,
    "expected_impact": 8,
    "evidence_quality": 6,
    "fatal_flaw": None,
    "rationale": "The approach has a clear mechanism and realistic implementation path.",
    "improvement": "Add a measurable pilot gate before production rollout.",
}


def test_out_of_range_score_is_rejected():
    with pytest.raises(ValidationError):
        Evaluation(**{**BASE, "feasibility": 11})


def test_unexpected_field_is_rejected():
    with pytest.raises(ValidationError):
        Evaluation(**{**BASE, "invented_total": 30})


def test_runtime_defaults_are_portfolio_ready():
    settings = Settings()
    assert settings.num_branches == 4
    assert settings.judges_per_branch == 3
    assert settings.max_concurrency == 4
    assert settings.request_timeout_seconds == 60.0
    assert settings.workflow_timeout_seconds == 600.0
