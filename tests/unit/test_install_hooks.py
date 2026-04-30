import json
import sys
from codingbot import install_hooks


def test_install_creates_settings_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    install_hooks.install()
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "hooks" in data
    assert "PreToolUse" in data["hooks"]
    assert "Stop" in data["hooks"]
    pre = data["hooks"]["PreToolUse"]
    assert any("codingbot.hooks.auto_approve" in str(h) for h in _flatten(pre))
    stop = data["hooks"]["Stop"]
    assert any("codingbot.hooks.handoff_or_continue" in str(h) for h in _flatten(stop))


def test_install_preserves_existing_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    existing = {"theme": "dark", "model": "sonnet", "hooks": {"PreCompact": [{"a": 1}]}}
    settings_path.write_text(json.dumps(existing), encoding="utf-8")
    install_hooks.install()
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["model"] == "sonnet"
    assert "PreCompact" in data["hooks"]
    assert "PreToolUse" in data["hooks"]
    assert "Stop" in data["hooks"]


def test_install_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    install_hooks.install()
    install_hooks.install()
    settings_path = tmp_path / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    pre = data["hooks"]["PreToolUse"]
    matches = [h for h in _flatten(pre) if "codingbot.hooks.auto_approve" in str(h)]
    assert len(matches) == 1


def test_uninstall_removes_codingbot_hooks_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    install_hooks.install()
    install_hooks.uninstall()
    settings_path = tmp_path / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    pre_flat = _flatten(data.get("hooks", {}).get("PreToolUse", []))
    assert not any("codingbot" in str(h) for h in pre_flat)


def _flatten(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _flatten(v)
    else:
        yield obj
