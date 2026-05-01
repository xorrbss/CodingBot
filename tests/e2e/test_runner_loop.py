"""runner loop e2e (S1/S2/S3) — Task 2 임시 fixture 검증부터."""
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e_auto


def test_route_and_scenario_fixtures_wire_up(
    tmp_codingbot_home, fake_claude_shim, e2e_scenario
):
    # monkeypatch가 codingbot.runner.subprocess.run을 라우팅하는지 확인
    e2e_scenario({"name": "smoke", "steps": [
        {"exit_code": 7, "handoff": None},
    ]})

    from codingbot.runner import subprocess as runner_subprocess
    r = runner_subprocess.run(["claude", "probe"], capture_output=True, text=True)
    assert r.returncode == 7, (r.returncode, r.stdout, r.stderr)
    # step counter 증가 확인
    assert (tmp_codingbot_home / ".e2e_step").read_text() == "1"


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
