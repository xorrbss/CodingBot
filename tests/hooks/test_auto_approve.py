import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_hook(input_dict, env_overrides=None):
    """hook 스크립트를 subprocess로 실행."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.auto_approve"],
        input=json.dumps(input_dict),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return result


def test_safe_tool_returns_approve(tmp_codingbot_home):
    r = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "approve"


def test_risky_tool_skips_auto_approval(tmp_codingbot_home):
    r = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_unknown_tool_calls_llm(tmp_codingbot_home):
    r = _run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": "x"}, "transcript_path": ""},
        env_overrides={
            "CODINGBOT_HOME": str(tmp_codingbot_home),
            "ANTHROPIC_API_KEY": "",
        },
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_stop_signal_skips_auto_approval(tmp_codingbot_home):
    (tmp_codingbot_home / ".codingbot-stop").touch()
    r = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_invalid_json_input_does_not_crash(tmp_codingbot_home):
    r = subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.auto_approve"],
        input="not json at all",
        capture_output=True,
        text=True,
        env={**os.environ, "CODINGBOT_HOME": str(tmp_codingbot_home)},
        timeout=60,
    )
    assert r.returncode == 0
