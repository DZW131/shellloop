"""Comparable, privacy-preserving metrics for Harness evaluation runs."""

from __future__ import annotations

from typing import Any


def run_metrics(result: dict[str, Any], events: list[dict[str, Any]], duration_ms: int) -> dict[str, Any]:
    """Reduce a run to evidence that can be displayed without raw task content."""
    command_events = [event for event in events if event["event"] == "command_finished"]
    return {
        "exit_status": result["exit_status"],
        "success": result["exit_status"] == "Submitted",
        "steps": int(result.get("steps", max((event.get("step", 0) for event in events), default=0))),
        "model_calls": sum(event["event"] == "model_response" for event in events),
        "command_count": len(command_events),
        "failed_command_count": sum(event.get("returncode") != 0 for event in command_events),
        "verification_count": sum(event["event"] == "verification_finished" for event in events),
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
