"""실제 Claude Code 사용 E2E 스모크 테스트.

실행:
    pytest tests/e2e/test_smoke.py -v -m e2e

전제 조건:
- claude CLI가 PATH에 있음
- ANTHROPIC_API_KEY 환경변수 설정
- codingbot install-hooks 실행됨
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e


def test_codingbot_runs_simple_task(tmp_path, monkeypatch):
    """간단한 토이 태스크가 다중 사이클로 진행되는지 검증."""
    if not shutil.which("claude"):
        pytest.skip("claude CLI not found")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    test_home = tmp_path / "codingbot_home"
    test_home.mkdir()
    monkeypatch.setenv("CODINGBOT_HOME", str(test_home))

    workdir = tmp_path / "toy_project"
    workdir.mkdir()
    (workdir / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8"
    )

    result = subprocess.run(
        ["codingbot", "run", "이 Flask 앱에 /health 엔드포인트 추가하고 print로 'health ok' 찍게 해줘"],
        cwd=workdir,
        timeout=600,
        capture_output=True,
        text=True,
    )

    log_path = test_home / "log.jsonl"
    assert log_path.exists(), "log file should exist"
    cycle_starts = [line for line in log_path.read_text(encoding="utf-8").splitlines() if "cycle_start" in line]
    assert len(cycle_starts) >= 1, "at least one cycle should have started"

    app_code = (workdir / "app.py").read_text(encoding="utf-8")
    assert "/health" in app_code
