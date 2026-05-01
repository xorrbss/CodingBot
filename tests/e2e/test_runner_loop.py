"""runner loop e2e (S1/S2/S3) — Task 2 임시 fixture 검증부터."""
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
