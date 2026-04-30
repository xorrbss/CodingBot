import time
from datetime import datetime, timedelta, timezone
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
