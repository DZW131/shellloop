"""Auditable, reversible Harness configuration versions."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from shellloop.harness import HarnessSpec, load_harness, save_harness, update_harness

_VERSION_ID = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True)
class HarnessVersion:
    id: str
    created_at: str
    source: str
    summary: str
    parent_id: str | None
    restored_from: str | None
    spec: HarnessSpec


class HarnessVersionStore:
    """Keep Harness revisions outside source control without storing credentials."""

    def __init__(self, root: Path, harness_path: Path) -> None:
        self.directory = root.resolve() / "artifacts" / "studio" / "harness-versions"
        self.harness_path = harness_path.resolve()
        self._lock = threading.RLock()

    def ensure_current(self) -> HarnessVersion:
        with self._lock:
            spec = load_harness(self.harness_path)
            active = self._active_version()
            if active is not None and active.spec == spec:
                return active
            return self._record(spec, "initial" if active is None else "external", "Current Harness discovered", active)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            active = self.ensure_current()
            versions = [self._read(path) for path in self.directory.glob("*.json")]
            return [
                version_data(version, version.id == active.id)
                for version in sorted(versions, key=lambda item: item.created_at, reverse=True)
            ]

    def get(self, version_id: str) -> HarnessVersion:
        with self._lock:
            if _VERSION_ID.fullmatch(version_id) is None:
                raise ValueError("invalid Harness version id")
            path = self.directory / f"{version_id}.json"
            if not path.is_file():
                raise ValueError("Harness version not found")
            return self._read(path)

    def activate(
        self,
        spec: HarnessSpec,
        source: str,
        summary: str,
        restored_from: str | None = None,
    ) -> HarnessVersion:
        with self._lock:
            parent = self.ensure_current()
            save_harness(self.harness_path, spec)
            return self._record(spec, source, summary, parent, restored_from)

    def _record(
        self,
        spec: HarnessSpec,
        source: str,
        summary: str,
        parent: HarnessVersion | None,
        restored_from: str | None = None,
    ) -> HarnessVersion:
        self.directory.mkdir(parents=True, exist_ok=True)
        version = HarnessVersion(
            id=uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            source=source,
            summary=summary,
            parent_id=parent.id if parent is not None else None,
            restored_from=restored_from,
            spec=spec,
        )
        (self.directory / f"{version.id}.json").write_text(
            json.dumps(_stored_data(version), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.directory / "active").write_text(version.id, encoding="utf-8")
        return version

    def _active_version(self) -> HarnessVersion | None:
        pointer = self.directory / "active"
        if not pointer.is_file():
            return None
        try:
            return self.get(pointer.read_text(encoding="utf-8").strip())
        except ValueError:
            return None

    @staticmethod
    def _read(path: Path) -> HarnessVersion:
        data = json.loads(path.read_text(encoding="utf-8"))
        return HarnessVersion(
            id=str(data["id"]),
            created_at=str(data["created_at"]),
            source=str(data["source"]),
            summary=str(data["summary"]),
            parent_id=str(data["parent_id"]) if data.get("parent_id") else None,
            restored_from=str(data["restored_from"]) if data.get("restored_from") else None,
            spec=update_harness(HarnessSpec(), data["spec"]),
        )


def version_data(version: HarnessVersion, active: bool = False) -> dict[str, Any]:
    return {
        "id": version.id,
        "created_at": version.created_at,
        "source": version.source,
        "summary": version.summary,
        "parent_id": version.parent_id,
        "restored_from": version.restored_from,
        "fingerprint": _fingerprint(version.spec),
        "spec": asdict(version.spec),
        "active": active,
    }


def _stored_data(version: HarnessVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "created_at": version.created_at,
        "source": version.source,
        "summary": version.summary,
        "parent_id": version.parent_id,
        "restored_from": version.restored_from,
        "spec": asdict(version.spec),
    }


def _fingerprint(spec: HarnessSpec) -> str:
    return hashlib.sha256(json.dumps(asdict(spec), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
