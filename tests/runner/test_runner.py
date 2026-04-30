import os
import subprocess as sp
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from codingbot import handoff, paths, runner, state


class FakeClaude:
    """subprocess.run 대체. 매 호출마다 정해진 동작 시뮬레이트."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []

    def __call__(self, args, **kwargs):
        if not self.scripts:
            raise AssertionError(f"unexpected extra call: {args}")
        action = self.scripts.pop(0)
        self.calls.append({"args": args, "action": action})
        if "writes_handoff" in action:
            handoff.write(action["writes_handoff"])
        return MagicMock(returncode=action.get("exit_code", 0))


def test_normal_flow_terminates_after_done_then_final_check(tmp_codingbot_home, monkeypatch):
    fake = FakeClaude([
        {"writes_handoff": "## 다음 작업: db.py"},
        {},
        {},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("리팩터링해줘")
    assert len(fake.calls) == 3
    assert fake.calls[0]["args"][1] == "리팩터링해줘"
    assert "db.py" in fake.calls[1]["args"][1]
    from codingbot.runner import FINAL_CHECK_PROMPT
    assert fake.calls[2]["args"][1] == FINAL_CHECK_PROMPT


def test_final_check_finds_new_work(tmp_codingbot_home, monkeypatch):
    fake = FakeClaude([
        {},
        {"writes_handoff": "## 추가 작업: 테스트"},
        {},
        {},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 4


def test_stop_signal_breaks_loop(tmp_codingbot_home, monkeypatch):
    def fake_with_stop(args, **kw):
        handoff.write("계속 작업")
        paths.stop_signal_file().touch()
        return MagicMock(returncode=0)
    monkeypatch.setattr(sp, "run", fake_with_stop)
    runner.run("초기")
    s = state.read()
    assert s["cycles_this_run"] == 1


def test_run_clears_old_stop_signal_at_start(tmp_codingbot_home, monkeypatch):
    paths.stop_signal_file().touch()
    fake = FakeClaude([
        {"writes_handoff": "x"},
        {},
        {},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) >= 1


def test_abnormal_exit_retries_once(tmp_codingbot_home, monkeypatch):
    fake = FakeClaude([
        {"exit_code": 1},
        {"writes_handoff": "ok"},
        {},
        {},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 4


def test_abnormal_exit_twice_breaks(tmp_codingbot_home, monkeypatch):
    fake = FakeClaude([
        {"exit_code": 1},
        {"exit_code": 1},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 2
    s = state.read()
    assert s["cycles_this_run"] == 2


def test_stale_lock_is_cleaned_up(tmp_codingbot_home, monkeypatch):
    paths.lock_file().write_text("999999", encoding="utf-8")
    monkeypatch.setattr(runner, "_is_pid_alive", lambda pid: False)
    fake = FakeClaude([{"writes_handoff": "x"}, {}, {}])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 3


def test_concurrent_run_rejected(tmp_codingbot_home, monkeypatch):
    paths.lock_file().write_text("12345", encoding="utf-8")
    monkeypatch.setattr(runner, "_is_pid_alive", lambda pid: True)
    fake = FakeClaude([])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 0
