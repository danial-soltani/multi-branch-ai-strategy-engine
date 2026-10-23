import pytest
from pydantic import ValidationError

from agent_hq_adapter import (
    Candidate,
    CandidateAssessment,
    EvaluationRequest,
    evaluate_offline,
)


def request():
    return EvaluationRequest(
        request_id="req-1",
        team_id="revenue",
        artifact_type="proposal",
        artifact_ref="synthetic-example",
        rubric_version="v1",
        problem_statement="Evaluate a fictional project proposal without external side effects.",
        candidates=[Candidate(candidate_id="a", label="Option alpha"),
                    Candidate(candidate_id="b", label="Option bravo")],
    )


def assessment(candidate_id, score=8, evidence=True):
    return CandidateAssessment(
        candidate_id=candidate_id,
        feasibility=score,
        scalability=score,
        risk_mitigation=score,
        expected_impact=score,
        evidence_quality=score,
        evidence_refs=["synthetic-fixture"] if evidence else [],
    )


def test_offline_evaluation_is_advisory_and_ranked():
    response = evaluate_offline(request(), [assessment("b", 4), assessment("a", 9)])
    assert response.status == "ADVISORY"
    assert response.review_required is True
    assert response.model_id == "offline-fixture"
    assert [r.candidate_id for r in response.results] == ["a", "b"]
    assert [r.score for r in response.results] == [9, 4]
    assert len(response.input_sha256) == 64


def test_missing_evidence_fails_closed():
    response = evaluate_offline(request(), [assessment("a", evidence=False), assessment("b")])
    assert response.status == "NEEDS_REVIEW"


@pytest.mark.parametrize("assessments", [
    [assessment("a")],
    [assessment("a"), assessment("a")],
    [assessment("a"), assessment("other")],
])
def test_missing_duplicate_or_unknown_assessment_is_rejected(assessments):
    with pytest.raises(ValueError):
        evaluate_offline(request(), assessments)


def test_duplicate_candidate_is_rejected():
    payload = request().model_dump()
    payload["candidates"][1]["candidate_id"] = "a"
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(payload)


def test_unknown_input_field_is_rejected():
    payload = request().model_dump()
    payload["secret_token"] = "should never be accepted"
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(payload)
