import io
import json
import os
import subprocess
import sys
from pathlib import Path

from codingbot import state


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "transcripts"


def _run_hook(input_dict, env_overrides=None):
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.handoff_or_continue"],
        input=json.dumps(input_dict),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_stop_signal_exits_silently(tmp_codingbot_home):
    (tmp_codingbot_home / ".codingbot-stop").touch()
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_handoff_exists_exits_silently(tmp_codingbot_home):
    (tmp_codingbot_home / "handoff.md").write_text("some handoff", encoding="utf-8")
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_clearly_continuing_blocks_with_continue_msg(tmp_codingbot_home):
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert "계속" in out["reason"] or "이어" in out["reason"]


def test_clearly_done_requests_handoff(tmp_codingbot_home):
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_done.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert "handoff" in out["reason"].lower() or "핸드오프" in out["reason"]


def test_llm_failure_falls_back_to_silent(tmp_codingbot_home, tmp_path):
    ambiguous = tmp_path / "ambiguous.jsonl"
    ambiguous.write_text(
        '{"role": "assistant", "content": "음... 잠시만요"}\n',
        encoding="utf-8",
    )
    r = _run_hook(
        {"transcript_path": str(ambiguous)},
        env_overrides={
            "CODINGBOT_HOME": str(tmp_codingbot_home),
            "ANTHROPIC_API_KEY": "",
        },
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_invalid_input_does_not_crash(tmp_codingbot_home):
    r = subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.handoff_or_continue"],
        input="garbage",
        capture_output=True,
        text=True,
        env={**os.environ, "CODINGBOT_HOME": str(tmp_codingbot_home)},
        timeout=60,
    )
    assert r.returncode == 0


# --- 0.3.0 카운터 회귀 ---


def _read_state(home):
    sf = home / "state.json"
    if not sf.exists():
        return {}
    return json.loads(sf.read_text(encoding="utf-8"))


def test_counter_continuing_increments_block_continue(tmp_codingbot_home):
    state.start_cycle()
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["stop_block_continue"] == 1
    assert s["stop_block_handoff"] == 0
    assert s["auto_continue_count"] == 1  # 호환 카운터도 증가


def test_counter_done_increments_block_handoff(tmp_codingbot_home):
    state.start_cycle()
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_done.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["stop_block_handoff"] == 1
    assert s["stop_block_continue"] == 0


def test_counter_stop_signal_increments_allow(tmp_codingbot_home):
    state.start_cycle()
    (tmp_codingbot_home / ".codingbot-stop").touch()
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["stop_allow"] == 1


def test_counter_handoff_already_written_increments_allow(tmp_codingbot_home):
    state.start_cycle()
    (tmp_codingbot_home / "handoff.md").write_text("x", encoding="utf-8")
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    s = _read_state(tmp_codingbot_home)
    assert s["stop_allow"] == 1


def test_counter_llm_timeout_increments_timeout_and_allow(tmp_codingbot_home, tmp_path, mocker):
    """ambiguous transcript → llm_judge timeout → stop_allow + judge_timeout_total."""
    import anthropic

    state.start_cycle()
    ambiguous = tmp_path / "ambiguous.jsonl"
    # 새 schema (top-level type + message.content)로 작성
    ambiguous.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"음... 잠시만요"}]}}\n',
        encoding="utf-8",
    )
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

    from codingbot.hooks import handoff_or_continue as hc
    payload = json.dumps({"transcript_path": str(ambiguous)})

    # plan에 redirect_stdin이 있었으나 stdlib에 없음. Task 4와 동일 패턴 사용:
    mocker.patch.object(sys, "stdin", io.StringIO(payload))
    mocker.patch.object(sys, "stdout", io.StringIO())
    rc = hc.main()
    assert rc == 0

    s = _read_state(tmp_codingbot_home)
    assert s["judge_call_total"] == 1
    assert s["judge_timeout_total"] == 1
    assert s["judge_error_total"] == 0
    assert s["stop_allow"] == 1


def test_counter_unstuck_increments_block_unstuck(tmp_codingbot_home, tmp_path, mocker):
    """ambiguous transcript → llm_judge classify=blocked_unsure → stop_block_unstuck +1."""
    state.start_cycle()
    ambiguous = tmp_path / "ambiguous.jsonl"
    ambiguous.write_text(
        '{"type":"assistant","message":{"content":[{"type":"text","text":"음... 잠시만요"}]}}\n',
        encoding="utf-8",
    )
    mocker.patch.dict(os.environ, {
        "CODINGBOT_HOME": str(tmp_codingbot_home),
        "ANTHROPIC_API_KEY": "fake",
    })
    mock_client = mocker.MagicMock()
    msg = type("Msg", (), {"text": '{"category": "blocked_unsure", "reason": "stuck"}'})()
    mock_client.messages.create.return_value = type("R", (), {"content": [msg]})()
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    from codingbot import config
    config.load.cache_clear()

    from codingbot.hooks import handoff_or_continue as hc
    payload = json.dumps({"transcript_path": str(ambiguous)})
    mocker.patch.object(sys, "stdin", io.StringIO(payload))
    mocker.patch.object(sys, "stdout", io.StringIO())
    rc = hc.main()
    assert rc == 0

    s = _read_state(tmp_codingbot_home)
    assert s["judge_call_total"] == 1
    assert s["stop_block_unstuck"] == 1
    assert s["stop_block_continue"] == 0
    assert s["stop_block_handoff"] == 0
    assert s["stop_allow"] == 0
