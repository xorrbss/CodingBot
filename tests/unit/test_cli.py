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
