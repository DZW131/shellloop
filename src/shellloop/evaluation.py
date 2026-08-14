"""Comparable, privacy-preserving metrics for Harness evaluation runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_CASE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    title: str
    description: str
    task: str
    check_command: str | None = None


def run_metrics(
    result: dict[str, Any],
    events: list[dict[str, Any]],
    duration_ms: int,
    task_check_returncode: int | None = None,
) -> dict[str, Any]:
    """Reduce a run to evidence that can be displayed without raw task content."""
    command_events = [event for event in events if event["event"] == "command_finished"]
    completed = result["exit_status"] == "Submitted"
    return {
        "exit_status": result["exit_status"],
        "completed": completed,
        "success": completed and task_check_returncode in (None, 0),
        "steps": int(result.get("steps", max((event.get("step", 0) for event in events), default=0))),
        "model_calls": sum(event["event"] == "model_response" for event in events),
        "command_count": len(command_events),
        "failed_command_count": sum(event.get("returncode") != 0 for event in command_events),
        "verification_count": sum(event["event"] == "verification_finished" for event in events),
        "task_check_passed": None if task_check_returncode is None else task_check_returncode == 0,
        "duration_ms": duration_ms,
    }


def comparison_data(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Describe evidence deltas without claiming that one stochastic run is proof."""
    if candidate["success"] and not baseline["success"]:
        conclusion = "candidate_succeeded_where_baseline_failed"
    elif baseline["success"] and not candidate["success"]:
        conclusion = "candidate_regressed"
    elif candidate["success"] and candidate["failed_command_count"] < baseline["failed_command_count"]:
        conclusion = "candidate_used_fewer_failed_commands"
    elif candidate["success"] and candidate["steps"] < baseline["steps"]:
        conclusion = "candidate_used_fewer_steps"
    else:
        conclusion = "inconclusive_single_run"
    return {
        "baseline": baseline,
        "candidate": candidate,
        "delta": {
            "steps": candidate["steps"] - baseline["steps"],
            "failed_command_count": candidate["failed_command_count"] - baseline["failed_command_count"],
            "duration_ms": candidate["duration_ms"] - baseline["duration_ms"],
        },
        "conclusion": conclusion,
        "caution": "One stochastic comparison is evidence, not proof. Repeat important evaluations.",
    }


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    """Load a bounded, versionable evaluation suite without executing it."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {"cases": []}
    values = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise ValueError("evaluation suite must contain between 1 and 8 cases")
    cases = [_evaluation_case(value) for value in values]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("evaluation case ids must be unique")
    return cases


def select_evaluation_cases(
    available: list[EvaluationCase], case_ids: Any, private_task: Any = None
) -> list[EvaluationCase]:
    """Select public cases and optionally add one request-scoped private task."""
    if case_ids is None:
        case_ids = []
    if not isinstance(case_ids, list) or any(not isinstance(case_id, str) for case_id in case_ids):
        raise TypeError("evaluation_case_ids must be a list of strings")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("evaluation case ids must not repeat")
    by_id = {case.id: case for case in available}
    try:
        selected = [by_id[case_id] for case_id in case_ids]
    except KeyError as error:
        raise ValueError(f"unknown evaluation case: {error.args[0]}") from error
    if private_task is not None and private_task != "":
        if not isinstance(private_task, str) or not private_task.strip() or len(private_task) > 4000:
            raise ValueError("private evaluation task must contain 1 to 4000 characters")
        selected.append(
            EvaluationCase(
                "private", "Private task", "Request-scoped task without a saved checker", private_task.strip()
            )
        )
    if not 1 <= len(selected) <= 6:
        raise ValueError("select between 1 and 6 evaluation cases")
    return selected


def evaluation_case_data(case: EvaluationCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "has_check": case.check_command is not None,
    }


def suite_comparison_data(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate repeated case evidence without retaining tasks or raw outputs."""
    cases = [
        {
            "id": result["case"].id,
            "title": result["case"].title,
            "baseline": result["baseline"],
            "candidate": result["candidate"],
            "conclusion": comparison_data(result["baseline"], result["candidate"])["conclusion"],
        }
        for result in results
    ]
    baseline = _aggregate([case["baseline"] for case in cases])
    candidate = _aggregate([case["candidate"] for case in cases])
    score = "verified_success_count" if baseline["checked_case_count"] else "success_count"
    if candidate[score] > baseline[score]:
        conclusion = "candidate_improved_success_rate"
    elif candidate[score] < baseline[score]:
        conclusion = "candidate_regressed_success_rate"
    elif candidate["failed_command_count"] < baseline["failed_command_count"]:
        conclusion = "candidate_used_fewer_failed_commands"
    elif candidate["steps"] < baseline["steps"]:
        conclusion = "candidate_used_fewer_steps"
    else:
        conclusion = "inconclusive_suite"
    return {
        "case_count": len(cases),
        "baseline": baseline,
        "candidate": candidate,
        "cases": cases,
        "score_basis": "deterministic_checks" if baseline["checked_case_count"] else "completion_only",
        "conclusion": conclusion,
        "caution": "A small stochastic suite is evidence, not proof. Repeat important evaluations.",
    }


def _evaluation_case(value: Any) -> EvaluationCase:
    if not isinstance(value, dict):
        raise TypeError("each evaluation case must be a mapping")
    case = EvaluationCase(
        id=str(value.get("id", "")),
        title=str(value.get("title", "")),
        description=str(value.get("description", "")),
        task=str(value.get("task", "")),
        check_command=str(value["check_command"]) if value.get("check_command") is not None else None,
    )
    if _CASE_ID.fullmatch(case.id) is None:
        raise ValueError("evaluation case id must use lowercase letters, digits, underscores, or hyphens")
    if not case.title.strip() or len(case.title) > 100:
        raise ValueError("evaluation case title must contain 1 to 100 characters")
    if not case.description.strip() or len(case.description) > 300:
        raise ValueError("evaluation case description must contain 1 to 300 characters")
    if not case.task.strip() or len(case.task) > 4000:
        raise ValueError("evaluation case task must contain 1 to 4000 characters")
    if case.check_command is not None and (
        not case.check_command.strip()
        or len(case.check_command) > 500
        or "\n" in case.check_command
        or "\r" in case.check_command
    ):
        raise ValueError("evaluation check_command must be one line of 1 to 500 characters")
    return case


def _aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(metrics)
    return {
        "completed_count": sum(metric.get("completed", metric.get("exit_status") == "Submitted") for metric in metrics),
        "success_count": sum(metric["success"] for metric in metrics),
        "success_rate": round(sum(metric["success"] for metric in metrics) / count, 3),
        "checked_case_count": sum(metric.get("task_check_passed") is not None for metric in metrics),
        "verified_success_count": sum(
            metric["success"] and metric.get("task_check_passed") is True for metric in metrics
        ),
        "steps": sum(metric["steps"] for metric in metrics),
        "failed_command_count": sum(metric["failed_command_count"] for metric in metrics),
        "verification_count": sum(metric.get("verification_count", 0) for metric in metrics),
        "task_check_passed_count": sum(metric.get("task_check_passed") is True for metric in metrics),
        "duration_ms": sum(metric["duration_ms"] for metric in metrics),
    }
