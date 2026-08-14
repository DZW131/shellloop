"""Local single-user Studio server for observing and evolving a Harness."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from shellloop.agents import DefaultAgent
from shellloop.config import SANDBOX_IMAGE, RunConfig, serialize_config
from shellloop.environments import DockerEnvironment
from shellloop.evaluation import (
    EvaluationCase,
    evaluation_case_data,
    load_evaluation_cases,
    run_metrics,
    select_evaluation_cases,
    suite_comparison_data,
)
from shellloop.harness import HarnessSpec, effective_system_prompt, flow_data, load_harness, save_harness, spec_data
from shellloop.models import OllamaCloudModel, OpenAICompatibleModel
from shellloop.models.ollama_cloud import OllamaCloudError
from shellloop.models.openai_compatible import OpenAIModelError
from shellloop.models.text_actions import TextActionFormatError
from shellloop.proposals import HarnessProposal, generate_proposal, proposal_data
from shellloop.serialize import save_trajectory
from shellloop.sessions import create_session_workspace, temporary_session_workspace
from shellloop.tracing import safe_preview
from shellloop.versions import HarnessVersionStore, version_data

_STATIC_ROOT = (Path(__file__).parent / "studio_static").resolve()
_VERIFICATION_TIMEOUT = 120


class StudioRun:
    """Thread-safe event history for one local Studio execution."""

    def __init__(self) -> None:
        self.id = uuid4().hex
        self.events: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.running = True
        self.condition = threading.Condition()
        self._started = perf_counter()
        self.duration_ms: int | None = None

    def emit(self, event: dict[str, Any]) -> None:
        with self.condition:
            self.events.append(
                {
                    "sequence": len(self.events) + 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **event,
                }
            )
            self.condition.notify_all()

    def finish(self, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self.condition:
            self.result = result
            self.error = error
            self.running = False
            self.duration_ms = round((perf_counter() - self._started) * 1000)
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            return {
                "id": self.id,
                "running": self.running,
                "result": self.result,
                "error": self.error,
                "event_count": len(self.events),
                "metrics": run_metrics(self.result, self.events, self.duration_ms)
                if self.result is not None and self.duration_ms is not None
                else None,
            }


class ComparisonRun:
    """Thread-safe progress and result for a multi-case Harness comparison."""

    def __init__(self, proposal_id: str) -> None:
        self.id = uuid4().hex
        self.proposal_id = proposal_id
        self.events: list[dict[str, Any]] = []
        self.comparison: dict[str, Any] | None = None
        self.error: str | None = None
        self.running = True
        self.condition = threading.Condition()

    def emit(self, event: dict[str, Any]) -> None:
        with self.condition:
            self.events.append(
                {
                    "sequence": len(self.events) + 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **event,
                }
            )
            self.condition.notify_all()

    def finish(self, comparison: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self.condition:
            self.comparison = comparison
            self.error = error
            self.running = False
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            return {
                "id": self.id,
                "proposal_id": self.proposal_id,
                "running": self.running,
                "comparison": self.comparison,
                "error": self.error,
                "event_count": len(self.events),
            }


class _ScopedTrace:
    """Attach case and variant identity to safe Agent events."""

    def __init__(self, run: ComparisonRun, case: EvaluationCase, variant: str) -> None:
        self.run = run
        self.case = case
        self.variant = variant

    def emit(self, event: dict[str, Any]) -> None:
        self.run.emit({**event, "case_id": self.case.id, "case_title": self.case.title, "variant": self.variant})


class StudioService:
    """Own local-only Studio state; API keys exist only during one model call."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.harness_path = self.root / "harness.yaml"
        self.evaluation_path = self.root / "evaluations.yaml"
        self.version_store = HarnessVersionStore(self.root, self.harness_path)
        self.runs: dict[str, StudioRun] = {}
        self.proposals: dict[str, HarnessProposal] = {}
        self.comparisons: dict[str, ComparisonRun] = {}
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        active = self.version_store.ensure_current()
        return {
            "sandbox_available": DockerEnvironment.available(SANDBOX_IMAGE),
            "harness": spec_data(load_harness(self.harness_path)),
            "harness_flow": flow_data(load_harness(self.harness_path)),
            "active_version": version_data(active, True),
            "runtime_url": "/runtime.html",
            "evolution_url": "/evolution.html",
        }

    def evaluation_cases(self) -> list[dict[str, Any]]:
        return [evaluation_case_data(case) for case in load_evaluation_cases(self.evaluation_path)]

    def versions(self) -> list[dict[str, Any]]:
        return self.version_store.list()

    def start_run(self, values: dict[str, Any]) -> StudioRun:
        if not DockerEnvironment.available(SANDBOX_IMAGE):
            raise ValueError("Docker is unavailable. Studio is in preview-only mode.")
        task = _required_text(values, "task")
        model = _build_model(values)
        spec = load_harness(self.harness_path)
        run = StudioRun()
        with self._lock:
            self.runs[run.id] = run
        threading.Thread(target=self._run_agent, args=(run, task, model, spec), daemon=True).start()
        return run

    def create_proposal(self, values: dict[str, Any]) -> HarnessProposal:
        self.version_store.ensure_current()
        proposal = generate_proposal(
            _build_model(values), _required_text(values, "request"), load_harness(self.harness_path)
        )
        with self._lock:
            self.proposals[proposal.id] = proposal
        return proposal

    def verify_proposal(self, proposal_id: str) -> HarnessProposal:
        proposal = self._proposal(proposal_id)
        if not DockerEnvironment.available(SANDBOX_IMAGE):
            raise ValueError("Docker is unavailable. Candidate verification cannot run.")
        output_path = self.root / "artifacts" / "studio" / f"verify-{proposal.id}.traj.json"
        session = create_session_workspace(self.root, output_path)
        save_harness(session / "harness.yaml", proposal.candidate)
        result = DockerEnvironment(session, _VERIFICATION_TIMEOUT, SANDBOX_IMAGE).execute(
            {"command": "python -m pytest -q"}
        )
        proposal.verification_returncode = int(result["returncode"])
        proposal.verification_duration_ms = int(result["duration_ms"])
        return proposal

    def start_comparison(self, proposal_id: str, values: dict[str, Any]) -> ComparisonRun:
        """Run current and candidate Harnesses on a selected suite in the background."""
        proposal = self._proposal(proposal_id)
        if not DockerEnvironment.available(SANDBOX_IMAGE):
            raise ValueError("Docker is unavailable. Harness comparison cannot run.")
        cases = select_evaluation_cases(
            load_evaluation_cases(self.evaluation_path),
            values.get("evaluation_case_ids"),
            values.get("evaluation_task"),
        )
        model = _build_model(values)
        run = ComparisonRun(proposal.id)
        with self._lock:
            self.comparisons[run.id] = run
        threading.Thread(
            target=self._run_comparison,
            args=(run, proposal, model, cases),
            daemon=True,
        ).start()
        return run

    def create_restore_proposal(self, version_id: str) -> HarnessProposal:
        target = self.version_store.get(version_id)
        current = load_harness(self.harness_path)
        if target.spec == current:
            raise ValueError("selected Harness version is already active")
        proposal = HarnessProposal(
            summary=f"Restore Harness version {version_id[:8]}",
            current=current,
            candidate=target.spec,
            origin="restore",
            source_version_id=version_id,
        )
        with self._lock:
            self.proposals[proposal.id] = proposal
        return proposal

    def apply_proposal(self, proposal_id: str) -> HarnessProposal:
        proposal = self._proposal(proposal_id)
        if proposal.applied:
            raise ValueError("candidate Harness has already been applied")
        if not proposal.verified:
            raise ValueError("candidate tests must pass before user approval can apply it")
        if load_harness(self.harness_path) != proposal.current:
            raise ValueError("active Harness changed after this proposal was created; generate a new candidate")
        self.version_store.activate(
            proposal.candidate,
            proposal.origin,
            proposal.summary,
            proposal.source_version_id,
        )
        proposal.applied = True
        return proposal

    def _proposal(self, proposal_id: str) -> HarnessProposal:
        try:
            return self.proposals[proposal_id]
        except KeyError as error:
            raise ValueError("proposal not found") from error

    def _evaluate_case(
        self,
        model: Any,
        case: EvaluationCase,
        spec: HarnessSpec,
        trace_sink: Any,
    ) -> dict[str, Any]:
        with temporary_session_workspace(self.root) as session:
            environment = DockerEnvironment(session, spec.timeout, SANDBOX_IMAGE)
            agent = DefaultAgent(
                model,
                environment,
                spec.max_steps,
                trace_sink=trace_sink,
                system_prompt=effective_system_prompt(spec),
                verification_command=spec.verification_command if spec.verification_enabled else None,
                verification_retries=spec.verification_retries,
            )
            started = perf_counter()
            result = agent.run(case.task)
            task_check_returncode = None
            if case.check_command is not None:
                trace_sink.emit(
                    {
                        "event": "task_check_started",
                        "step": result["steps"],
                        "summary": "deterministic task check started",
                        "phase": "evaluation",
                    }
                )
                checked = environment.execute({"command": case.check_command})
                task_check_returncode = int(checked["returncode"])
                trace_sink.emit(
                    {
                        "event": "task_check_finished",
                        "step": result["steps"],
                        "summary": "deterministic task check completed",
                        "phase": "evaluation",
                        "returncode": task_check_returncode,
                        "duration_ms": checked["duration_ms"],
                        "output_preview": safe_preview(str(checked.get("output", ""))),
                    }
                )
            duration_ms = round((perf_counter() - started) * 1000)
            return run_metrics(result, agent.events, duration_ms, task_check_returncode)

    def _run_comparison(
        self,
        run: ComparisonRun,
        proposal: HarnessProposal,
        model: Any,
        cases: list[EvaluationCase],
    ) -> None:
        try:
            results = []
            for index, case in enumerate(cases, 1):
                run.emit(
                    {
                        "event": "evaluation_case_started",
                        "step": index,
                        "summary": case.title,
                        "phase": "evaluation",
                        "case_id": case.id,
                        "case_index": index,
                        "case_count": len(cases),
                    }
                )
                baseline = self._evaluate_case(model, case, proposal.current, _ScopedTrace(run, case, "baseline"))
                candidate = self._evaluate_case(model, case, proposal.candidate, _ScopedTrace(run, case, "candidate"))
                results.append({"case": case, "baseline": baseline, "candidate": candidate})
                run.emit(
                    {
                        "event": "evaluation_case_finished",
                        "step": index,
                        "summary": case.title,
                        "phase": "evaluation",
                        "case_id": case.id,
                        "baseline_success": baseline["success"],
                        "candidate_success": candidate["success"],
                    }
                )
            comparison = suite_comparison_data(results)
            proposal.comparison = comparison
            run.emit(
                {
                    "event": "comparison_finished",
                    "step": len(cases),
                    "summary": "evaluation suite completed",
                    "phase": "evaluation",
                    "conclusion": comparison["conclusion"],
                }
            )
            run.finish(comparison)
        except (OllamaCloudError, OpenAIModelError, TextActionFormatError, ValueError) as error:
            run.finish(error=str(error))
        except OSError:
            run.finish(error="Harness comparison stopped unexpectedly.")

    def _run_agent(self, run: StudioRun, task: str, model: Any, spec: HarnessSpec) -> None:
        output_path = self.root / "artifacts" / "studio" / "runs" / f"{run.id}.traj.json"
        try:
            session = create_session_workspace(self.root, output_path)
            run.emit(
                {
                    "event": "sandbox_prepared",
                    "step": 0,
                    "summary": "disposable Docker session prepared",
                    "phase": "sandbox",
                    "network": "disabled",
                    "image": SANDBOX_IMAGE,
                    "harness_flow": flow_data(spec),
                }
            )
            agent = DefaultAgent(
                model,
                DockerEnvironment(session, spec.timeout, SANDBOX_IMAGE),
                spec.max_steps,
                trace_sink=run,
                system_prompt=effective_system_prompt(spec),
                verification_command=spec.verification_command if spec.verification_enabled else None,
                verification_retries=spec.verification_retries,
            )
            result = agent.run(task)
            save_trajectory(
                output_path,
                messages=agent.messages,
                result=result,
                config=serialize_config(
                    RunConfig(
                        workspace=self.root,
                        max_steps=spec.max_steps,
                        timeout=spec.timeout,
                        model_provider=str(getattr(model, "_provider", "configured-api")),
                        model_name=str(getattr(model, "_model_name", "configured-model")),
                        api_base=str(getattr(model, "_api_base", "configured-api")),
                    )
                ),
                events=run.events,
            )
            run.finish(result=result)
        except (OllamaCloudError, OpenAIModelError, TextActionFormatError, ValueError) as error:
            run.emit({"event": "run_failed", "step": 0, "summary": "run stopped before completion"})
            run.finish(error=str(error))
        except OSError:
            run.emit(
                {
                    "event": "run_finished",
                    "step": 0,
                    "summary": "Studio run stopped unexpectedly",
                    "exit_status": "RunError",
                }
            )
            run.finish(error="Studio run failed. Inspect the safe event trace for progress.")


