"""tests/e2e/ 전용 fixture — codingbot.runner.subprocess.run 라우팅 + 시나리오 factory."""
import json
import subprocess as _stdlib_subprocess
import sys
from pathlib import Path

import pytest


FAKE_CLAUDE = Path(__file__).parent / "fake_claude.py"


@pytest.fixture
def fake_claude_shim(monkeypatch):
    """codingbot.runner의 subprocess.run을 fake_claude로 라우팅.

    Windows에서는 PATH 기반 .cmd shim이 시스템 claude.exe에 가려지므로 monkeypatch
    패턴이 필요하다. POSIX에서도 동일한 결정성을 위해 같은 방식을 사용.

    Returns: wrapper 함수 (디버깅 편의, 미사용 가능).
    """
    real_run = _stdlib_subprocess.run

    def _wrapper(args, *a, **kw):
        if (
            isinstance(args, (list, tuple))
            and args
            and args[0] == "claude"
        ):
            new_args = [sys.executable, str(FAKE_CLAUDE), *args[1:]]
            return real_run(new_args, *a, **kw)
        return real_run(args, *a, **kw)

    # codingbot.runner는 `import subprocess`로 참조 → `runner.subprocess.run` patch
    monkeypatch.setattr("codingbot.runner.subprocess.run", _wrapper)
    return _wrapper


@pytest.fixture
def e2e_scenario(tmp_path, monkeypatch):
    """시나리오 dict → JSON 파일 → CODINGBOT_E2E_SCENARIO 설정.

    factory fixture: 테스트가 `e2e_scenario({...})` 처럼 호출.
    동일 테스트 내 재호출 시 마지막 시나리오로 덮어쓴다 (last-write-wins).
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
