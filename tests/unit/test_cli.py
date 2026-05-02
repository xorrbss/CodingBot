import json
import subprocess
import sys
from codingbot import cli, paths


def test_stop_creates_signal_file(tmp_codingbot_home):
    cli.main(["stop"])
    assert paths.stop_signal_file().exists()


def test_start_removes_signal_file(tmp_codingbot_home):
    paths.stop_signal_file().touch()
    cli.main(["start"])
    assert not paths.stop_signal_file().exists()


def test_status_outputs_state(tmp_codingbot_home, capsys):
    rc = cli.main(["status"])
    out = capsys.readouterr().out
    assert "cycles" in out.lower() or "state" in out.lower()
    assert rc == 0


def test_tail_log_outputs_lines(tmp_codingbot_home, capsys):
    paths.log_file().write_text(
        '{"event":"a"}\n{"event":"b"}\n{"event":"c"}\n', encoding="utf-8"
    )
    cli.main(["tail-log", "-n", "2"])
    out = capsys.readouterr().out
    assert '"event":"b"' in out or '"event": "b"' in out
    assert '"event":"c"' in out or '"event": "c"' in out
    assert '"event":"a"' not in out and '"event": "a"' not in out


def test_run_calls_runner(tmp_codingbot_home, mocker):
    spy = mocker.patch("codingbot.runner.run", return_value=0)
    cli.main(["run", "어떤 작업"])
    spy.assert_called_once_with("어떤 작업")


def test_run_propagates_runner_exit_code(tmp_codingbot_home, mocker):
    """M-5: runner가 비정상 종료 코드 반환 시 CLI도 그대로 전파."""
    mocker.patch("codingbot.runner.run", return_value=1)
    rc = cli.main(["run", "어떤 작업"])
    assert rc == 1


def test_install_hooks_calls_install(tmp_codingbot_home, mocker):
    spy = mocker.patch("codingbot.install_hooks.install")
    cli.main(["install-hooks"])
    spy.assert_called_once()


def test_uninstall_hooks_calls_uninstall(tmp_codingbot_home, mocker):
    spy = mocker.patch("codingbot.install_hooks.uninstall")
    cli.main(["uninstall-hooks"])
    spy.assert_called_once()


def test_no_args_prints_help(tmp_codingbot_home, capsys):
    rc = cli.main([])
    out = capsys.readouterr().out
    assert "usage" in out.lower()
    assert rc != 0


def test_config_outputs_yaml_keys(tmp_codingbot_home, capsys):
    cli.main(["config"])
    out = capsys.readouterr().out
    assert "time_limit_minutes" in out
    assert "judge_model" in out


def test_status_includes_new_sections(tmp_codingbot_home, capsys):
    from codingbot import state
    state.start_cycle()
    cli.main(["status"])
    out = capsys.readouterr().out
    assert "=== Cycle ===" in out
    assert "=== Decisions (PreToolUse) ===" in out
    assert "=== Decisions (Stop) ===" in out
    assert "=== Judge ===" in out
    assert "=== Config ===" in out


def test_status_includes_new_counter_keys(tmp_codingbot_home, capsys):
    from codingbot import state
    state.start_cycle()
    cli.main(["status"])
    out = capsys.readouterr().out
    for key in (
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
    ):
        assert key in out, f"status output missing key: {key}"


# 0.6.0 — `status --watch` (S 사이클)

def test_read_log_tail_returns_last_n(tmp_codingbot_home):
    paths.log_file().write_text(
        '{"event":"a"}\n{"event":"b"}\n{"event":"c"}\n'
        '{"event":"d"}\n{"event":"e"}\n',
        encoding="utf-8",
    )
    tail = cli._read_log_tail(2)
    assert tail == ['{"event":"d"}', '{"event":"e"}']


def test_read_log_tail_no_log_returns_empty(tmp_codingbot_home):
    # log_file()가 없을 때 빈 리스트 (예외 없음)
    assert not paths.log_file().exists()
    assert cli._read_log_tail(5) == []


