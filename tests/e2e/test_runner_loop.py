"""runner loop e2e (S1/S2/S3)."""
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e_auto


def _read_log_events(home: Path) -> list[dict]:
    """log.jsonl 파싱 헬퍼."""
    log_path = home / "log.jsonl"
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_s1_happy_1_cycle(tmp_codingbot_home, fake_claude_shim, e2e_scenario):
    """초기 프롬프트 1회 처리 → final-check 1회 → 종료."""
    e2e_scenario({
        "name": "happy_1_cycle",
        "steps": [
            {"exit_code": 0, "handoff": None},
            {"exit_code": 0, "handoff": None},
        ],
    })

    from codingbot import state
    from codingbot.runner import run

    rc = run("test prompt")

    assert rc == 0
    assert state.read()["cycles_this_run"] == 2

    events = _read_log_events(tmp_codingbot_home)
    cycle_starts = [e for e in events if e.get("event") == "cycle_start"]
    assert len(cycle_starts) == 2
    run_ends = [e for e in events if e.get("event") == "run_end"]
    assert any(e.get("reason") == "final_check_returned_done" for e in run_ends)
    assert not (tmp_codingbot_home / "handoff.md").exists()


def test_s2_handoff_multi(tmp_codingbot_home, fake_claude_shim, e2e_scenario):
    """첫 사이클이 handoff 작성 → 다음 사이클이 처리 → final-check → 종료."""
    e2e_scenario({
        "name": "handoff_multi",
        "steps": [
            {"exit_code": 0, "handoff": "다음 작업: foo"},
            {"exit_code": 0, "handoff": None},
            {"exit_code": 0, "handoff": None},
        ],
    })

    from codingbot import state
    from codingbot.runner import run

    rc = run("initial prompt")

    assert rc == 0
    assert state.read()["cycles_this_run"] == 3

    events = _read_log_events(tmp_codingbot_home)
    cycle_starts = [e for e in events if e.get("event") == "cycle_start"]
    assert len(cycle_starts) == 3

    # iter#1 입력 = initial, iter#2 입력 = handoff content, iter#3 입력 = final-check
    assert "initial prompt" in cycle_starts[0]["msg_preview"]
    assert "다음 작업: foo" in cycle_starts[1]["msg_preview"]
    assert "지금 코드 상태를" in cycle_starts[2]["msg_preview"]

    run_ends = [e for e in events if e.get("event") == "run_end"]
    assert any(e.get("reason") == "final_check_returned_done" for e in run_ends)


def test_s3_abnormal_recover(tmp_codingbot_home, fake_claude_shim, e2e_scenario):
    """첫 사이클 비정상(exit 2) → continue → 다음 사이클 정상 → final-check → 종료."""
    e2e_scenario({
        "name": "abnormal_recover",
        "steps": [
            {"exit_code": 2, "handoff": None},
            {"exit_code": 0, "handoff": None},
            {"exit_code": 0, "handoff": None},
        ],
    })

    from codingbot import state
    from codingbot.runner import run

    rc = run("initial prompt")

    assert rc == 0
    assert state.read()["cycles_this_run"] == 3

    events = _read_log_events(tmp_codingbot_home)
    abnormal = [e for e in events if e.get("event") == "claude_abnormal_exit"]
    assert len(abnormal) == 1
    assert abnormal[0]["count"] == 1

    run_ends = [e for e in events if e.get("event") == "run_end"]
    assert any(e.get("reason") == "final_check_returned_done" for e in run_ends)
