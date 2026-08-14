import threading
import urllib.request
from pathlib import Path

import pytest

from shellloop.environments import DockerEnvironment
from shellloop.harness import HarnessSpec, load_harness
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
    assert (tmp_path / "artifacts" / "studio" / "harness-history" / f"{proposal.id}.yaml").is_file()


def test_studio_serves_local_runtime_and_evolution_pages(tmp_path: Path):
    server = _StudioHttpServer(("127.0.0.1", 0), _StudioHandler, StudioService(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        runtime = urllib.request.urlopen(f"{base}/runtime.html").read().decode("utf-8")
        evolution = urllib.request.urlopen(f"{base}/evolution.html").read().decode("utf-8")
        assert "事件检查器" in runtime
        assert "流程结构对比" in evolution
        assert "真实同任务 A/B 对比" in evolution
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
                {"success": False, "steps": 4, "failed_command_count": 2, "duration_ms": 5000},
                {"success": True, "steps": 2, "failed_command_count": 0, "duration_ms": 3000},
            ]

        def _evaluate_spec(self, model, task: str, spec: HarnessSpec) -> dict:
            return self.metrics.pop(0)

    monkeypatch.setattr(DockerEnvironment, "available", staticmethod(lambda: True))
    studio = ComparisonStudio(tmp_path)
    proposal = HarnessProposal("Better flow", HarnessSpec(), HarnessSpec(verification_retries=2))
    studio.proposals[proposal.id] = proposal

    studio.compare_proposal(
        proposal.id,
        {
            "provider": "ollama-cloud",
            "api_base": "https://ollama.com/api",
            "model": "test-model",
            "api_key": "test-key",
            "evaluation_task": "private evaluation task",
        },
    )

    assert proposal.comparison["conclusion"] == "candidate_succeeded_where_baseline_failed"
    assert "private evaluation task" not in str(proposal.comparison)
