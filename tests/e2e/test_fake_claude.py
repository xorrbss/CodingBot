"""fake_claude.py 자체 단위 회귀 (PATH shim 없이 직접 호출)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e_auto


FAKE_CLAUDE = Path(__file__).parent / "fake_claude.py"


def _run_fake(scenario_path: Path | None, home: Path, env_extra: dict | None = None):
    env = os.environ.copy()
    env["CODINGBOT_HOME"] = str(home)
    if scenario_path is not None:
        env["CODINGBOT_E2E_SCENARIO"] = str(scenario_path)
    else:
        env.pop("CODINGBOT_E2E_SCENARIO", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(FAKE_CLAUDE), "test prompt"],
        env=env,
        capture_output=True,
        text=True,
    )


def test_fake_claude_step_writes_handoff_and_advances(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps({
            "name": "t1",
            "steps": [
                {"exit_code": 0, "handoff": "다음 작업: foo"},
                {"exit_code": 0, "handoff": None},
            ],
        }),
        encoding="utf-8",
    )

    r1 = _run_fake(scenario, home)
    assert r1.returncode == 0, r1.stderr
    assert (home / "handoff.md").read_text(encoding="utf-8") == "다음 작업: foo"
    assert (home / ".e2e_step").read_text(encoding="utf-8") == "1"

    # step 1: handoff is None — 기존 파일은 fake_claude가 지우지 않음 (runner가 clear)
    r2 = _run_fake(scenario, home)
    assert r2.returncode == 0, r2.stderr
    assert (home / ".e2e_step").read_text(encoding="utf-8") == "2"
    # step 0이 작성한 handoff.md가 그대로 보존됨 (fake_claude는 None 시 file 손대지 않음)
    assert (home / "handoff.md").read_text(encoding="utf-8") == "다음 작업: foo"


def test_fake_claude_out_of_range_exits_91(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps({"name": "t2", "steps": [{"exit_code": 0, "handoff": None}]}),
        encoding="utf-8",
    )

    # 첫 호출 정상
    assert _run_fake(scenario, home).returncode == 0
    # 두 번째 호출 — out of range
    r = _run_fake(scenario, home)
    assert r.returncode == 91
    assert "out of range" in r.stderr.lower()


def test_fake_claude_missing_env_exits_90(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    r = _run_fake(scenario_path=None, home=home)
    assert r.returncode == 90
    assert "codingbot_e2e_scenario" in r.stderr.lower()


def test_transcript_jsonl_factory_emits_session_schema(transcript_jsonl_factory):
    """factory가 Claude Code session schema로 emit한다 — iter_messages가 읽을 수 있어야 함."""
    from codingbot import transcript

    path = transcript_jsonl_factory([
        {"role": "user", "text": "hello"},
        {"role": "assistant", "text": "hi there"},
    ])
    msgs = list(transcript.iter_messages(path))
    assert msgs == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_hook_env_includes_codingbot_home(hook_env, tmp_codingbot_home):
    """hook_env가 CODINGBOT_HOME을 tmp_codingbot_home과 일치시킨다."""
    env = hook_env()
    assert env["CODINGBOT_HOME"] == str(tmp_codingbot_home)


def test_hook_env_overrides_apply(hook_env):
    env = hook_env(CODINGBOT_FAULT_INJECT="judge_timeout", FOO="bar")
    assert env["CODINGBOT_FAULT_INJECT"] == "judge_timeout"
    assert env["FOO"] == "bar"
