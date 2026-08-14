import json

from shellloop.tracing import (
    CompositeTraceSink,
    ConsoleTraceSink,
    TraceRecorder,
    build_event,
)


def test_build_event_keeps_only_the_fixed_protocol_fields():
    event = build_event(
        "action_selected",
        2,
        "command selected",
        command="echo hello",
        returncode=0,
        task="SECRET_TASK",
        api_key="sk-fake-key-12345",
    )

    assert event == {
        "event": "action_selected",
        "step": 2,
        "summary": "command selected",
        "command": "echo hello",
        "returncode": 0,
    }
    assert "SECRET_TASK" not in json.dumps(event)
    assert "sk-fake-key" not in json.dumps(event)


def test_build_event_truncates_long_commands():
    event = build_event("action_selected", 1, "command selected", command="x" * 200)

    assert event["command"] == "x" * 160 + "..."
    assert len(event["command"]) == 163


def test_build_event_drops_none_fields():
    event = build_event("command_finished", 1, "command finished", returncode=None, finished=False)

    assert "returncode" not in event
    assert event["finished"] is False


def test_recorder_appends_events_in_order():
    recorder = TraceRecorder()
    recorder.emit({"event": "run_started", "step": 0, "summary": "task accepted"})
    recorder.emit({"event": "run_finished", "step": 1, "summary": "run finished", "exit_status": "Submitted"})

    assert [e["event"] for e in recorder.events] == ["run_started", "run_finished"]


def test_console_sink_prints_one_trace_line(capsys):
    ConsoleTraceSink().emit(
        {"event": "action_selected", "step": 1, "summary": "command selected", "command": "echo hello"}
    )
    ConsoleTraceSink().emit({"event": "run_started", "step": 0, "summary": "task accepted"})

    out = capsys.readouterr().out
    assert out.splitlines() == [
        "[trace] step 1 action_selected: command selected (command=echo hello)",
        "[trace] step 0 run_started: task accepted",
    ]


def test_composite_sink_forwards_to_every_child_in_order():
    first = TraceRecorder()
    second = TraceRecorder()
    composite = CompositeTraceSink(first, second)

    composite.emit({"event": "model_request", "step": 1, "summary": "waiting for model"})

    assert len(first.events) == 1
    assert len(second.events) == 1
    assert first.events == second.events
