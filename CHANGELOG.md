# Changelog

## 1.0.1 - 2026-10-03

### Added

- Configurable timeout for every Gemini request.
- Separate timeout for the complete multi-stage workflow.
- CLI options `--request-timeout` and `--workflow-timeout`.
- Explicit timeout error handling and exit status.
- Automated tests for successful completion and stalled-operation cancellation.

## 1.0.0 - 2026-10-02

### Added

- Multi-perspective strategy generation.
- Repeated rubric-based evaluation.
- Deterministic weighted scoring and agreement-aware ranking.
- Top-two strategy synthesis.
- Structured JSON output, retries, bounded concurrency, tests, and CI.
