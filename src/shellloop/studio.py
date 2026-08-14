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
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from shellloop.agents import DefaultAgent
from shellloop.config import RunConfig, serialize_config
from shellloop.environments import DockerEnvironment
from shellloop.harness import HarnessSpec, load_harness, save_harness, spec_data
from shellloop.models import OllamaCloudModel, OpenAICompatibleModel
from shellloop.models.ollama_cloud import OllamaCloudError
from shellloop.models.openai_compatible import OpenAIModelError
from shellloop.models.text_actions import TextActionFormatError
from shellloop.proposals import HarnessProposal, generate_proposal, proposal_data
from shellloop.serialize import save_trajectory
from shellloop.sessions import create_session_workspace

_STATIC_ROOT = (Path(__file__).parent / "studio_static").resolve()


class StudioRun:
    """Thread-safe event history for one local Studio execution."""

    def __init__(self) -> None:
        self.id = uuid4().hex
        self.events: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None
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

    def finish(self, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self.condition:
            self.result = result
            self.error = error
            self.running = False
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            return {
                "id": self.id,
                "running": self.running,
                "result": self.result,
                "error": self.error,
                "event_count": len(self.events),
            }


class StudioService:
    """Own local-only Studio state; API keys exist only during one model call."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.harness_path = self.root / "harness.yaml"
        self.runs: dict[str, StudioRun] = {}
        self.proposals: dict[str, HarnessProposal] = {}
        self._lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        return {
            "sandbox_available": DockerEnvironment.available(),
            "harness": spec_data(load_harness(self.harness_path)),
            "runtime_url": "/runtime.html",
            "evolution_url": "/evolution.html",
        }

    def start_run(self, values: dict[str, Any]) -> StudioRun:
        if not DockerEnvironment.available():
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
        proposal = generate_proposal(
            _build_model(values), _required_text(values, "request"), load_harness(self.harness_path)
        )
        with self._lock:
            self.proposals[proposal.id] = proposal
        return proposal

    def verify_proposal(self, proposal_id: str) -> HarnessProposal:
        proposal = self._proposal(proposal_id)
        if not DockerEnvironment.available():
            raise ValueError("Docker is unavailable. Candidate verification cannot run.")
        output_path = self.root / "artifacts" / "studio" / f"verify-{proposal.id}.traj.json"
        session = create_session_workspace(self.root, output_path)
        save_harness(session / "harness.yaml", proposal.candidate)
        result = DockerEnvironment(session, proposal.candidate.timeout, "shellloop-sandbox:0.3").execute(
            {"command": "python -m pytest -q"}
        )
        proposal.verification_returncode = int(result["returncode"])
        return proposal

    def apply_proposal(self, proposal_id: str) -> HarnessProposal:
        proposal = self._proposal(proposal_id)
        if not proposal.verified:
            raise ValueError("candidate tests must pass before user approval can apply it")
        history = self.root / "artifacts" / "studio" / "harness-history"
        history.mkdir(parents=True, exist_ok=True)
        save_harness(history / f"{proposal.id}.yaml", proposal.current)
        save_harness(self.harness_path, proposal.candidate)
        proposal.applied = True
        return proposal

    def _proposal(self, proposal_id: str) -> HarnessProposal:
        try:
            return self.proposals[proposal_id]
        except KeyError as error:
            raise ValueError("proposal not found") from error

    def _run_agent(self, run: StudioRun, task: str, model: Any, spec: HarnessSpec) -> None:
        output_path = self.root / "artifacts" / "studio" / "runs" / f"{run.id}.traj.json"
        try:
            session = create_session_workspace(self.root, output_path)
            run.emit({"event": "sandbox_prepared", "step": 0, "summary": "disposable Docker session prepared"})
            agent = DefaultAgent(
                model,
                DockerEnvironment(session, spec.timeout, "shellloop-sandbox:0.3"),
                spec.max_steps,
                trace_sink=run,
                system_prompt=spec.system_prompt,
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
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(HTTPStatus.OK, self.server.service.status())
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
            if path.startswith("/api/proposals/") and path.endswith("/apply"):
                self._json(HTTPStatus.OK, proposal_data(self.server.service.apply_proposal(path.split("/")[3])))
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
        except (TypeError, ValueError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def _run_snapshot(self, run_id: str) -> None:
        run = self.server.service.runs.get(run_id)
        if run is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "run not found"})
            return
        self._json(HTTPStatus.OK, run.snapshot())

    def _events(self, run_id: str) -> None:
        run = self.server.service.runs.get(run_id)
        if run is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "run not found"})
            return
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
