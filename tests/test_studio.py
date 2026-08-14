import json
import threading
import urllib.request
from pathlib import Path

import pytest

from shellloop.environments import DockerEnvironment
from shellloop.harness import HarnessSpec, load_harness, save_harness
from shellloop.proposals import HarnessProposal
from shellloop.studio import StudioRun, StudioService, _StudioHandler, _StudioHttpServer


def test_studio_run_exposes_ordered_safe_events():
    run = StudioRun()
    run.emit({"event": "model_request", "step": 1, "summary": "waiting for model"})
    run.finish(result={"exit_status": "Submitted"})

    assert run.events[0]["sequence"] == 1
    assert run.snapshot()["result"] == {"exit_status": "Submitted"}
    assert run.snapshot()["metrics"]["model_calls"] == 0


def test_only_a_verified_proposal_can_change_the_active_harness(tmp_path: Path):
    studio = StudioService(tmp_path)
    proposal = HarnessProposal("Shorter loop", HarnessSpec(), HarnessSpec(max_steps=4))
    studio.proposals[proposal.id] = proposal

    with pytest.raises(ValueError, match="tests must pass"):
        studio.apply_proposal(proposal.id)

    proposal.verification_returncode = 0
    studio.apply_proposal(proposal.id)

    assert proposal.applied is True
    assert load_harness(tmp_path / "harness.yaml").max_steps == 4
    versions = studio.versions()
    assert len(versions) == 2
    assert versions[0]["active"] is True
    assert versions[0]["source"] == "natural-language"


def test_studio_serves_local_runtime_and_evolution_pages(tmp_path: Path):
    (tmp_path / "evaluations.yaml").write_text(
        "cases:\n  - id: checked\n    title: Checked\n    description: Public description\n"
        "    task: task text must remain server-side\n    check_command: test -f result.txt\n",
        encoding="utf-8",
    )
    server = _StudioHttpServer(("127.0.0.1", 0), _StudioHandler, StudioService(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        runtime = urllib.request.urlopen(f"{base}/runtime.html").read().decode("utf-8")
        evolution = urllib.request.urlopen(f"{base}/evolution.html").read().decode("utf-8")
        assert "事件检查器" in runtime
        assert "流程结构对比" in evolution
        assert "真实多任务 A/B 评测" in evolution
        assert "Harness 版本时间线" in evolution
        cases = json.load(urllib.request.urlopen(f"{base}/api/evaluation-cases"))["cases"]
        versions = json.load(urllib.request.urlopen(f"{base}/api/versions"))["versions"]
        assert cases == [{"id": "checked", "title": "Checked", "description": "Public description", "has_check": True}]
        assert "task text must remain server-side" not in str(cases)
        assert versions[0]["active"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_studio_compares_baseline_and_candidate_without_retaining_the_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class ComparisonStudio(StudioService):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.metrics = [
                {
                    "completed": False,
                    "success": False,
                    "steps": 4,
                    "failed_command_count": 2,
                    "task_check_passed": False,
                    "duration_ms": 5000,
                },
                {
                    "completed": True,
                    "success": True,
                    "steps": 2,
                    "failed_command_count": 0,
                    "task_check_passed": True,
                    "duration_ms": 3000,
                },
            ]

        def _evaluate_case(self, model, case, spec: HarnessSpec, trace_sink) -> dict:
            return self.metrics.pop(0)

    (tmp_path / "evaluations.yaml").write_text(
        "cases:\n  - id: checked\n    title: Checked\n    description: Deterministic check\n"
        "    task: private evaluation task\n    check_command: test -f result.txt\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(DockerEnvironment, "available", staticmethod(lambda image=None: True))
    studio = ComparisonStudio(tmp_path)
    proposal = HarnessProposal("Better flow", HarnessSpec(), HarnessSpec(verification_retries=2))
    studio.proposals[proposal.id] = proposal

    run = studio.start_comparison(
        proposal.id,
        {
            "provider": "ollama-cloud",
            "api_base": "https://ollama.com/api",
            "model": "test-model",
            "api_key": "test-key",
            "evaluation_case_ids": ["checked"],
        },
    )
    with run.condition:
        run.condition.wait_for(lambda: not run.running, timeout=2)

    assert proposal.comparison["conclusion"] == "candidate_improved_success_rate"
    assert "private evaluation task" not in str(proposal.comparison)
    assert [event["event"] for event in run.events] == [
        "evaluation_case_started",
        "evaluation_case_finished",
        "comparison_finished",
    ]
    assert run.snapshot()["comparison"] == proposal.comparison


def test_restore_is_a_new_candidate_that_must_pass_the_gate(tmp_path: Path):
    studio = StudioService(tmp_path)
    initial = studio.version_store.ensure_current()
    studio.version_store.activate(HarnessSpec(max_steps=4), "test", "Use four steps")

    proposal = studio.create_restore_proposal(initial.id)

    assert proposal.origin == "restore"
    assert proposal.source_version_id == initial.id
    with pytest.raises(ValueError, match="tests must pass"):
        studio.apply_proposal(proposal.id)
    proposal.verification_returncode = 0
    studio.apply_proposal(proposal.id)
    assert load_harness(tmp_path / "harness.yaml") == HarnessSpec()
    assert studio.versions()[0]["restored_from"] == initial.id


def test_stale_proposal_cannot_overwrite_a_newer_active_harness(tmp_path: Path):
    studio = StudioService(tmp_path)
    proposal = HarnessProposal("Old candidate", HarnessSpec(), HarnessSpec(max_steps=4))
    proposal.verification_returncode = 0
    studio.proposals[proposal.id] = proposal
    save_harness(tmp_path / "harness.yaml", HarnessSpec(max_steps=6))

    with pytest.raises(ValueError, match="active Harness changed"):
        studio.apply_proposal(proposal.id)

    assert load_harness(tmp_path / "harness.yaml").max_steps == 6
