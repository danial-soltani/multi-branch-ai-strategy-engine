import statistics
from unittest.mock import AsyncMock, patch

import pytest
from google.genai import errors as genai_errors

from strategy_engine import (
    Evaluation,
    Settings,
    StrategicApproach,
    evaluate_approach,
    is_retryable_error,
)


def evaluation(score: int) -> Evaluation:
    return Evaluation(
        feasibility=score,
        scalability=score,
        risk_mitigation=score,
        expected_impact=score,
        evidence_quality=score,
        rationale="A sufficiently detailed assessment for the test case.",
        improvement="Improve the implementation with a measured change.",
    )


@pytest.mark.asyncio
async def test_even_judge_count_uses_true_median():
    approach = StrategicApproach(
        name="Test strategy",
        perspective="Reliability first",
        summary="A sufficiently detailed summary for a valid test strategy.",
        key_mechanism="A measurable operating mechanism for evaluation.",
    )
    with patch("strategy_engine.evaluate_once", new_callable=AsyncMock) as mock:
        mock.side_effect = [evaluation(2), evaluation(8)]
        result = await evaluate_approach(
            None, Settings(judges_per_branch=2), "Test problem", approach, None
        )
    assert result["median_score"] == statistics.median([2, 8]) == 5


def test_retry_policy():
    assert is_retryable_error(TimeoutError())
    assert is_retryable_error(ConnectionError())
    assert not is_retryable_error(ValueError("invalid schema"))
    assert not is_retryable_error(PermissionError("not authorized"))
    assert is_retryable_error(genai_errors.ClientError(429, {"error": {"message": "rate limited"}}))
    assert is_retryable_error(genai_errors.ServerError(503, {"error": {"message": "unavailable"}}))
    assert not is_retryable_error(genai_errors.ClientError(401, {"error": {"message": "unauthorized"}}))
