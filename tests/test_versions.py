from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from shellloop.harness import HarnessSpec, load_harness, save_harness
from shellloop.versions import HarnessVersionStore


def test_version_store_records_activation_and_detects_external_edits(tmp_path: Path):
    harness_path = tmp_path / "harness.yaml"
    save_harness(harness_path, HarnessSpec())
    store = HarnessVersionStore(tmp_path, harness_path)

    initial = store.ensure_current()
    applied = store.activate(HarnessSpec(max_steps=4), "proposal", "Use a shorter loop")
    save_harness(harness_path, HarnessSpec(max_steps=6))
    external = store.ensure_current()

    assert applied.parent_id == initial.id
    assert external.parent_id == applied.id
    assert external.source == "external"
    assert [version["id"] for version in store.list()] == [external.id, applied.id, initial.id]
    assert sum(version["active"] for version in store.list()) == 1


def test_version_store_can_reactivate_an_old_spec_without_exposing_credentials(tmp_path: Path):
    harness_path = tmp_path / "harness.yaml"
    store = HarnessVersionStore(tmp_path, harness_path)
    initial = store.ensure_current()
    store.activate(HarnessSpec(max_steps=3), "proposal", "Short experiment")

    restored = store.activate(store.get(initial.id).spec, "restore", "Restore initial Harness", initial.id)

    assert load_harness(harness_path) == HarnessSpec()
    assert restored.source == "restore"
    assert restored.restored_from == initial.id
    assert "api_key" not in str(store.list())
    with pytest.raises(ValueError, match="invalid"):
        store.get("../harness.yaml")


def test_concurrent_readers_create_only_one_initial_version(tmp_path: Path):
    store = HarnessVersionStore(tmp_path, tmp_path / "harness.yaml")

    with ThreadPoolExecutor(max_workers=8) as executor:
        versions = list(executor.map(lambda _: store.ensure_current(), range(16)))

    assert len({version.id for version in versions}) == 1
    assert len(store.list()) == 1
