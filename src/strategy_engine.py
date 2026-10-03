"""Robust Generate -> Evaluate -> Select -> Synthesize workflow for Gemini.

Install:
    pip install -U google-genai pydantic

Run:
    export GEMINI_API_KEY="..."
    python optimized_tree_of_thoughts.py "Your problem statement"

The program stores a complete JSON report in tot_report.json by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field


LOGGER = logging.getLogger("strategy_engine")
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrategicApproach(StrictModel):
    name: str = Field(min_length=3, max_length=100)
    perspective: str = Field(min_length=3, max_length=80)
    summary: str = Field(min_length=20, max_length=700)
    key_mechanism: str = Field(min_length=10, max_length=400)


class ApproachSet(StrictModel):
    approaches: list[StrategicApproach]


class Evaluation(StrictModel):
    feasibility: int = Field(ge=1, le=10)
    scalability: int = Field(ge=1, le=10)
    risk_mitigation: int = Field(ge=1, le=10)
    expected_impact: int = Field(ge=1, le=10)
    evidence_quality: int = Field(ge=1, le=10)
    fatal_flaw: str | None = Field(default=None, max_length=350)
    rationale: str = Field(min_length=20, max_length=900)
    improvement: str = Field(min_length=10, max_length=500)


class ActionStep(StrictModel):
    order: int = Field(ge=1)
    action: str = Field(min_length=10, max_length=500)
    owner_or_component: str = Field(min_length=2, max_length=120)
    deliverable: str = Field(min_length=3, max_length=250)
    acceptance_test: str = Field(min_length=5, max_length=350)


class FailureControl(StrictModel):
    failure_mode: str = Field(min_length=5, max_length=300)
    early_signal: str = Field(min_length=3, max_length=250)
    control: str = Field(min_length=5, max_length=400)


class FinalPlan(StrictModel):
    title: str = Field(min_length=3, max_length=140)
    executive_summary: str = Field(min_length=40, max_length=1200)
    why_this_plan: str = Field(min_length=20, max_length=700)
    action_steps: list[ActionStep]
    failure_controls: list[FailureControl]
    success_metrics: list[str]
    first_72_hours: list[str]


@dataclass(frozen=True)
class Settings:
    model_id: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    num_branches: int = 4
    judges_per_branch: int = 3
    max_concurrency: int = 4
    max_attempts: int = 4
    retry_base_seconds: float = 1.5
    request_timeout_seconds: float = 60.0
    workflow_timeout_seconds: float = 600.0
    output_path: Path = Path("tot_report.json")


WEIGHTS = {
    "feasibility": 0.25,
    "scalability": 0.15,
    "risk_mitigation": 0.25,
    "expected_impact": 0.25,
    "evidence_quality": 0.10,
}

PERSPECTIVES = [
    "fastest practical implementation",
    "highest quality and reliability",
    "lowest cost and operational complexity",
    "most scalable production architecture",
    "strongest risk-control and fallback design",
]


def require_api_key() -> None:
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "Set GEMINI_API_KEY (or GOOGLE_API_KEY) before running this program."
        )


def weighted_score(evaluation: Evaluation) -> float:
    """Calculate the score locally; never trust arithmetic produced by the model."""
    return round(
        sum(getattr(evaluation, metric) * weight for metric, weight in WEIGHTS.items()),
        3,
    )


async def await_with_timeout(awaitable, timeout_seconds: float):
    """Await one operation with a hard deadline and cancellation on timeout."""
    async with asyncio.timeout(timeout_seconds):
        return await awaitable


async def generate_typed(
    client: genai.Client,
    settings: Settings,
    prompt: str,
    schema: type[SchemaT],
    *,
    temperature: float,
    semaphore: asyncio.Semaphore,
) -> SchemaT:
    """Call Gemini with schema validation plus bounded exponential backoff."""
    last_error: Exception | None = None
    async with semaphore:
        for attempt in range(1, settings.max_attempts + 1):
            try:
                response = await await_with_timeout(
                    client.aio.models.generate_content(
                        model=settings.model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                            temperature=temperature,
                        ),
                    ),
                    settings.request_timeout_seconds,
                )
                if getattr(response, "parsed", None) is not None:
                    parsed = response.parsed
                    return parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
                if not response.text:
                    raise ValueError("Gemini returned an empty response.")
                return schema.model_validate_json(response.text)
            except Exception as exc:  # SDK/network/schema errors are retried together.
                last_error = exc
                if attempt == settings.max_attempts:
                    break
                delay = settings.retry_base_seconds * (2 ** (attempt - 1))
                delay += random.uniform(0, 0.35 * delay)
                LOGGER.warning("Attempt %s failed; retrying in %.1fs: %s", attempt, delay, exc)
                await asyncio.sleep(delay)
    raise RuntimeError(f"Gemini request failed after {settings.max_attempts} attempts") from last_error


async def generate_approaches(
    client: genai.Client,
    settings: Settings,
    problem: str,
    semaphore: asyncio.Semaphore,
) -> list[StrategicApproach]:
    perspectives = PERSPECTIVES[: settings.num_branches]
    prompt = f"""
