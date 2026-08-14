from pathlib import Path

import pytest

from shellloop.harness import HarnessSpec, load_harness, save_harness, update_harness


def test_default_harness_is_available_before_any_user_approval(tmp_path: Path):
    spec = load_harness(tmp_path / "harness.yaml")

    assert spec.max_steps == 8
    assert "Docker sandbox" in spec.system_prompt


def test_harness_accepts_only_bounded_fields_and_persists_without_credentials(tmp_path: Path):
    candidate = update_harness(HarnessSpec(), {"max_steps": 5, "timeout": 45})
    path = tmp_path / "harness.yaml"

    save_harness(path, candidate)

    assert load_harness(path) == candidate
    assert "api_key" not in path.read_text(encoding="utf-8")


def test_harness_rejects_arbitrary_agent_capabilities():
    with pytest.raises(ValueError, match="unsupported Harness field"):
        update_harness(HarnessSpec(), {"workspace": "/"})


@pytest.mark.parametrize(("changes",), [({"max_steps": 0},), ({"timeout": 121},), ({"system_prompt": "  "},)])
def test_harness_rejects_unsafe_bounds(changes: dict):
    with pytest.raises(ValueError):
        update_harness(HarnessSpec(), changes)
