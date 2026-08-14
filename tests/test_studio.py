import threading
import urllib.request
from pathlib import Path

import pytest

from shellloop.harness import HarnessSpec, load_harness
from shellloop.proposals import HarnessProposal
from shellloop.studio import StudioRun, StudioService, _StudioHandler, _StudioHttpServer


def test_studio_run_exposes_ordered_safe_events():
    run = StudioRun()
    run.emit({"event": "model_request", "step": 1, "summary": "waiting for model"})
    run.finish(result={"exit_status": "Submitted"})

    assert run.events[0]["sequence"] == 1
    assert run.snapshot()["result"] == {"exit_status": "Submitted"}


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
        assert "运行观测台" in urllib.request.urlopen(f"{base}/runtime.html").read().decode("utf-8")
        assert "演化工作台" in urllib.request.urlopen(f"{base}/evolution.html").read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