You are a strategic solution architect.

Problem:
{problem}

Create exactly {settings.num_branches} genuinely different high-level approaches.
Use each of these perspectives once and in the same order:
{json.dumps(perspectives, ensure_ascii=False)}

Keep the approaches solution-focused. Do not reveal private chain-of-thought.
State only the proposed strategy and its key operating mechanism.
""".strip()
    result = await generate_typed(
        client, settings, prompt, ApproachSet, temperature=0.8, semaphore=semaphore
    )
    if len(result.approaches) != settings.num_branches:
        raise ValueError(
            f"Expected {settings.num_branches} approaches, got {len(result.approaches)}."
        )
    return result.approaches


async def evaluate_once(
    client: genai.Client,
    settings: Settings,
    problem: str,
    approach: StrategicApproach,
    judge_number: int,
    semaphore: asyncio.Semaphore,
) -> Evaluation:
    # The neutral label and isolated call reduce ordering and comparison bias.
    prompt = f"""
Act as independent evaluator J{judge_number}. Assess one anonymous strategy.

Problem:
{problem}

Candidate strategy:
{approach.model_dump_json(indent=2)}

Score these dimensions independently from 1 to 10:
- feasibility: implementable with realistic resources and dependencies
- scalability: can grow without disproportionate cost or fragility
- risk_mitigation: anticipates and controls important failure modes
- expected_impact: likely to solve the stated problem materially
- evidence_quality: claims are testable and supported by sound mechanisms

Use conservative scores. Identify a fatal flaw only if one truly exists.
Give a concise rationale and one concrete improvement. Do not reveal private
chain-of-thought; provide only the decision-relevant assessment.
""".strip()
    return await generate_typed(
        client, settings, prompt, Evaluation, temperature=0.15, semaphore=semaphore
    )


async def evaluate_approach(
    client: genai.Client,
    settings: Settings,
    problem: str,
    approach: StrategicApproach,
    semaphore: asyncio.Semaphore,
) -> dict:
    evaluations = await asyncio.gather(
        *[
            evaluate_once(client, settings, problem, approach, judge, semaphore)
            for judge in range(1, settings.judges_per_branch + 1)
        ]
    )
    scores = sorted(weighted_score(item) for item in evaluations)
    median_score = scores[len(scores) // 2]
    fatal_flaws = [item.fatal_flaw for item in evaluations if item.fatal_flaw]
    return {
        "approach": approach,
        "evaluations": evaluations,
        "median_score": median_score,
        "score_spread": round(max(scores) - min(scores), 3),
        "fatal_flaws": fatal_flaws,
    }


async def synthesize_plan(
    client: genai.Client,
    settings: Settings,
    problem: str,
    ranked: list[dict],
    semaphore: asyncio.Semaphore,
) -> FinalPlan:
    finalists = ranked[:2]
    finalist_payload = []
    for item in finalists:
        finalist_payload.append(
            {
                "approach": item["approach"].model_dump(),
                "median_score": item["median_score"],
                "score_spread": item["score_spread"],
                "judge_rationales": [e.rationale for e in item["evaluations"]],
                "recommended_improvements": [e.improvement for e in item["evaluations"]],
                "fatal_flaws": item["fatal_flaws"],
            }
        )

    prompt = f"""
You are the lead solution architect.

Problem:
{problem}

The two strongest independently evaluated approaches are:
{json.dumps(finalist_payload, ensure_ascii=False, indent=2)}