def serve(root: Path, port: int, open_browser: bool = True) -> None:
    """Serve the local-only Studio until the user stops the process."""
    server = _StudioHttpServer(("127.0.0.1", port), _StudioHandler, StudioService(root))
    url = f"http://127.0.0.1:{port}"
    if open_browser:
        webbrowser.open(url)
    print(f"Shellloop Studio listening at {url}")
    server.serve_forever()


class _StudioHttpServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], service: StudioService) -> None:
        super().__init__(address, handler)
        self.service = service


class _StudioHandler(BaseHTTPRequestHandler):
    server: _StudioHttpServer

    def do_GET(self) -> None:
        try:
            self._get()
        except (TypeError, ValueError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _get(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(HTTPStatus.OK, self.server.service.status())
            return
        if path == "/api/evaluation-cases":
            self._json(HTTPStatus.OK, {"cases": self.server.service.evaluation_cases()})
            return
        if path == "/api/versions":
            self._json(HTTPStatus.OK, {"versions": self.server.service.versions()})
            return
        if path.startswith("/api/comparisons/") and path.endswith("/events"):
            self._comparison_events(path.split("/")[3])
            return
        if path.startswith("/api/comparisons/"):
            self._comparison_snapshot(path.split("/")[3])
            return
        if path.startswith("/api/runs/") and path.endswith("/events"):
            self._events(path.split("/")[3])
            return
        if path.startswith("/api/runs/"):
            self._run_snapshot(path.split("/")[3])
            return
        self._static("index.html" if path == "/" else path.lstrip("/"))

    def do_POST(self) -> None:
        try:
            values = self._body()
            path = urlparse(self.path).path
            if path == "/api/runs":
                run = self.server.service.start_run(values)
                self._json(HTTPStatus.ACCEPTED, {"run_id": run.id})
                return
            if path == "/api/proposals":
                self._json(HTTPStatus.OK, proposal_data(self.server.service.create_proposal(values)))
                return
            if path.startswith("/api/proposals/") and path.endswith("/verify"):
                self._json(HTTPStatus.OK, proposal_data(self.server.service.verify_proposal(path.split("/")[3])))
                return
            if path.startswith("/api/proposals/") and path.endswith("/compare"):
                run = self.server.service.start_comparison(path.split("/")[3], values)
                self._json(HTTPStatus.ACCEPTED, {"comparison_id": run.id})
                return
            if path.startswith("/api/proposals/") and path.endswith("/apply"):
                self._json(HTTPStatus.OK, proposal_data(self.server.service.apply_proposal(path.split("/")[3])))
                return
            if path.startswith("/api/versions/") and path.endswith("/restore"):
                self._json(
                    HTTPStatus.OK,
                    proposal_data(self.server.service.create_restore_proposal(path.split("/")[3])),
                )
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
        except (TypeError, ValueError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except (OllamaCloudError, OpenAIModelError, TextActionFormatError) as error:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})

    def _run_snapshot(self, run_id: str) -> None:
        run = self.server.service.runs.get(run_id)
        if run is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "run not found"})
            return
        self._json(HTTPStatus.OK, run.snapshot())

    def _comparison_snapshot(self, comparison_id: str) -> None:
        run = self.server.service.comparisons.get(comparison_id)
        if run is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "comparison not found"})
            return
        self._json(HTTPStatus.OK, run.snapshot())

    def _comparison_events(self, comparison_id: str) -> None:
        run = self.server.service.comparisons.get(comparison_id)
        if run is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "comparison not found"})
            return
        self._stream_events(run)

    def _events(self, run_id: str) -> None:
        run = self.server.service.runs.get(run_id)
        if run is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "run not found"})
            return
        self._stream_events(run)

    def _stream_events(self, run: StudioRun | ComparisonRun) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        sent = 0
        try:
            while True:
                with run.condition:
                    if sent == len(run.events) and run.running:
                        run.condition.wait(timeout=15)
                    events = run.events[sent:]
                    done = not run.running
                for event in events:
                    self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    sent += 1
                if done and sent == len(run.events):
                    break
        except (BrokenPipeError, ConnectionResetError):
            return

    def _static(self, name: str) -> None:
        path = (_STATIC_ROOT / name).resolve()
        if _STATIC_ROOT not in path.parents or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 64_000:
            raise ValueError("request body must be between 1 and 64000 bytes")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise TypeError("request body must be a JSON object")
        return data

    def _json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _required_text(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _build_model(values: dict[str, Any]) -> OllamaCloudModel | OpenAICompatibleModel:
    provider = _required_text(values, "provider")
    model = _required_text(values, "model")
    api_base = _required_text(values, "api_base")
    api_key = _required_text(values, "api_key")
    if provider == "ollama-cloud":
        return OllamaCloudModel(api_base, model, api_key)
    if provider == "openai-compatible":
        return OpenAICompatibleModel(api_base, model, api_key)
    raise ValueError("provider must be ollama-cloud or openai-compatible")
