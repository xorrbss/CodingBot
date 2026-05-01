"""tests/e2e/ 전용 fixture — fake_claude shim + scenario factory."""
import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest


FAKE_CLAUDE = Path(__file__).parent / "fake_claude.py"


@pytest.fixture
def fake_claude_shim(tmp_path, monkeypatch):
    """`claude` CLI를 fake_claude.py로 가리는 PATH shim 디렉터리.

    Returns:
        bin_dir (Path): shim이 위치한 디렉터리. shutil.which("claude")가 이 dir의
        파일을 가리키도록 fail-fast assert 한다.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    if sys.platform == "win32":
        shim = bin_dir / "claude.cmd"
        shim.write_text(
            f'@python "{FAKE_CLAUDE}" %*\n',
            encoding="utf-8",
        )
    else:
        shim = bin_dir / "claude"
        shim.write_text(
            f'#!/usr/bin/env python3\n'
            f'import runpy, sys\n'
            f'sys.argv[0] = "{FAKE_CLAUDE}"\n'
            f'runpy.run_path("{FAKE_CLAUDE}", run_name="__main__")\n',
            encoding="utf-8",
        )
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    which = shutil.which("claude")
    assert which is not None and Path(which).parent == bin_dir, (
        f"shim not at front of PATH: which={which}, bin_dir={bin_dir}"
    )
    return bin_dir


@pytest.fixture
def e2e_scenario(tmp_path, monkeypatch):
    """시나리오 dict → JSON 파일 → CODINGBOT_E2E_SCENARIO 설정.

    factory fixture: 테스트가 `e2e_scenario({...})` 처럼 호출.
    """
    def _set(scenario: dict) -> Path:
        scenario_path = tmp_path / "scenario.json"
        scenario_path.write_text(
            json.dumps(scenario, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setenv("CODINGBOT_E2E_SCENARIO", str(scenario_path))
        return scenario_path

    return _set