Create one implementation plan. Use the top-ranked approach as the backbone,
but incorporate compatible strengths from the runner-up. Explicitly resolve
conflicts instead of blindly merging them. Make every action testable through a
deliverable and acceptance test. Include failure controls, success metrics, and
the first actions to complete within 72 hours. Do not reveal private
chain-of-thought; provide concise decision rationale only.
""".strip()
    return await generate_typed(
        client, settings, prompt, FinalPlan, temperature=0.25, semaphore=semaphore
    )


async def run_strategy_engine(problem: str, settings: Settings) -> dict:
    if not problem.strip():
        raise ValueError("Problem statement cannot be empty.")
    if settings.num_branches < 2 or settings.num_branches > len(PERSPECTIVES):
        raise ValueError(f"num_branches must be between 2 and {len(PERSPECTIVES)}.")
    if settings.judges_per_branch < 1:
        raise ValueError("judges_per_branch must be at least 1.")
    if settings.max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1.")
    if settings.request_timeout_seconds <= 0:
        raise ValueError("request_timeout_seconds must be greater than 0.")
    if settings.workflow_timeout_seconds <= 0:
        raise ValueError("workflow_timeout_seconds must be greater than 0.")

    require_api_key()
    client = genai.Client()
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    LOGGER.info("Generating %s diverse approaches...", settings.num_branches)
    approaches = await generate_approaches(client, settings, problem, semaphore)

    LOGGER.info("Running independent evaluations...")
    evaluated = await asyncio.gather(
        *[
            evaluate_approach(client, settings, problem, approach, semaphore)
            for approach in approaches
        ]
    )
    ranked = sorted(
        evaluated,
        key=lambda item: (item["median_score"], -item["score_spread"]),
        reverse=True,
    )

    LOGGER.info("Synthesizing the two strongest approaches...")
    final_plan = await synthesize_plan(client, settings, problem, ranked, semaphore)

    report = {
        "problem": problem,
        "model": settings.model_id,
        "weights": WEIGHTS,
        "configuration": {
            "num_branches": settings.num_branches,
            "judges_per_branch": settings.judges_per_branch,
            "max_concurrency": settings.max_concurrency,
            "request_timeout_seconds": settings.request_timeout_seconds,
            "workflow_timeout_seconds": settings.workflow_timeout_seconds,
        },
        "ranking": [
            {
                "rank": index,
                "approach": item["approach"].model_dump(),
                "median_score": item["median_score"],
                "score_spread": item["score_spread"],
                "evaluations": [e.model_dump() for e in item["evaluations"]],
            }
            for index, item in enumerate(ranked, start=1)
        ],
        "final_plan": final_plan.model_dump(),
    }
    settings.output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


async def run_strategy_engine_with_timeout(problem: str, settings: Settings) -> dict:
    """Apply a hard deadline to the complete multi-stage workflow."""
    return await await_with_timeout(
        run_strategy_engine(problem, settings),
        settings.workflow_timeout_seconds,
    )


def print_summary(report: dict, output_path: Path) -> None:
    print("\n" + "=" * 72)
    print("RANKING")
    print("=" * 72)
    for item in report["ranking"]:
        name = item["approach"]["name"]
        print(
            f"{item['rank']}. {name} | median={item['median_score']:.2f}/10 "
            f"| judge spread={item['score_spread']:.2f}"
        )

    plan = report["final_plan"]
    print("\n" + "=" * 72)
    print(plan["title"])
    print("=" * 72)
    print(plan["executive_summary"])
    print("\nFirst 72 hours:")
    for item in plan["first_72_hours"]:
        print(f"- {item}")
    print(f"\nFull JSON report: {output_path.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate, evaluate, rank, and synthesize strategic solutions with Gemini."
    )
    parser.add_argument(
        "problem",
        nargs="?",
        default=(
            "Design an automated QA pipeline for controlled AI image generation "
            "to prevent character face drift across multiple camera angles."
        ),
    )
    parser.add_argument("--branches", type=int, default=4)
    parser.add_argument("--judges", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=60.0,
        help="Maximum seconds allowed for one Gemini request.",
    )
    parser.add_argument(
        "--workflow-timeout",
        type=float,
        default=600.0,
        help="Maximum seconds allowed for the complete workflow.",
    )
    parser.add_argument("--output", type=Path, default=Path("tot_report.json"))
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    settings = Settings(
        num_branches=args.branches,
        judges_per_branch=args.judges,
        max_concurrency=args.concurrency,
        request_timeout_seconds=args.request_timeout,
        workflow_timeout_seconds=args.workflow_timeout,
        output_path=args.output,
    )
    try:
        report = asyncio.run(run_strategy_engine_with_timeout(args.problem, settings))
        print_summary(report, settings.output_path)
    except TimeoutError:
        LOGGER.error(
            "Execution timed out. Increase --request-timeout or "
            "--workflow-timeout if the service is responding slowly."
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
