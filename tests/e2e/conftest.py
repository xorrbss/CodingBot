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


@pytest.fixture
def transcript_jsonl_factory(tmp_path):
    """dict 리스트를 Claude Code session schema JSONL로 변환해 임시 파일에 쓴다.

    입력 dict: {"role": "user"|"assistant", "text": str}
    출력 schema (한 줄당 한 entry):
        user      → {"type":"user",     "message":{"role":"user",     "content":[{"type":"text","text":...}]}}
        assistant → {"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":...}]}}
    """
    counter = {"n": 0}

    def _make(messages: list[dict]) -> Path:
        counter["n"] += 1
        path = tmp_path / f"transcript_{counter['n']}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for m in messages:
                role = m["role"]
                if role not in ("user", "assistant"):
                    raise ValueError(f"invalid role: {role!r}")
                entry = {
                    "type": role,
                    "message": {
                        "role": role,
                        "content": [{"type": "text", "text": m["text"]}],
                    },
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return path

    return _make


@pytest.fixture
def hook_env(tmp_codingbot_home):
    """hook subprocess용 env 빌더.

    기본: os.environ 사본 + CODINGBOT_HOME=tmp_codingbot_home + ANTHROPIC_API_KEY 더미.
    overrides는 추가/덮어쓰기.
    """
    import os as _os

    def _build(**overrides) -> dict:
        env = _os.environ.copy()
        env["CODINGBOT_HOME"] = str(tmp_codingbot_home)
        env.setdefault("ANTHROPIC_API_KEY", "fake-key-for-tests")
        # fault-inject env가 누설되어 다음 테스트에 영향 가지 않도록 기본은 제거
        env.pop("CODINGBOT_FAULT_INJECT", None)
        env.update({k: str(v) for k, v in overrides.items()})
        return env

    return _build
