# Agent HQ Evaluation Adapter — contract v0.1 (proposal)

Status: **design only**. This repository is a strategy-evaluation utility, **not** the Agent HQ executor. No direct cross-project integration or autonomous agent execution is enabled.

## Boundary

Agent HQ may submit a sanitized `evaluation_request` containing:
- `request_id`, `team_id`, `artifact_type`, `artifact_ref`, `rubric_version`
- `problem_statement` and non-sensitive candidate approaches
- `requested_by`, `created_at`, `model_policy`

The evaluation service may return:
- `request_id`, `engine_version`, `model_id`, `rubric_version`
- candidate scores and evidence references, disagreement/spread
- `limitations`, `review_required=true`, `status=ADVISORY`

## Non-negotiable controls

1. **No execution authority:** evaluation never approves bids, spending, publishing, merges, or deployment.
2. **Human approval:** separate signed approval required for any external/production action.
3. **Evidence:** retain input hash, rubric/model versions, timestamp, test references and explicit uncertainty.
4. **Data minimization:** never send Pet Life private content, customer secrets, credentials, or confidential cross-team data to an external model without explicit clearance.
5. **Shared Engineering Core lifecycle:** CANDIDATE → EVIDENCE_REVIEW → VERIFIED → APPLIED_TO_TARGET → REVALIDATED.
6. **CTLP boundary:** code/knowledge transfer requires license check, compatibility check, target-specific QA, and owner approval.
7. **Fail closed:** missing evidence, timeout, schema failure or low agreement means `NEEDS_REVIEW`, not silent success.
8. **Cost:** require configurable call limits and budget caps before any live API integration.

## Implementation gates

- Gate A: regression tests and PR review (this PR).
- Gate B: schema-only adapter and offline fixture tests in a separate branch.
- Gate C: sanitized end-to-end sandbox trial with measured latency and token cost.
- Gate D: explicit owner approval before any real Agent HQ connection.

This contract introduces **no sixth team**. Shared Engineering Core remains a parent-company horizontal capability.
