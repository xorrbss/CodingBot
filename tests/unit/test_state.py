import time
from datetime import datetime, timedelta, timezone

import pytest

from codingbot import state, paths


def test_start_cycle_creates_state(tmp_codingbot_home):
    state.start_cycle()
    s = state.read()
    assert s["cycles_this_run"] == 0
    assert s["auto_approve_count"] == 0
    assert s["auto_continue_count"] == 0
    assert "cycle_started_at" in s


def test_record_cycle_increments(tmp_codingbot_home):
    state.start_cycle()
    state.record_cycle()
    state.record_cycle()
    s = state.read()
    assert s["cycles_this_run"] == 2


def test_record_auto_approve(tmp_codingbot_home):
    state.start_cycle()
    state.record_auto_approve()
    state.record_auto_approve()
    state.record_auto_approve()
    s = state.read()
    assert s["auto_approve_count"] == 3


def test_should_stop_false_initially(tmp_codingbot_home):
    state.start_cycle()
    assert state.should_stop() is False


def test_should_stop_true_when_stop_file_exists(tmp_codingbot_home):
    state.start_cycle()
    paths.stop_signal_file().touch()
    assert state.should_stop() is True


def test_should_stop_true_when_time_exceeded(tmp_codingbot_home):
    state.start_cycle()
    s = state.read()
    s["cycle_started_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=31)
    ).isoformat().replace("+00:00", "Z")
    state.write(s)
    assert state.should_stop() is True


def test_should_stop_true_when_cycle_limit_exceeded(tmp_codingbot_home):
    state.start_cycle()
    s = state.read()
    s["cycles_this_run"] = 50
    state.write(s)
    assert state.should_stop() is True


def test_corrupt_state_resets(tmp_codingbot_home):
    paths.state_file().write_text("not valid json", encoding="utf-8")
    s = state.read()
    assert s["cycles_this_run"] == 0


def test_clear_stop_signal(tmp_codingbot_home):
    paths.stop_signal_file().touch()
    assert paths.stop_signal_file().exists()
    state.clear_stop_signal()
    assert not paths.stop_signal_file().exists()


def test_clear_stop_signal_no_file_ok(tmp_codingbot_home):
    state.clear_stop_signal()  # no exception


# --- 0.3.0 신규 카운터 ---

NEW_COUNTER_KEYS = [
    "auto_approve_by_heuristic",
    "auto_approve_by_llm",
    "auto_defer_by_rule",
    "auto_defer_by_heuristic",
    "auto_defer_by_llm",
    "stop_block_continue",
    "stop_block_handoff",
    "stop_block_unstuck",
    "stop_allow",
    "judge_call_total",
    "judge_timeout_total",
    "judge_error_total",
]


def test_initial_state_includes_new_counters(tmp_codingbot_home):
    state.start_cycle()
    s = state.read()
    for key in NEW_COUNTER_KEYS:
        assert s.get(key) == 0, f"missing or non-zero: {key}"


def test_record_auto_approve_by_heuristic(tmp_codingbot_home):
    state.start_cycle()
    state.record_auto_approve_by("heuristic")
    state.record_auto_approve_by("heuristic")
    s = state.read()
    assert s["auto_approve_by_heuristic"] == 2
    assert s["auto_approve_by_llm"] == 0


def test_record_auto_approve_by_llm(tmp_codingbot_home):
    state.start_cycle()
    state.record_auto_approve_by("llm")
    s = state.read()
    assert s["auto_approve_by_llm"] == 1


def test_record_auto_approve_by_invalid_raises(tmp_codingbot_home):
    state.start_cycle()
    with pytest.raises(ValueError):
        state.record_auto_approve_by("rule")  # rule은 defer에만 유효


def test_record_auto_defer_by_each_source(tmp_codingbot_home):
    state.start_cycle()
    for src in ("rule", "heuristic", "llm"):
        state.record_auto_defer_by(src)
    s = state.read()
    assert s["auto_defer_by_rule"] == 1
    assert s["auto_defer_by_heuristic"] == 1
    assert s["auto_defer_by_llm"] == 1


def test_record_auto_defer_by_invalid_raises(tmp_codingbot_home):
    state.start_cycle()
    with pytest.raises(ValueError):
        state.record_auto_defer_by("unknown_src")


def test_record_stop_outcome_each_value(tmp_codingbot_home):
    state.start_cycle()
    for o in ("block_continue", "block_handoff", "block_unstuck", "allow"):
        state.record_stop_outcome(o)
    s = state.read()
    assert s["stop_block_continue"] == 1
    assert s["stop_block_handoff"] == 1
    assert s["stop_block_unstuck"] == 1
    assert s["stop_allow"] == 1


def test_record_stop_outcome_invalid_raises(tmp_codingbot_home):
    state.start_cycle()
    with pytest.raises(ValueError):
        state.record_stop_outcome("block_unknown")


def test_record_judge_call_increments(tmp_codingbot_home):
    state.start_cycle()
    state.record_judge_call()
    state.record_judge_call()
    state.record_judge_call()
    s = state.read()
    assert s["judge_call_total"] == 3


def test_record_judge_timeout_increments(tmp_codingbot_home):
    state.start_cycle()
    state.record_judge_timeout()
    s = state.read()
    assert s["judge_timeout_total"] == 1


def test_record_judge_error_increments(tmp_codingbot_home):
    state.start_cycle()
    state.record_judge_error()
    s = state.read()
    assert s["judge_error_total"] == 1
