"""Offline, advisory-only Agent HQ evaluation adapter.

No external model calls, persistence, publishing or approval authority.
All inputs must be sanitized before crossing a product boundary.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Candidate(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=3, max_length=120)


class EvaluationRequest(StrictModel):
    request_id: str = Field(min_length=1, max_length=100)
    team_id: str = Field(min_length=1, max_length=80)
    artifact_type: str = Field(min_length=1, max_length=80)
    artifact_ref: str = Field(min_length=1, max_length=160)
    rubric_version: str = Field(min_length=1, max_length=40)
    problem_statement: str = Field(min_length=20, max_length=1500)
    candidates: list[Candidate] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_candidates(self):
        ids = [c.candidate_id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate IDs")
        return self


class CandidateAssessment(StrictModel):
    candidate_id: str
    feasibility: int = Field(ge=1, le=10)
    scalability: int = Field(ge=1, le=10)
    risk_mitigation: int = Field(ge=1, le=10)
    expected_impact: int = Field(ge=1, le=10)
    evidence_quality: int = Field(ge=1, le=10)
    evidence_refs: list[str] = Field(default_factory=list, max_length=10)
    limitation: str = Field(default="", max_length=400)


class CandidateResult(StrictModel):
    candidate_id: str
    score: float
    evidence_refs: list[str]
    limitation: str


class EvaluationResponse(StrictModel):
    request_id: str
    input_sha256: str
    rubric_version: str
    engine_version: Literal["adapter-v0.1"] = "adapter-v0.1"
    status: Literal["ADVISORY", "NEEDS_REVIEW"]
    review_required: Literal[True] = True
    model_id: Literal["offline-fixture"] = "offline-fixture"
    evaluated_at: str
    results: list[CandidateResult]
    limitations: list[str]


WEIGHTS = {
    "feasibility": 0.25,
    "scalability": 0.15,
    "risk_mitigation": 0.25,
    "expected_impact": 0.25,
    "evidence_quality": 0.10,
}


def evaluate_offline(
    request: EvaluationRequest,
    assessments: list[CandidateAssessment],
) -> EvaluationResponse:
    """Evaluate supplied fixture assessments, never invent evidence or execute actions."""
    expected = {candidate.candidate_id for candidate in request.candidates}
    received = [assessment.candidate_id for assessment in assessments]
    if len(received) != len(set(received)) or set(received) != expected:
        raise ValueError("Assessments must match candidate IDs exactly")

    canonical = request.model_dump_json(exclude_none=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    results = [
        CandidateResult(
            candidate_id=assessment.candidate_id,
            score=round(sum(getattr(assessment, key) * weight for key, weight in WEIGHTS.items()), 3),
            evidence_refs=assessment.evidence_refs,
            limitation=assessment.limitation,
        )
        for assessment in assessments
    ]
    results.sort(key=lambda item: (-item.score, item.candidate_id))
    needs_review = any(not result.evidence_refs or result.limitation for result in results)
    return EvaluationResponse(
        request_id=request.request_id,
        input_sha256=digest,
        rubric_version=request.rubric_version,
        status="NEEDS_REVIEW" if needs_review else "ADVISORY",
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        results=results,
        limitations=["Fixture scores are provided by the caller, not independently verified."],
    )
