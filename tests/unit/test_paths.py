import os
from pathlib import Path
from codingbot import paths


def test_codingbot_home_uses_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("CODINGBOT_HOME", str(tmp_path))
    assert paths.codingbot_home() == tmp_path


def test_codingbot_home_defaults_to_home_dir(monkeypatch):
    monkeypatch.delenv("CODINGBOT_HOME", raising=False)
    expected = Path.home() / ".codingbot"
    assert paths.codingbot_home() == expected


def test_specific_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("CODINGBOT_HOME", str(tmp_path))
    assert paths.config_file() == tmp_path / "config.yaml"
    assert paths.state_file() == tmp_path / "state.json"
    assert paths.handoff_file() == tmp_path / "handoff.md"
    assert paths.log_file() == tmp_path / "log.jsonl"
    assert paths.stop_signal_file() == tmp_path / ".codingbot-stop"
    assert paths.lock_file() == tmp_path / ".runner.lock"


def test_ensure_home_creates_directory(tmp_path, monkeypatch):
    home = tmp_path / "subdir"
    monkeypatch.setenv("CODINGBOT_HOME", str(home))
    assert not home.exists()
    paths.ensure_home()
    assert home.exists()
    assert home.is_dir()