def test_status_watch_runs_one_iteration_then_exits_on_interrupt(
    tmp_codingbot_home, capsys, mocker
):
    """time.sleep을 KeyboardInterrupt로 patch → watch 루프 1회 실행 후 정상 종료(rc 0).

    화면 clear 부수효과를 막기 위해 os.system도 no-op patch.
    출력에는 watch 헤더 + 기존 status 본문 + Last log 섹션이 포함돼야 한다.
    """
    paths.log_file().write_text(
        '{"event":"x"}\n{"event":"y"}\n', encoding="utf-8"
    )
    mocker.patch("codingbot.cli.os.system", return_value=0)
    mocker.patch("codingbot.cli.time.sleep", side_effect=KeyboardInterrupt)

    rc = cli.main(["status", "--watch", "--interval", "1", "--tail", "3"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "refresh 1s" in out
    assert "=== Cycle ===" in out
    assert "=== Last log ===" in out
    assert '{"event":"y"}' in out


def test_status_watch_default_interval_and_tail(tmp_codingbot_home, capsys, mocker):
    """--interval / --tail 미지정 시 기본값 (1초, 10줄) 적용 + 헤더 출력."""
    mocker.patch("codingbot.cli.os.system", return_value=0)
    mocker.patch("codingbot.cli.time.sleep", side_effect=KeyboardInterrupt)

    rc = cli.main(["status", "--watch"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "refresh 1s" in out


def test_read_lock_pid_returns_int(tmp_codingbot_home):
    paths.lock_file().write_text("12345", encoding="utf-8")
    assert cli._read_lock_pid() == 12345


def test_read_lock_pid_none_when_absent(tmp_codingbot_home):
    assert not paths.lock_file().exists()
    assert cli._read_lock_pid() is None


def test_read_lock_pid_none_when_garbage(tmp_codingbot_home):
    paths.lock_file().write_text("not-a-pid", encoding="utf-8")
    assert cli._read_lock_pid() is None


def test_status_watch_header_shows_lock_pid_when_present(
    tmp_codingbot_home, capsys, mocker
):
    """lock 파일에 PID가 있으면 watch 헤더에 `lock pid=<n>` 표시."""
    paths.lock_file().write_text("9876", encoding="utf-8")
    mocker.patch("codingbot.cli.os.system", return_value=0)
    mocker.patch("codingbot.cli.time.sleep", side_effect=KeyboardInterrupt)

    rc = cli.main(["status", "--watch"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "lock pid=9876" in out


def test_status_watch_header_shows_lock_none_when_absent(
    tmp_codingbot_home, capsys, mocker
):
    """lock 파일 부재 시 watch 헤더에 `lock none` 표시."""
    assert not paths.lock_file().exists()
    mocker.patch("codingbot.cli.os.system", return_value=0)
    mocker.patch("codingbot.cli.time.sleep", side_effect=KeyboardInterrupt)

    rc = cli.main(["status", "--watch"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "lock none" in out


# 0.7.0 — `serve` (W 사이클)

def test_serve_subparser_invokes_run_serve_with_defaults(tmp_codingbot_home, mocker):
    """`codingbot serve`가 host=127.0.0.1, port=8723, open_browser=True로 run_serve 호출."""
    spy = mocker.patch("codingbot.serve.run_serve", return_value=0)
    rc = cli.main(["serve"])
    assert rc == 0
    spy.assert_called_once_with("127.0.0.1", 8723, True)


def test_serve_subparser_overrides(tmp_codingbot_home, mocker):
    spy = mocker.patch("codingbot.serve.run_serve", return_value=0)
    rc = cli.main(["serve", "--host", "0.0.0.0", "--port", "9000", "--no-browser"])
    assert rc == 0
    spy.assert_called_once_with("0.0.0.0", 9000, False)
