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


# --- 0.3.0 카운터 회귀 ---

from codingbot import state


def _read_state(home):
    """hook subprocess가 쓴 state.json을 직접 읽어 검증."""
    sf = home / "state.json"
    if not sf.exists():
        return {}
    return json.loads(sf.read_text(encoding="utf-8"))


def test_counter_safe_tool_increments_heuristic(tmp_codingbot_home):
    state.start_cycle()  # 카운터 0으로 초기화
    r = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["auto_approve_by_heuristic"] == 1
    assert s["auto_approve_by_llm"] == 0
    assert s["auto_approve_count"] == 1  # 호환 카운터도 증가


def test_counter_risky_tool_increments_defer_heuristic(tmp_codingbot_home):
    state.start_cycle()
    r = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["auto_defer_by_heuristic"] == 1
    assert s["auto_defer_by_llm"] == 0
    assert s["auto_defer_by_rule"] == 0


def test_counter_stop_signal_increments_defer_rule(tmp_codingbot_home):
    state.start_cycle()
    (tmp_codingbot_home / ".codingbot-stop").touch()
    r = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["auto_defer_by_rule"] == 1


def _make_anthropic_response(text: str):
    """SDK 응답 형태를 흉내내는 객체."""
    msg = type("Msg", (), {"text": text})()
    return type("R", (), {"content": [msg]})()


def test_counter_llm_approve_increments_call_and_approve(tmp_codingbot_home, mocker):
    """llm 호출 → approve. judge_call_total + auto_approve_by_llm 모두 +1."""
    state.start_cycle()
    # subprocess 안에서 patch가 적용되도록 monkey patch는 못 씀.
    # 대신 hook 모듈 main()을 직접 import해 호출 (subprocess 우회).
    import io

    mocker.patch.dict(os.environ, {
        "CODINGBOT_HOME": str(tmp_codingbot_home),
        "ANTHROPIC_API_KEY": "fake",
    })
    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = _make_anthropic_response(
        '{"decision": "approve", "reason": "ok"}'
    )
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    from codingbot import config
    config.load.cache_clear()

    from codingbot.hooks import auto_approve as ap
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "x"},
        "transcript_path": "",
    })
    mocker.patch.object(sys, "stdin", io.StringIO(payload))
    mocker.patch.object(sys, "stdout", io.StringIO())
    rc = ap.main()
    assert rc == 0

    s = _read_state(tmp_codingbot_home)
    assert s["judge_call_total"] == 1
    assert s["auto_approve_by_llm"] == 1
    assert s["judge_timeout_total"] == 0
    assert s["judge_error_total"] == 0


def test_counter_llm_timeout_increments_call_timeout_defer(tmp_codingbot_home, mocker):
    """llm 호출 → timeout. judge_call_total + judge_timeout_total + auto_defer_by_llm 모두 +1."""
    import io
    import anthropic

    state.start_cycle()
    mocker.patch.dict(os.environ, {
        "CODINGBOT_HOME": str(tmp_codingbot_home),
        "ANTHROPIC_API_KEY": "fake",
    })
    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = anthropic.APITimeoutError(
        request=type("R", (), {})()
    )
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    from codingbot import config
    config.load.cache_clear()

    from codingbot.hooks import auto_approve as ap
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "x"},
        "transcript_path": "",
    })
    mocker.patch.object(sys, "stdin", io.StringIO(payload))
    mocker.patch.object(sys, "stdout", io.StringIO())
    rc = ap.main()
    assert rc == 0

    s = _read_state(tmp_codingbot_home)
    assert s["judge_call_total"] == 1
    assert s["judge_timeout_total"] == 1
    assert s["judge_error_total"] == 0
    assert s["auto_defer_by_llm"] == 1


def test_counter_llm_error_increments_call_error_defer(tmp_codingbot_home, mocker):
    """llm 호출 → 일반 에러. judge_call_total + judge_error_total + auto_defer_by_llm 모두 +1 (timeout은 0)."""
    import io

    state.start_cycle()
    mocker.patch.dict(os.environ, {
        "CODINGBOT_HOME": str(tmp_codingbot_home),
        "ANTHROPIC_API_KEY": "fake",
    })
    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("network fail")
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    from codingbot import config
    config.load.cache_clear()

    from codingbot.hooks import auto_approve as ap
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "x"},
        "transcript_path": "",
    })
    mocker.patch.object(sys, "stdin", io.StringIO(payload))
    mocker.patch.object(sys, "stdout", io.StringIO())
    rc = ap.main()
    assert rc == 0

    s = _read_state(tmp_codingbot_home)
    assert s["judge_call_total"] == 1
    assert s["judge_timeout_total"] == 0
    assert s["judge_error_total"] == 1
    assert s["auto_defer_by_llm"] == 1
