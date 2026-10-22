# Strategy Engine — GitHub Free CI budget

The shared GitHub Actions Free allowance reached 2,000 of 2,000 included minutes in October 2026. Preserve security and privacy but avoid duplicate jobs.

`.github/workflows/tests.yml` is now scoped to changes in `src/**`, `tests/**`, `requirements.txt`, or the workflow itself, for relevant PRs or main pushes. The former Python 3.11+3.12 matrix is replaced with one Python 3.12 job. `concurrency.cancel-in-progress` suppresses outdated runs on the same PR. A manual `workflow_dispatch` is available for a planned release check.

Before a language-compatibility release, run Python 3.11 tests locally or explicitly restore the 3.11 CI gate. This cost optimization is not proof of cross-Python compatibility. No application source or user data were modified.

Rollback: `checkpoint/ci-budget-before-20261023`.
