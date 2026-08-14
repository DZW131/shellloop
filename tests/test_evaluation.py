from pathlib import Path

import pytest

from shellloop.evaluation import (
    EvaluationCase,
    comparison_data,
    load_evaluation_cases,
    run_metrics,
    select_evaluation_cases,
    suite_comparison_data,
)


def test_run_metrics_exposes_behavior_without_messages_or_task_content():
    metrics = run_metrics(
        {"exit_status": "Submitted", "steps": 2},
        [
            {"event": "model_response", "step": 1},
            {"event": "command_finished", "step": 1, "returncode": 1},
            {"event": "model_response", "step": 2},
            {"event": "command_finished", "step": 2, "returncode": 0},
            {"event": "verification_finished", "step": 2, "returncode": 0},
        ],
        1250,
    )

    assert metrics == {
        "exit_status": "Submitted",
        "completed": True,
        "success": True,
        "steps": 2,
        "model_calls": 2,
        "command_count": 2,
        "failed_command_count": 1,
        "verification_count": 1,
        "task_check_passed": None,
        "duration_ms": 1250,
    }
    assert "task" not in metrics
    assert "messages" not in metrics


def test_comparison_reports_deltas_and_keeps_single_run_caution():
    baseline = {
        "success": False,
        "steps": 4,
        "failed_command_count": 2,
        "duration_ms": 5000,
    }
    candidate = {
        "success": True,
        "steps": 3,
        "failed_command_count": 0,
        "duration_ms": 4000,
    }

    comparison = comparison_data(baseline, candidate)

    assert comparison["conclusion"] == "candidate_succeeded_where_baseline_failed"
    assert comparison["delta"] == {"steps": -1, "failed_command_count": -2, "duration_ms": -1000}
    assert "not proof" in comparison["caution"]


def test_task_checker_controls_evaluation_success():
    assert run_metrics({"exit_status": "Submitted", "steps": 1}, [], 10, 1)["success"] is False
    assert run_metrics({"exit_status": "Submitted", "steps": 1}, [], 10, 0)["task_check_passed"] is True


def test_evaluation_suite_is_validated_and_private_task_is_request_scoped(tmp_path: Path):
    path = tmp_path / "evaluations.yaml"
    path.write_text(
        "cases:\n  - id: exact\n    title: Exact\n    description: A checked case\n"
        "    task: Create result.txt\n    check_command: test -f result.txt\n",
        encoding="utf-8",
    )

    cases = load_evaluation_cases(path)
    selected = select_evaluation_cases(cases, ["exact"], "private task")

    assert [case.id for case in selected] == ["exact", "private"]
    assert selected[0].check_command == "test -f result.txt"
    with pytest.raises(ValueError, match="unknown"):
        select_evaluation_cases(cases, ["missing"])


def test_suite_comparison_aggregates_cases_without_tasks():
    case = EvaluationCase("checked", "Checked", "Description", "private task", "test -f result")
    comparison = suite_comparison_data(
        [
            {
                "case": case,
                "baseline": {
                    "success": False,
                    "steps": 3,
                    "failed_command_count": 1,
                    "verification_count": 1,
                    "task_check_passed": False,
                    "duration_ms": 300,
                },
                "candidate": {
                    "success": True,
                    "steps": 2,
                    "failed_command_count": 0,
                    "verification_count": 1,
                    "task_check_passed": True,
                    "duration_ms": 200,
                },
            }
        ]
    )

    assert comparison["conclusion"] == "candidate_improved_success_rate"
    assert comparison["candidate"]["success_rate"] == 1.0
    assert "private task" not in str(comparison)
