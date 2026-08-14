from pathlib import Path

import pytest

from shellloop.harness import (
    HarnessSpec,
    effective_system_prompt,
    flow_data,
    load_harness,
    save_harness,
    update_harness,
)


def test_default_harness_is_available_before_any_user_approval(tmp_path: Path):
    spec = load_harness(tmp_path / "harness.yaml")

    assert spec.max_steps == 8
    assert "Docker sandbox" in spec.system_prompt


def test_harness_accepts_only_bounded_fields_and_persists_without_credentials(tmp_path: Path):
    candidate = update_harness(
        HarnessSpec(),
        {
            "max_steps": 5,
            "timeout": 45,
            "visible_planning": False,
            "verification_command": "python -m pytest tests/test_agent.py -q",
            "verification_retries": 2,
        },
    )
    path = tmp_path / "harness.yaml"

    save_harness(path, candidate)

    assert load_harness(path) == candidate
    assert "api_key" not in path.read_text(encoding="utf-8")


def test_harness_flow_and_effective_prompt_reflect_structural_changes():
    candidate = update_harness(HarnessSpec(), {"visible_planning": False, "verification_enabled": False})

    assert [node["id"] for node in flow_data(candidate) if node["enabled"]] == [
        "understand",
        "act",
        "observe",
        "finish",
    ]
    assert "state a short visible plan" not in effective_system_prompt(candidate)
    assert "configured verification command" not in effective_system_prompt(candidate)


def test_harness_rejects_arbitrary_agent_capabilities():
    with pytest.raises(ValueError, match="unsupported Harness field"):
        update_harness(HarnessSpec(), {"workspace": "/"})


@pytest.mark.parametrize(
    ("changes",),
    [
        ({"max_steps": 0},),
        ({"timeout": 121},),
        ({"system_prompt": "  "},),
        ({"verification_command": "x\ny"},),
        ({"verification_retries": 4},),
    ],
)
def test_harness_rejects_unsafe_bounds(changes: dict):
    with pytest.raises(ValueError):
        update_harness(HarnessSpec(), changes)


def test_harness_rejects_string_booleans():
    with pytest.raises(TypeError, match="must be true or false"):
        update_harness(HarnessSpec(), {"visible_planning": "false"})
