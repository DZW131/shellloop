from pathlib import Path

from shellloop.sessions import create_session_workspace, temporary_session_workspace


def test_persistent_session_copies_source_without_runtime_artifacts(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "code.py").write_text("print('ok')", encoding="utf-8")
    (source / "artifacts").mkdir()
    (source / "artifacts" / "secret.txt").write_text("not copied", encoding="utf-8")

    session = create_session_workspace(source, tmp_path / "output" / "run.json")

    assert (session / "code.py").is_file()
    assert not (session / "artifacts").exists()


def test_private_evaluation_session_is_destroyed_after_use(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "code.py").write_text("print('ok')", encoding="utf-8")

    with temporary_session_workspace(source) as session:
        session_path = session
        (session / "evaluation-note.txt").write_text("private task output", encoding="utf-8")
        assert session.exists()

    assert not session_path.exists()
