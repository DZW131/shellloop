from pathlib import Path

from shellloop.config import build_run_config, load_config, serialize_config


def test_config_file_and_explicit_values_are_merged(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("workspace: .\nmax_steps: 3\ntimeout: 9\nconfirm: false\n", encoding="utf-8")

    config = build_run_config(load_config(path), max_steps=5)

    assert config.max_steps == 5
    assert config.timeout == 9
    assert config.confirm is False
    assert serialize_config(config)["workspace"] == str(Path.cwd())
