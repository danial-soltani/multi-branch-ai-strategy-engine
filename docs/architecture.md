# Architecture

## Objective

The engine reduces dependence on a single model response by separating divergent generation, repeated evaluation, deterministic ranking, and final synthesis.

## Processing sequence

1. Validate the problem statement and runtime configuration.
2. Generate strategies from deliberately different operating perspectives.
3. Evaluate every strategy in isolated model calls.
4. Validate every response against strict Pydantic schemas.
5. Calculate weighted scores in Python.
6. Use the median score to reduce the influence of an outlier evaluation.
7. Calculate score spread to measure evaluator agreement.
8. Rank by median score and use lower spread as the tie-breaker.
9. Send the two strongest strategies and their evaluations to synthesis.
10. Validate and save the final implementation plan as JSON.

## Reliability controls

- Schema validation rejects malformed or unexpected output.
- Criterion bounds reject scores outside 1-10.
- Local arithmetic prevents model calculation errors.
- Exponential backoff and jitter handle transient request failures.
- A semaphore limits simultaneous API requests.
- A per-request timeout cancels a stalled external call before retry logic continues.
- A whole-workflow timeout prevents the orchestration from waiting indefinitely.
- Acceptance tests make each generated action operationally reviewable.

## Scoring

The weighted score is calculated as:

```text
score =
    feasibility       × 0.25
  + scalability       × 0.15
  + risk_mitigation   × 0.25
  + expected_impact   × 0.25
  + evidence_quality  × 0.10
```

The result is on a 1-10 scale.

## Trust boundary

The model proposes strategies and criterion-level judgments. The application owns validation, arithmetic, ranking, concurrency, retry behavior, serialization, and reporting. This separation makes the orchestration logic deterministic even though model outputs remain probabilistic.

## Known limitation

Repeated evaluations are independent API calls but normally use the same configured model. They help expose run-to-run variance; they do not create truly independent expert opinions.
