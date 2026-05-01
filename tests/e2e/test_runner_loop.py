"""runner loop e2e (S1/S2/S3) — Task 2 임시 fixture 검증부터."""
import os
import shutil
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e_auto


def test_shim_and_scenario_fixtures_wire_up(
    tmp_codingbot_home, fake_claude_shim, e2e_scenario, tmp_path
):
    # shim은 PATH 앞에 위치
    which = shutil.which("claude")
    assert which is not None
    assert Path(which).parent == fake_claude_shim, which

    # scenario fixture가 env를 설정
    scenario_path = e2e_scenario({"name": "smoke", "steps": [
        {"exit_code": 0, "handoff": None},
    ]})
    assert os.environ["CODINGBOT_E2E_SCENARIO"] == str(scenario_path)
    assert Path(scenario_path).exists()
