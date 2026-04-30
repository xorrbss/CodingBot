import json
import os
import subprocess
import sys
from pathlib import Path


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
