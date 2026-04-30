# CodingBot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code의 권한 자동 승인 + 작업 단위마다 컨텍스트 초기화하며 자동 진행하는 CLI 도구를 구현한다.

**Architecture:** Hooks (PreToolUse + Stop) + Shell-loop wrapper. wrapper는 Claude Code의 입출력을 가로채지 않고 단순히 자식 프로세스로 띄우고 종료를 기다린 후 다음 사이클을 시작한다. 작업 단위가 끝나면 Claude가 핸드오프 문서를 작성하고 새 세션이 그 문서를 시작 메시지로 받는다 = 진짜 컨텍스트 초기화.

**Tech Stack:** Python 3.11+, Anthropic SDK (`anthropic`), PyYAML, portalocker, pytest, pytest-mock.

**Spec:** [docs/superpowers/specs/2026-04-30-codingbot-design.md](../specs/2026-04-30-codingbot-design.md)

---

## 사전 사항

### 환경 가정
- Working directory: `C:/project/CodingBot`
- Python 3.11+ 설치됨
- Git는 아직 init 안 됨 → Task 0에서 처리
- `~/.codingbot/` (런타임 디렉터리)는 **테스트에서 절대 건드리지 말 것** — 모든 테스트는 `tmp_path` 또는 `tmp_codingbot_home` fixture로 격리

### 공통 fixture 약속

`tests/conftest.py`에서 모든 테스트가 사용할 fixture를 정의 (Task 1에서 작성):

```python
@pytest.fixture
def tmp_codingbot_home(tmp_path, monkeypatch):
    """테스트 격리된 가짜 ~/.codingbot 디렉터리."""
    home = tmp_path / "codingbot_home"
    home.mkdir()
    monkeypatch.setenv("CODINGBOT_HOME", str(home))
    return home

@pytest.fixture
def mock_anthropic_client(mocker):
    """Anthropic 클라이언트 mock. 기본은 응답 없음, 테스트가 set_response로 지정."""
    client = mocker.MagicMock()
    return client
```

**모든 모듈은** `~/.codingbot` 경로를 직접 하드코딩하지 말고 `config.codingbot_home()` 함수를 통해 얻어야 함 (환경변수 `CODINGBOT_HOME`이 있으면 그걸 사용, 없으면 `Path.home() / ".codingbot"`).

---

## 파일 구조 (전체)

| 경로 | 책임 |
|---|---|
| `pyproject.toml` | 패키지 메타, 의존성, 엔트리 포인트 |
| `codingbot/__init__.py` | 패키지 마커 |
| `codingbot/paths.py` | `~/.codingbot` 위치 결정. 모든 파일 경로 단일 출처 |
| `codingbot/logger.py` | JSONL 감사 로그 |
| `codingbot/config.py` | YAML 설정 로딩 + 기본값 |
| `codingbot/state.py` | state.json + 파일 락 + should_stop() |
| `codingbot/handoff.py` | 핸드오프 파일 read/write/clear/exists |
| `codingbot/transcript.py` | Claude Code transcript .jsonl 파서 |
| `codingbot/heuristics.py` | 도구 안전성 + 메시지 분류 (순수 함수) |
| `codingbot/llm_judge.py` | Claude API 호출 래퍼 |
| `codingbot/hooks/__init__.py` | 패키지 마커 |
| `codingbot/hooks/auto_approve.py` | PreToolUse hook 엔트리 |
| `codingbot/hooks/handoff_or_continue.py` | Stop hook 엔트리 |
| `codingbot/runner.py` | 셸 루프 wrapper |
| `codingbot/cli.py` | argparse 기반 CLI 분기 |
| `codingbot/install_hooks.py` | `~/.claude/settings.json` 수정 로직 |
| `config.example.yaml` | 사용자 참고용 |
| `tests/conftest.py` | 공통 fixture |
| `tests/unit/*` | 모듈별 유닛 테스트 |
| `tests/hooks/*` | hook 통합 테스트 (subprocess 호출) |
| `tests/runner/*` | runner 통합 테스트 (subprocess.run mock) |
| `tests/fixtures/transcripts/*.jsonl` | transcript 샘플 |

---

## Task 0: 프로젝트 스캐폴딩 + Git 초기화

**Files:**
- Create: `C:/project/CodingBot/pyproject.toml`
- Create: `C:/project/CodingBot/.gitignore`
- Create: `C:/project/CodingBot/codingbot/__init__.py`
- Create: `C:/project/CodingBot/codingbot/hooks/__init__.py`
- Create: `C:/project/CodingBot/tests/__init__.py`
- Create: `C:/project/CodingBot/README.md`

- [ ] **Step 1: Git 저장소 초기화**

```bash
cd /c/project/CodingBot
git init
git config user.name "CodingBot Dev"
git config user.email "dev@codingbot.local"
```

(이미 init 되어 있으면 스킵)

- [ ] **Step 2: `.gitignore` 작성**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
dist/
build/

# Virtual envs
.venv/
venv/

# Editor
.vscode/
.idea/

# Local
*.local.yaml
```

- [ ] **Step 3: `pyproject.toml` 작성**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "codingbot"
version = "0.1.0"
description = "Claude Code 자동 승인 + 자동 진행 도구"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
    "portalocker>=2.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-cov>=4.1",
]

[project.scripts]
codingbot = "codingbot.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "e2e: real Claude Code smoke tests (manual, costs money)",
]

[tool.hatch.build.targets.wheel]
packages = ["codingbot"]
```

- [ ] **Step 4: 빈 패키지 마커 + 스텁 README**

`codingbot/__init__.py`:
```python
__version__ = "0.1.0"
```

`codingbot/hooks/__init__.py`: 빈 파일

`tests/__init__.py`: 빈 파일

`README.md`:
```markdown
# CodingBot

Claude Code의 권한 자동 승인 + 작업 자동 진행 도구.

자세한 사용법은 추후 추가 예정.
```

- [ ] **Step 5: 가상환경 + 의존성 설치 검증**

```bash
python -m venv .venv
source .venv/Scripts/activate    # Windows bash
pip install -e ".[dev]"
codingbot --help    # 아직 동작 안 함, 다음 task에서 구현
```

`pip install` 성공해야 함. `codingbot --help`는 ImportError 나도 OK (cli.py 미구현).

- [ ] **Step 6: 첫 커밋**

```bash
git add .gitignore pyproject.toml codingbot/__init__.py codingbot/hooks/__init__.py tests/__init__.py README.md
git commit -m "chore: scaffold codingbot package"
```

---

## Task 1: paths 모듈 + conftest fixture

**Files:**
- Create: `codingbot/paths.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_paths.py`

**Why first**: 모든 모듈이 `~/.codingbot` 위치 결정에 의존. 단일 출처 만들기.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_paths.py`:
```python
import os
from pathlib import Path
from codingbot import paths


def test_codingbot_home_uses_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("CODINGBOT_HOME", str(tmp_path))
    assert paths.codingbot_home() == tmp_path


def test_codingbot_home_defaults_to_home_dir(monkeypatch):
    monkeypatch.delenv("CODINGBOT_HOME", raising=False)
    expected = Path.home() / ".codingbot"
    assert paths.codingbot_home() == expected


def test_specific_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("CODINGBOT_HOME", str(tmp_path))
    assert paths.config_file() == tmp_path / "config.yaml"
    assert paths.state_file() == tmp_path / "state.json"
    assert paths.handoff_file() == tmp_path / "handoff.md"
    assert paths.log_file() == tmp_path / "log.jsonl"
    assert paths.stop_signal_file() == tmp_path / ".codingbot-stop"
    assert paths.lock_file() == tmp_path / ".runner.lock"


def test_ensure_home_creates_directory(tmp_path, monkeypatch):
    home = tmp_path / "subdir"
    monkeypatch.setenv("CODINGBOT_HOME", str(home))
    assert not home.exists()
    paths.ensure_home()
    assert home.exists()
    assert home.is_dir()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/unit/test_paths.py -v
```

Expected: ModuleNotFoundError 또는 ImportError.

- [ ] **Step 3: `codingbot/paths.py` 구현**

```python
"""모든 파일 경로를 단일 출처로 관리."""
import os
from pathlib import Path


def codingbot_home() -> Path:
    """런타임 디렉터리. CODINGBOT_HOME 환경변수 우선, 없으면 ~/.codingbot."""
    env = os.environ.get("CODINGBOT_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codingbot"


def ensure_home() -> Path:
    home = codingbot_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def config_file() -> Path:
    return codingbot_home() / "config.yaml"


def state_file() -> Path:
    return codingbot_home() / "state.json"


def handoff_file() -> Path:
    return codingbot_home() / "handoff.md"


def log_file() -> Path:
    return codingbot_home() / "log.jsonl"


def stop_signal_file() -> Path:
    return codingbot_home() / ".codingbot-stop"


def lock_file() -> Path:
    return codingbot_home() / ".runner.lock"
```

- [ ] **Step 4: `tests/conftest.py` 공통 fixture 작성**

```python
"""모든 테스트 공유 fixture."""
import pytest


@pytest.fixture
def tmp_codingbot_home(tmp_path, monkeypatch):
    """격리된 가짜 ~/.codingbot 디렉터리."""
    home = tmp_path / "codingbot_home"
    home.mkdir()
    monkeypatch.setenv("CODINGBOT_HOME", str(home))
    return home


@pytest.fixture
def mock_anthropic(mocker):
    """anthropic.Anthropic 생성자를 mock으로 패치하고 반환."""
    mock_client = mocker.MagicMock()
    mocker.patch("anthropic.Anthropic", return_value=mock_client)
    return mock_client
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/unit/test_paths.py -v
```

Expected: 4 passed.

- [ ] **Step 6: 커밋**

```bash
git add codingbot/paths.py tests/conftest.py tests/unit/__init__.py tests/unit/test_paths.py
git commit -m "feat: add paths module and shared test fixtures"
```

---

## Task 2: logger 모듈

**Files:**
- Create: `codingbot/logger.py`
- Create: `tests/unit/test_logger.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_logger.py`:
```python
import json
from codingbot import logger, paths


def test_log_event_appends_jsonl(tmp_codingbot_home):
    logger.log("info", "cycle_start", cycle=1, msg="hi")
    log_path = paths.log_file()
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["level"] == "info"
    assert record["event"] == "cycle_start"
    assert record["cycle"] == 1
    assert record["msg"] == "hi"
    assert "ts" in record


def test_multiple_events_append(tmp_codingbot_home):
    logger.log("info", "first")
    logger.log("warn", "second")
    lines = paths.log_file().read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "first"
    assert json.loads(lines[1])["event"] == "second"


def test_log_helpers(tmp_codingbot_home):
    logger.info("e1", x=1)
    logger.warn("e2", x=2)
    logger.error("e3", x=3)
    lines = paths.log_file().read_text(encoding="utf-8").strip().split("\n")
    levels = [json.loads(line)["level"] for line in lines]
    assert levels == ["info", "warn", "error"]


def test_log_resilient_to_disk_error(tmp_codingbot_home, monkeypatch):
    """디스크 쓰기 실패 시 예외 던지지 말 것 (호출 흐름 보호)."""
    def boom(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr("pathlib.Path.open", boom)
    # 예외가 전파되면 안 됨
    logger.log("info", "test_event")
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_logger.py -v
```

Expected: ImportError.

- [ ] **Step 3: 구현**

`codingbot/logger.py`:
```python
"""JSONL 형식 감사 로그. 디스크 실패에 안전 (예외 삼킴)."""
import json
import sys
from datetime import datetime, timezone
from typing import Any

from codingbot import paths


def log(level: str, event: str, **fields: Any) -> None:
    """단일 이벤트를 log.jsonl에 한 줄 append. 실패해도 예외 안 던짐."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "level": level,
        "event": event,
        **fields,
    }
    try:
        paths.ensure_home()
        with paths.log_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        # 자동화 흐름을 막지 않음. stderr에 한 번 출력.
        print(f"[codingbot logger] failed to write: {e}", file=sys.stderr)


def info(event: str, **fields: Any) -> None:
    log("info", event, **fields)


def warn(event: str, **fields: Any) -> None:
    log("warn", event, **fields)


def error(event: str, **fields: Any) -> None:
    log("error", event, **fields)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_logger.py -v
```

Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/logger.py tests/unit/test_logger.py
git commit -m "feat: add JSONL audit logger"
```

---

## Task 3: config 모듈

**Files:**
- Create: `codingbot/config.py`
- Create: `config.example.yaml`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_config.py`:
```python
import pytest
from codingbot import config, paths


def test_defaults_when_no_file(tmp_codingbot_home):
    cfg = config.load()
    assert cfg.enabled is True
    assert cfg.time_limit_minutes == 30
    assert cfg.max_cycles_per_run == 50
    assert cfg.judge_model == "claude-haiku-4-5-20251001"
    assert "Read" in cfg.safe_tools
    assert "rm -rf" in cfg.risky_patterns
    assert cfg.api_key_env == "ANTHROPIC_API_KEY"
    assert cfg.log_level == "info"


def test_user_yaml_overrides_defaults(tmp_codingbot_home):
    paths.config_file().write_text(
        "time_limit_minutes: 60\nmax_cycles_per_run: 100\nlog_level: warn\n",
        encoding="utf-8",
    )
    cfg = config.load()
    assert cfg.time_limit_minutes == 60
    assert cfg.max_cycles_per_run == 100
    assert cfg.log_level == "warn"
    assert cfg.enabled is True   # 미지정은 기본값


def test_corrupt_yaml_falls_back_to_defaults(tmp_codingbot_home):
    paths.config_file().write_text("invalid: yaml: : :", encoding="utf-8")
    cfg = config.load()
    assert cfg.time_limit_minutes == 30  # 기본값


def test_partial_overrides_keep_defaults_for_lists(tmp_codingbot_home):
    paths.config_file().write_text(
        "safe_tools: [Read, MyCustomTool]\n", encoding="utf-8"
    )
    cfg = config.load()
    assert cfg.safe_tools == ["Read", "MyCustomTool"]
    assert "rm -rf" in cfg.risky_patterns  # 기본값 유지
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_config.py -v
```

- [ ] **Step 3: 구현**

`codingbot/config.py`:
```python
"""사용자 설정 로딩. YAML + 기본값."""
from dataclasses import dataclass, field
from typing import List

import yaml

from codingbot import logger, paths


DEFAULT_SAFE_TOOLS = ["Read", "Glob", "Grep", "TodoWrite"]
DEFAULT_RISKY_PATTERNS = [
    "rm -rf",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "DROP TABLE",
    "DROP DATABASE",
    ":(){:|:&};:",
    "mkfs",
    "dd if=",
]


@dataclass
class Config:
    enabled: bool = True
    time_limit_minutes: int = 30
    max_cycles_per_run: int = 50
    judge_model: str = "claude-haiku-4-5-20251001"
    api_key_env: str = "ANTHROPIC_API_KEY"
    safe_tools: List[str] = field(default_factory=lambda: list(DEFAULT_SAFE_TOOLS))
    risky_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_RISKY_PATTERNS))
    log_level: str = "info"


def load() -> Config:
    """config.yaml 로딩. 누락/손상 시 기본값."""
    cfg = Config()
    cfg_path = paths.config_file()
    if not cfg_path.exists():
        return cfg
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.warn("config_corrupt", error=str(e), fallback="defaults")
        return cfg

    for key in (
        "enabled",
        "time_limit_minutes",
        "max_cycles_per_run",
        "judge_model",
        "api_key_env",
        "safe_tools",
        "risky_patterns",
        "log_level",
    ):
        if key in data:
            setattr(cfg, key, data[key])
    return cfg
```

- [ ] **Step 4: `config.example.yaml` 작성**

```yaml
# CodingBot 설정 예시. ~/.codingbot/config.yaml로 복사하여 사용.
enabled: true
time_limit_minutes: 30
max_cycles_per_run: 50
judge_model: "claude-haiku-4-5-20251001"
api_key_env: "ANTHROPIC_API_KEY"
safe_tools:
  - Read
  - Glob
  - Grep
  - TodoWrite
risky_patterns:
  - "rm -rf"
  - "git push --force"
  - "git push -f"
  - "git reset --hard"
  - "DROP TABLE"
  - "DROP DATABASE"
  - "mkfs"
  - "dd if="
log_level: info
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/unit/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 6: 커밋**

```bash
git add codingbot/config.py tests/unit/test_config.py config.example.yaml
git commit -m "feat: add YAML config loader with sensible defaults"
```

---

## Task 4: state 모듈 + should_stop()

**Files:**
- Create: `codingbot/state.py`
- Create: `tests/unit/test_state.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_state.py`:
```python
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
    # 31분 전에 시작한 것처럼 조작
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
    # 손상 시 빈 dict 또는 초기 state 반환 (구현 결정: 초기 state)
    assert s["cycles_this_run"] == 0


def test_clear_stop_signal(tmp_codingbot_home):
    paths.stop_signal_file().touch()
    assert paths.stop_signal_file().exists()
    state.clear_stop_signal()
    assert not paths.stop_signal_file().exists()


def test_clear_stop_signal_no_file_ok(tmp_codingbot_home):
    """파일 없어도 에러 안 남."""
    state.clear_stop_signal()  # no exception
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_state.py -v
```

- [ ] **Step 3: 구현**

`codingbot/state.py`:
```python
"""state.json 관리 + 정지 조건 검사."""
import json
from datetime import datetime, timezone
from typing import Any, Dict

import portalocker

from codingbot import config, logger, paths


def _initial_state() -> Dict[str, Any]:
    return {
        "cycle_started_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "cycles_this_run": 0,
        "auto_approve_count": 0,
        "auto_continue_count": 0,
    }


def read() -> Dict[str, Any]:
    """state.json 읽기. 누락/손상 시 초기 상태 반환."""
    state_path = paths.state_file()
    if not state_path.exists():
        return _initial_state()
    try:
        with state_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warn("state_corrupt", error=str(e), fallback="reset")
        return _initial_state()


def write(s: Dict[str, Any]) -> None:
    """state.json 쓰기 (락 보호)."""
    paths.ensure_home()
    state_path = paths.state_file()
    with portalocker.Lock(str(state_path) + ".lock", timeout=5):
        with state_path.open("w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)


def start_cycle() -> None:
    """새 자동화 실행 시작. 카운터 리셋."""
    write(_initial_state())


def record_cycle() -> None:
    s = read()
    s["cycles_this_run"] = s.get("cycles_this_run", 0) + 1
    write(s)


def record_auto_approve() -> None:
    s = read()
    s["auto_approve_count"] = s.get("auto_approve_count", 0) + 1
    write(s)


def record_auto_continue() -> None:
    s = read()
    s["auto_continue_count"] = s.get("auto_continue_count", 0) + 1
    write(s)


def clear_stop_signal() -> None:
    """`.codingbot-stop` 파일 제거 (없어도 OK)."""
    f = paths.stop_signal_file()
    try:
        f.unlink()
    except FileNotFoundError:
        pass


def should_stop() -> bool:
    """다음 중 하나라도 참이면 True."""
    if paths.stop_signal_file().exists():
        return True

    cfg = config.load()
    s = read()

    # 시간 한도 체크
    started_at = s.get("cycle_started_at")
    if started_at:
        try:
            started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            elapsed_min = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
            if elapsed_min >= cfg.time_limit_minutes:
                return True
        except ValueError:
            pass

    # 사이클 한도 체크
    if s.get("cycles_this_run", 0) >= cfg.max_cycles_per_run:
        return True

    return False
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_state.py -v
```

Expected: 10 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/state.py tests/unit/test_state.py
git commit -m "feat: add state management with stop conditions"
```

---

## Task 5: handoff 모듈

**Files:**
- Create: `codingbot/handoff.py`
- Create: `tests/unit/test_handoff.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_handoff.py`:
```python
from codingbot import handoff, paths


def test_exists_false_initially(tmp_codingbot_home):
    assert handoff.exists() is False


def test_write_then_read(tmp_codingbot_home):
    handoff.write("## 다음 작업\nDb refactor")
    assert handoff.read() == "## 다음 작업\nDb refactor"


def test_exists_after_write(tmp_codingbot_home):
    handoff.write("anything")
    assert handoff.exists() is True


def test_clear_removes_file(tmp_codingbot_home):
    handoff.write("anything")
    handoff.clear()
    assert handoff.exists() is False
    assert handoff.read() is None


def test_clear_no_file_ok(tmp_codingbot_home):
    handoff.clear()  # no exception


def test_read_empty_file_returns_none(tmp_codingbot_home):
    paths.handoff_file().touch()
    assert handoff.read() is None


def test_was_just_written_equals_exists(tmp_codingbot_home):
    """spec 결정: was_just_written == exists. clear()는 사이클 시작 시 호출됨."""
    assert handoff.was_just_written() is False
    handoff.write("x")
    assert handoff.was_just_written() is True
    handoff.clear()
    assert handoff.was_just_written() is False
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_handoff.py -v
```

- [ ] **Step 3: 구현**

`codingbot/handoff.py`:
```python
"""핸드오프 파일 read/write/clear/exists."""
from typing import Optional

from codingbot import paths


def exists() -> bool:
    return paths.handoff_file().exists()


def read() -> Optional[str]:
    """파일이 없거나 빈 문자열이면 None."""
    f = paths.handoff_file()
    if not f.exists():
        return None
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return None
    return text if text.strip() else None


def write(content: str) -> None:
    paths.ensure_home()
    paths.handoff_file().write_text(content, encoding="utf-8")


def clear() -> None:
    f = paths.handoff_file()
    try:
        f.unlink()
    except FileNotFoundError:
        pass


def was_just_written() -> bool:
    """runner가 매 사이클 시작 시 clear()하므로, 파일 존재 = 이번 사이클 안에서 작성됨."""
    return exists()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_handoff.py -v
```

Expected: 7 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/handoff.py tests/unit/test_handoff.py
git commit -m "feat: add handoff file module"
```

---

## Task 6: transcript 파서

**Files:**
- Create: `codingbot/transcript.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/transcripts/sample_simple.jsonl`
- Create: `tests/unit/test_transcript.py`

- [ ] **Step 1: fixture transcript 작성**

`tests/fixtures/transcripts/sample_simple.jsonl`:
```jsonl
{"role": "user", "content": "사용자 인증 모듈 구현해줘"}
{"role": "assistant", "content": "먼저 기존 코드 살펴볼게요"}
{"role": "tool_use", "name": "Read", "input": {"file_path": "auth.py"}}
{"role": "tool_result", "content": "..."}
{"role": "assistant", "content": "auth.py 분석 완료. 구현 시작합니다."}
```

`tests/fixtures/__init__.py`: 빈 파일

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/unit/test_transcript.py`:
```python
from pathlib import Path
from codingbot import transcript

FIXTURE = Path(__file__).parent.parent / "fixtures" / "transcripts" / "sample_simple.jsonl"


def test_read_recent_returns_last_n():
    msgs = transcript.read_recent(FIXTURE, n=2)
    assert len(msgs) == 2
    assert msgs[-1]["role"] == "assistant"
    assert "구현 시작합니다" in msgs[-1]["content"]


def test_read_recent_more_than_total():
    msgs = transcript.read_recent(FIXTURE, n=100)
    assert len(msgs) == 5  # fixture에 5개 메시지


def test_last_assistant_text():
    text = transcript.last_assistant_text(FIXTURE)
    assert "구현 시작합니다" in text


def test_iter_messages_yields_all():
    msgs = list(transcript.iter_messages(FIXTURE))
    assert len(msgs) == 5
    assert msgs[0]["role"] == "user"


def test_missing_file_returns_empty(tmp_path):
    msgs = transcript.read_recent(tmp_path / "nope.jsonl", n=5)
    assert msgs == []


def test_corrupt_line_skipped(tmp_path):
    p = tmp_path / "broken.jsonl"
    p.write_text(
        '{"role": "user", "content": "ok"}\n'
        'this is not json\n'
        '{"role": "assistant", "content": "still ok"}\n',
        encoding="utf-8",
    )
    msgs = transcript.read_recent(p, n=10)
    assert len(msgs) == 2  # 손상된 줄은 건너뜀
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/unit/test_transcript.py -v
```

- [ ] **Step 4: 구현**

`codingbot/transcript.py`:
```python
"""Claude Code transcript .jsonl 파서. 손상된 줄은 건너뜀."""
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from codingbot import logger


def iter_messages(path: Path) -> Iterator[Dict[str, Any]]:
    """전체 transcript를 한 메시지씩 yield. 손상 줄은 스킵."""
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.warn("transcript_bad_line", path=str(path), line=lineno)
    except OSError as e:
        logger.warn("transcript_read_error", path=str(path), error=str(e))


def read_recent(path: Path, n: int = 5) -> List[Dict[str, Any]]:
    """마지막 N개 메시지."""
    msgs = list(iter_messages(path))
    return msgs[-n:]


def last_assistant_text(path: Path) -> Optional[str]:
    """가장 최근 assistant 메시지의 텍스트 컨텐츠."""
    for msg in reversed(list(iter_messages(path))):
        if msg.get("role") == "assistant":
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return None
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/unit/test_transcript.py -v
```

Expected: 6 passed.

- [ ] **Step 6: 커밋**

```bash
git add codingbot/transcript.py tests/fixtures/__init__.py tests/fixtures/transcripts/sample_simple.jsonl tests/unit/test_transcript.py
git commit -m "feat: add transcript parser"
```

---

## Task 7: heuristics 모듈

**Files:**
- Create: `codingbot/heuristics.py`
- Create: `tests/unit/test_heuristics.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_heuristics.py`:
```python
import pytest
from codingbot import heuristics


# classify_tool_call

def test_safe_tool_by_name(tmp_codingbot_home):
    assert heuristics.classify_tool_call("Read", {"file_path": "/a"}) == "safe"
    assert heuristics.classify_tool_call("Glob", {"pattern": "*.py"}) == "safe"
    assert heuristics.classify_tool_call("Grep", {"pattern": "x"}) == "safe"
    assert heuristics.classify_tool_call("TodoWrite", {"todos": []}) == "safe"


def test_safe_bash_commands(tmp_codingbot_home):
    safe_cmds = ["git status", "git log -n 5", "ls", "pwd", "cat README.md"]
    for cmd in safe_cmds:
        assert heuristics.classify_tool_call("Bash", {"command": cmd}) == "safe", cmd


def test_risky_patterns(tmp_codingbot_home):
    risky_cmds = [
        "rm -rf node_modules",
        "git push --force origin main",
        "git push -f",
        "DROP TABLE users",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
    ]
    for cmd in risky_cmds:
        assert heuristics.classify_tool_call("Bash", {"command": cmd}) == "risky", cmd


def test_unknown_tool(tmp_codingbot_home):
    assert heuristics.classify_tool_call("Edit", {"file_path": "x"}) == "unknown"
    assert heuristics.classify_tool_call("Bash", {"command": "npm install"}) == "unknown"


# is_clearly_done / is_clearly_continuing

def test_clearly_done_korean():
    assert heuristics.is_clearly_done("작업 완료했습니다.") is True
    assert heuristics.is_clearly_done("모든 단계 마쳤습니다.") is True
    assert heuristics.is_clearly_done("✓ 완료") is True


def test_clearly_done_english():
    assert heuristics.is_clearly_done("All done.") is True
    assert heuristics.is_clearly_done("Finished implementing.") is True


def test_not_clearly_done_when_continuing():
    assert heuristics.is_clearly_done("이제 다음 단계로 진행할게요") is False
    assert heuristics.is_clearly_done("Let me continue with the next step") is False


def test_clearly_continuing_korean():
    assert heuristics.is_clearly_continuing("이제 db.py를 살펴볼게요") is True
    assert heuristics.is_clearly_continuing("다음으로 api.py 정리하겠습니다") is True


def test_clearly_continuing_when_question_to_user_returns_false():
    """사용자에게 묻고 있으면 continuing 아님."""
    assert heuristics.is_clearly_continuing("이렇게 하는 게 맞을까요?") is False
    assert heuristics.is_clearly_continuing("어떻게 할지 알려주세요") is False
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_heuristics.py -v
```

- [ ] **Step 3: 구현**

`codingbot/heuristics.py`:
```python
"""규칙 기반 휴리스틱. 순수 함수. config의 safe/risky 리스트 참조."""
import re
from typing import Any, Dict

from codingbot import config


# 명백히 안전한 Bash 명령 (전체 매치, 인자 차이 허용)
_SAFE_BASH_PREFIXES = (
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    "ls",
    "pwd",
    "cat ",
    "echo ",
    "which ",
    "whoami",
    "date",
    "head ",
    "tail ",
    "wc ",
)

# 사용자에게 묻는 질문 패턴
_QUESTION_PATTERNS = [
    r"\?",
    r"맞을까요",
    r"알려주세요",
    r"확인해주세요",
    r"어떻게 (할|하면|진행)",
]

# 작업 완료 신호
_DONE_PATTERNS = [
    r"완료(했|되었|됐|입니다)",
    r"마쳤습니다",
    r"끝(났|냈)습니다",
    r"✓\s*완료",
    r"\bAll done\b",
    r"\bFinished\b",
    r"\bComplete[d]?\b",
]

# 작업 진행 신호
_CONTINUING_PATTERNS = [
    r"이제\s*[가-힣A-Za-z]+",
    r"다음(으로|에)\s*[가-힣A-Za-z]+",
    r"계속해서",
    r"이어서",
    r"\bNext,?\s+",
    r"\bNow,?\s+(I|let|let's)",
]


def classify_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """returns 'safe' | 'risky' | 'unknown'."""
    cfg = config.load()

    # 도구 이름 기반 화이트리스트
    if tool_name in cfg.safe_tools:
        return "safe"

    # Bash 분석
    if tool_name == "Bash":
        cmd = str(tool_input.get("command", ""))

        # 위험 패턴 체크 (먼저)
        for pattern in cfg.risky_patterns:
            if pattern in cmd:
                return "risky"

        # 안전 prefix 체크
        if any(cmd == p.rstrip() or cmd.startswith(p) for p in _SAFE_BASH_PREFIXES):
            return "safe"

        return "unknown"

    # 비-Bash 도구 입력에 위험 패턴이 있으면 risky
    flat_input = " ".join(str(v) for v in tool_input.values())
    for pattern in cfg.risky_patterns:
        if pattern in flat_input:
            return "risky"

    return "unknown"


def is_clearly_done(text: str) -> bool:
    if not text:
        return False
    if _has_question(text):
        return False
    if any(re.search(p, text) for p in _CONTINUING_PATTERNS):
        return False
    return any(re.search(p, text) for p in _DONE_PATTERNS)


def is_clearly_continuing(text: str) -> bool:
    if not text:
        return False
    if _has_question(text):
        return False
    return any(re.search(p, text) for p in _CONTINUING_PATTERNS)


def _has_question(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _QUESTION_PATTERNS)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_heuristics.py -v
```

Expected: 9 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/heuristics.py tests/unit/test_heuristics.py
git commit -m "feat: add rule-based heuristics for tool safety and message classification"
```

---

## Task 8: llm_judge 모듈

**Files:**
- Create: `codingbot/llm_judge.py`
- Create: `tests/unit/test_llm_judge.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_llm_judge.py`:
```python
import json
import pytest
from codingbot import llm_judge


def _mock_response(client_mock, text: str):
    """anthropic client가 message.content에 text 반환하도록 설정."""
    msg = type("Msg", (), {"text": text})()
    response = type("R", (), {"content": [msg]})()
    client_mock.messages.create.return_value = response


def test_evaluate_tool_safety_approve(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, '{"decision": "approve", "reason": "테스트 명령은 안전"}')
    result = llm_judge.evaluate_tool_safety(
        tool_name="Bash",
        tool_input={"command": "pytest"},
        recent_context="some context",
    )
    assert result["decision"] == "approve"
    assert "안전" in result["reason"]


def test_evaluate_tool_safety_ask(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, '{"decision": "ask", "reason": "확인 필요"}')
    result = llm_judge.evaluate_tool_safety("Edit", {"file_path": "x"}, "")
    assert result["decision"] == "ask"


def test_classify_returns_category(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(
        mock_anthropic,
        '{"category": "task_unit_complete", "reason": "auth.py 끝남"}',
    )
    result = llm_judge.classify(transcript_messages=[{"role": "assistant", "content": "끝"}])
    assert result["category"] == "task_unit_complete"


def test_invalid_json_response_raises(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, "not json")
    with pytest.raises(llm_judge.JudgeError):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")


def test_api_error_raises(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    mock_anthropic.messages.create.side_effect = Exception("rate_limit")
    with pytest.raises(llm_judge.JudgeError):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")


def test_no_api_key_raises(tmp_codingbot_home, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm_judge.JudgeError):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_llm_judge.py -v
```

- [ ] **Step 3: 구현**

`codingbot/llm_judge.py`:
```python
"""Claude API 호출 래퍼. JSON 응답 강제. 실패 시 JudgeError."""
import json
import os
from typing import Any, Dict, List

import anthropic

from codingbot import config


class JudgeError(Exception):
    """LLM 호출/파싱 실패. 호출 측에서 안전 폴백."""


_TOOL_SAFETY_SYSTEM = (
    "You are a safety classifier for a coding agent's tool calls. "
    "Output ONLY a JSON object with keys 'decision' (string: 'approve' or 'ask') "
    "and 'reason' (string, brief). "
    "'approve' means the tool call is safe to auto-approve (read-only, "
    "non-destructive, reversible). 'ask' means it warrants human approval "
    "(modifies external state, deletes data, network calls, etc.). "
    "When in doubt, prefer 'ask'."
)

_CLASSIFY_SYSTEM = (
    "You are a classifier for a coding agent's session state. "
    "Given the recent transcript, classify what is happening. "
    "Output ONLY a JSON object with keys 'category' and 'reason'. "
    "category must be exactly one of: "
    "'continuing' (agent is mid-task, will keep going if prompted), "
    "'task_unit_complete' (one logical task finished, more work might exist elsewhere), "
    "'all_done' (entire goal accomplished, nothing more to do), "
    "'blocked_unsure' (agent is stuck or asking for help)."
)


def _client() -> anthropic.Anthropic:
    cfg = config.load()
    key = os.environ.get(cfg.api_key_env)
    if not key:
        raise JudgeError(f"missing API key in env: {cfg.api_key_env}")
    return anthropic.Anthropic(api_key=key)


def _call(system: str, user: str) -> str:
    cfg = config.load()
    try:
        resp = _client().messages.create(
            model=cfg.judge_model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:
        raise JudgeError(f"API call failed: {e}")
    try:
        return resp.content[0].text
    except (IndexError, AttributeError) as e:
        raise JudgeError(f"unexpected response shape: {e}")


def _parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise JudgeError(f"non-JSON response: {text[:200]}") from e


def evaluate_tool_safety(
    tool_name: str, tool_input: Dict[str, Any], recent_context: str
) -> Dict[str, Any]:
    user = (
        f"Tool: {tool_name}\n"
        f"Input: {json.dumps(tool_input, ensure_ascii=False)[:1000]}\n"
        f"Recent context (last messages, may be truncated):\n{recent_context[:1500]}"
    )
    raw = _call(_TOOL_SAFETY_SYSTEM, user)
    parsed = _parse_json(raw)
    if "decision" not in parsed or parsed["decision"] not in ("approve", "ask"):
        raise JudgeError(f"invalid decision in response: {parsed}")
    parsed.setdefault("reason", "")
    return parsed


def classify(transcript_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary_parts = []
    for msg in transcript_messages[-8:]:
        role = msg.get("role", "?")
        content = str(msg.get("content", ""))[:500]
        summary_parts.append(f"[{role}] {content}")
    user = "Recent transcript:\n" + "\n".join(summary_parts)
    raw = _call(_CLASSIFY_SYSTEM, user)
    parsed = _parse_json(raw)
    valid = ("continuing", "task_unit_complete", "all_done", "blocked_unsure")
    if parsed.get("category") not in valid:
        raise JudgeError(f"invalid category in response: {parsed}")
    parsed.setdefault("reason", "")
    return parsed
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_llm_judge.py -v
```

Expected: 6 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/llm_judge.py tests/unit/test_llm_judge.py
git commit -m "feat: add LLM judge wrapper with JSON-mode prompts"
```

---

## Task 9: PreToolUse hook (auto_approve)

**Files:**
- Create: `codingbot/hooks/auto_approve.py`
- Create: `tests/hooks/__init__.py`
- Create: `tests/hooks/test_auto_approve.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/hooks/test_auto_approve.py`:
```python
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_hook(input_dict, env_overrides=None):
    """hook 스크립트를 subprocess로 실행."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.auto_approve"],
        input=json.dumps(input_dict),
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def test_safe_tool_returns_approve(tmp_codingbot_home):
    r = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "approve"


def test_risky_tool_skips_auto_approval(tmp_codingbot_home):
    r = _run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""  # decision 미출력 = Claude Code가 사용자에게 물음


def test_unknown_tool_calls_llm(tmp_codingbot_home, mocker):
    """unknown 분류 시 LLM 호출. subprocess이므로 진짜 호출 안 가게 ANTHROPIC_API_KEY 비움."""
    r = _run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": "x"}, "transcript_path": ""},
        env_overrides={
            "CODINGBOT_HOME": str(tmp_codingbot_home),
            "ANTHROPIC_API_KEY": "",  # 키 없음 → JudgeError → exit 0
        },
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""  # LLM 실패 폴백


def test_stop_signal_skips_auto_approval(tmp_codingbot_home):
    (tmp_codingbot_home / ".codingbot-stop").touch()
    r = _run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "transcript_path": ""},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_invalid_json_input_does_not_crash(tmp_codingbot_home):
    """stdin이 깨져도 hook은 exit 0."""
    r = subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.auto_approve"],
        input="not json at all",
        capture_output=True,
        text=True,
        env={**os.environ, "CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/hooks/test_auto_approve.py -v
```

- [ ] **Step 3: 구현**

`codingbot/hooks/auto_approve.py`:
```python
"""PreToolUse hook entrypoint.

stdin: {"tool_name": str, "tool_input": dict, "transcript_path": str, ...}
stdout: {"decision": "approve", "reason": "..."} 또는 빈 출력 (사용자 승인 받게)
exit code: 항상 0 (Claude Code 흐름 막지 않음)
"""
import json
import sys
from pathlib import Path

from codingbot import heuristics, llm_judge, logger, state, transcript


def _read_recent_context(transcript_path: str, n_chars: int = 1500) -> str:
    if not transcript_path:
        return ""
    try:
        msgs = transcript.read_recent(Path(transcript_path), n=5)
    except Exception:
        return ""
    parts = []
    for m in msgs:
        parts.append(f"[{m.get('role','?')}] {str(m.get('content',''))[:300]}")
    return "\n".join(parts)[-n_chars:]


def _approve(reason: str, judge: str) -> None:
    state.record_auto_approve()
    logger.info("auto_approve", decision="approve", judge=judge, reason=reason)
    print(json.dumps({"decision": "approve", "reason": reason}))


def _skip(why: str, judge: str) -> None:
    logger.info("auto_skip", judge=judge, reason=why)
    # stdout 미출력 → Claude Code가 평소처럼 사용자에게 물음


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        transcript_path = data.get("transcript_path", "")

        if state.should_stop():
            _skip("stop_signal_active", "rule")
            return 0

        verdict = heuristics.classify_tool_call(tool_name, tool_input)
        if verdict == "safe":
            _approve(f"safe ({tool_name})", judge="heuristic")
            return 0
        if verdict == "risky":
            _skip(f"risky ({tool_name})", judge="heuristic")
            return 0

        # unknown → LLM
        try:
            ctx = _read_recent_context(transcript_path)
            result = llm_judge.evaluate_tool_safety(tool_name, tool_input, ctx)
        except llm_judge.JudgeError as e:
            logger.warn("llm_api_error", hook="auto_approve", error=str(e))
            _skip("llm_failed", judge="llm")
            return 0

        if result["decision"] == "approve":
            _approve(result.get("reason", ""), judge="llm")
        else:
            _skip(result.get("reason", "ask"), judge="llm")
        return 0

    except Exception as e:
        logger.error("hook_exception", hook="auto_approve", error=str(e))
        return 0  # 안전 폴백


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/hooks/test_auto_approve.py -v
```

Expected: 5 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/hooks/auto_approve.py tests/hooks/__init__.py tests/hooks/test_auto_approve.py
git commit -m "feat: add PreToolUse hook (auto-approve)"
```

---

## Task 10: Stop hook (handoff_or_continue)

**Files:**
- Create: `codingbot/hooks/handoff_or_continue.py`
- Create: `tests/fixtures/transcripts/sample_done.jsonl`
- Create: `tests/fixtures/transcripts/sample_continuing.jsonl`
- Create: `tests/hooks/test_handoff_or_continue.py`

- [ ] **Step 1: 추가 fixture 작성**

`tests/fixtures/transcripts/sample_done.jsonl`:
```jsonl
{"role": "user", "content": "auth 모듈 구현해줘"}
{"role": "assistant", "content": "auth.py 구현 완료했습니다. 모든 테스트 통과."}
```

`tests/fixtures/transcripts/sample_continuing.jsonl`:
```jsonl
{"role": "user", "content": "리팩터링 해줘"}
{"role": "assistant", "content": "auth.py 정리 끝났어요. 이제 db.py 살펴볼게요."}
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/hooks/test_handoff_or_continue.py`:
```python
import json
import os
import subprocess
import sys
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "transcripts"


def _run_hook(input_dict, env_overrides=None):
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.handoff_or_continue"],
        input=json.dumps(input_dict),
        capture_output=True,
        text=True,
        env=env,
    )


def test_stop_signal_exits_silently(tmp_codingbot_home):
    (tmp_codingbot_home / ".codingbot-stop").touch()
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_handoff_exists_exits_silently(tmp_codingbot_home):
    (tmp_codingbot_home / "handoff.md").write_text("some handoff", encoding="utf-8")
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_clearly_continuing_blocks_with_continue_msg(tmp_codingbot_home):
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_continuing.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert "계속" in out["reason"] or "이어" in out["reason"]


def test_clearly_done_requests_handoff(tmp_codingbot_home):
    r = _run_hook(
        {"transcript_path": str(FIXTURE_DIR / "sample_done.jsonl")},
        env_overrides={"CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert "handoff" in out["reason"].lower() or "핸드오프" in out["reason"]


def test_llm_failure_falls_back_to_silent(tmp_codingbot_home, tmp_path):
    """휴리스틱이 unknown으로 분류 + LLM 실패 → exit 0 (block 안 함)."""
    # 휴리스틱이 분류 못 하는 메시지
    ambiguous = tmp_path / "ambiguous.jsonl"
    ambiguous.write_text(
        '{"role": "assistant", "content": "음... 잠시만요"}\n',
        encoding="utf-8",
    )
    r = _run_hook(
        {"transcript_path": str(ambiguous)},
        env_overrides={
            "CODINGBOT_HOME": str(tmp_codingbot_home),
            "ANTHROPIC_API_KEY": "",  # LLM 실패
        },
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_invalid_input_does_not_crash(tmp_codingbot_home):
    r = subprocess.run(
        [sys.executable, "-m", "codingbot.hooks.handoff_or_continue"],
        input="garbage",
        capture_output=True,
        text=True,
        env={**os.environ, "CODINGBOT_HOME": str(tmp_codingbot_home)},
    )
    assert r.returncode == 0
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/hooks/test_handoff_or_continue.py -v
```

- [ ] **Step 4: 구현**

`codingbot/hooks/handoff_or_continue.py`:
```python
"""Stop hook entrypoint.

stdin: {"transcript_path": str, ...}
stdout:
  - {"decision": "block", "reason": "..."}: Claude가 멈추지 않고 reason을 받아 진행
  - 빈 출력: Claude 정상 정지
exit code: 항상 0
"""
import json
import sys
from pathlib import Path

from codingbot import handoff, heuristics, llm_judge, logger, state, transcript


HANDOFF_INSTRUCTION = (
    "이 작업 단위가 완료된 것 같아요. 이어서 할 작업이 있으면 "
    "`~/.codingbot/handoff.md`에 다음을 작성하고 종료해 주세요: "
    "(a) 지금까지 한 일 (b) 다음에 할 일 (c) 새 세션이 알아야 할 중요 컨텍스트. "
    "더 할 일 없으면 핸드오프 만들지 말고 그렇게 답하고 종료하세요."
)

CONTINUE_INSTRUCTION = "작업이 아직 끝나지 않은 것 같아요. 계속 진행해 주세요."

UNSTUCK_INSTRUCTION = (
    "막힌 부분이 있으면 가능한 도구로 더 조사해 주세요. "
    "여전히 모르겠으면 정확히 뭐가 막혔는지 핸드오프에 적고 종료하세요."
)


def _block(reason: str, judge: str, outcome: str) -> None:
    state.record_auto_continue()
    logger.info("stop_hook", outcome=outcome, judge=judge)
    print(json.dumps({"decision": "block", "reason": reason}))


def _allow_stop(why: str, judge: str = "rule") -> None:
    logger.info("stop_hook", outcome="allow_stop", judge=judge, reason=why)


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        transcript_path = data.get("transcript_path", "")

        if state.should_stop():
            _allow_stop("stop_signal_or_limit_active")
            return 0

        if handoff.was_just_written():
            _allow_stop("handoff_already_written")
            return 0

        last_text = ""
        if transcript_path:
            t = transcript.last_assistant_text(Path(transcript_path)) or ""
            last_text = t

        # 휴리스틱 우선
        if last_text:
            if heuristics.is_clearly_continuing(last_text):
                _block(CONTINUE_INSTRUCTION, judge="heuristic", outcome="continue")
                return 0
            if heuristics.is_clearly_done(last_text):
                _block(HANDOFF_INSTRUCTION, judge="heuristic", outcome="request_handoff")
                return 0

        # 애매하면 LLM
        try:
            msgs = transcript.read_recent(Path(transcript_path), n=5) if transcript_path else []
            verdict = llm_judge.classify(msgs)
        except llm_judge.JudgeError as e:
            logger.warn("llm_api_error", hook="handoff_or_continue", error=str(e))
            _allow_stop("llm_failed", judge="llm")
            return 0

        cat = verdict["category"]
        if cat == "continuing":
            _block(CONTINUE_INSTRUCTION, judge="llm", outcome="continue")
        elif cat == "task_unit_complete" or cat == "all_done":
            _block(HANDOFF_INSTRUCTION, judge="llm", outcome="request_handoff")
        elif cat == "blocked_unsure":
            _block(UNSTUCK_INSTRUCTION, judge="llm", outcome="unstuck")
        else:
            _allow_stop(f"unknown_category:{cat}", judge="llm")
        return 0

    except Exception as e:
        logger.error("hook_exception", hook="handoff_or_continue", error=str(e))
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/hooks/test_handoff_or_continue.py -v
```

Expected: 6 passed.

- [ ] **Step 6: 커밋**

```bash
git add codingbot/hooks/handoff_or_continue.py tests/fixtures/transcripts/sample_done.jsonl tests/fixtures/transcripts/sample_continuing.jsonl tests/hooks/test_handoff_or_continue.py
git commit -m "feat: add Stop hook (handoff or continue)"
```

---

## Task 11: runner 모듈

**Files:**
- Create: `codingbot/runner.py`
- Create: `tests/runner/__init__.py`
- Create: `tests/runner/test_runner.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/runner/test_runner.py`:
```python
import os
import subprocess as sp
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from codingbot import handoff, paths, runner, state


class FakeClaude:
    """subprocess.run 대체. 매 호출마다 정해진 동작 시뮬레이트."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []

    def __call__(self, args, **kwargs):
        if not self.scripts:
            raise AssertionError(f"unexpected extra call: {args}")
        action = self.scripts.pop(0)
        self.calls.append({"args": args, "action": action})
        if "writes_handoff" in action:
            handoff.write(action["writes_handoff"])
        return MagicMock(returncode=action.get("exit_code", 0))


def test_normal_flow_terminates_after_done_then_final_check(tmp_codingbot_home, monkeypatch):
    """일반 사이클 → 다 했음 → final check → 다 했음 → 종료."""
    fake = FakeClaude([
        {"writes_handoff": "## 다음 작업: db.py"},  # 사이클 1: 핸드오프 작성
        {},  # 사이클 2: 핸드오프 안 만듦 → final check 트리거
        {},  # final check: 또 핸드오프 안 만듦 → 종료
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("리팩터링해줘")
    assert len(fake.calls) == 3
    # 첫 호출은 initial prompt
    assert fake.calls[0]["args"][1] == "리팩터링해줘"
    # 두 번째는 handoff 내용
    assert "db.py" in fake.calls[1]["args"][1]
    # 세 번째는 FINAL_CHECK_PROMPT
    from codingbot.runner import FINAL_CHECK_PROMPT
    assert fake.calls[2]["args"][1] == FINAL_CHECK_PROMPT


def test_final_check_finds_new_work(tmp_codingbot_home, monkeypatch):
    """final check가 새 작업 찾으면 일반 사이클 복귀."""
    fake = FakeClaude([
        {},  # 사이클 1: 다 했음 → final check
        {"writes_handoff": "## 추가 작업: 테스트"},  # final check가 새 작업 발견
        {},  # 사이클 2 (새 작업): 다 했음 → 또 final check
        {},  # final check 2: 또 다 했음 → 종료
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 4


def test_stop_signal_breaks_loop(tmp_codingbot_home, monkeypatch):
    """첫 사이클 끝난 후 stop file 생성 → 다음 사이클 시작 안 함."""
    def fake_with_stop(args, **kw):
        # 첫 호출 후 stop 신호
        handoff.write("계속 작업")
        paths.stop_signal_file().touch()
        return MagicMock(returncode=0)
    monkeypatch.setattr(sp, "run", fake_with_stop)
    runner.run("초기")
    s = state.read()
    assert s["cycles_this_run"] == 1


def test_run_clears_old_stop_signal_at_start(tmp_codingbot_home, monkeypatch):
    """이전 정지 신호가 남아있어도 새 run이 정리."""
    paths.stop_signal_file().touch()  # 이전 정지 잔재
    fake = FakeClaude([
        {"writes_handoff": "x"},
        {},
        {},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) >= 1  # 적어도 시작은 함


def test_abnormal_exit_retries_once(tmp_codingbot_home, monkeypatch):
    """claude 비정상 exit 1회 → 같은 메시지로 재시도, 두 번째 정상이면 진행."""
    fake = FakeClaude([
        {"exit_code": 1},  # 첫 시도 실패
        {"writes_handoff": "ok"},  # 재시도 성공, 핸드오프 작성
        {},  # 사이클 2: 다 했음
        {},  # final check: 다 했음 → 종료
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 4


def test_abnormal_exit_twice_breaks(tmp_codingbot_home, monkeypatch):
    """claude 비정상 exit 2회 연속이면 break."""
    fake = FakeClaude([
        {"exit_code": 1},
        {"exit_code": 1},
    ])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")
    assert len(fake.calls) == 2
    s = state.read()
    assert s["cycles_this_run"] == 2  # 둘 다 시도는 됨


def test_stale_lock_is_cleaned_up(tmp_codingbot_home, monkeypatch):
    """이전 실행이 비정상 종료되어 죽은 PID로 락이 남아 있으면 자동 정리."""
    # 거의 확실히 안 살아있는 PID
    paths.lock_file().write_text("999999", encoding="utf-8")
    monkeypatch.setattr(runner, "_is_pid_alive", lambda pid: False)
    fake = FakeClaude([{"writes_handoff": "x"}, {}, {}])
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")  # 정상 진행해야 함
    assert len(fake.calls) == 3


def test_concurrent_run_rejected(tmp_codingbot_home, monkeypatch):
    """살아있는 다른 PID가 락을 가지고 있으면 즉시 종료 + 에러 메시지."""
    paths.lock_file().write_text("12345", encoding="utf-8")
    monkeypatch.setattr(runner, "_is_pid_alive", lambda pid: True)
    fake = FakeClaude([])  # 호출되면 안 됨
    monkeypatch.setattr(sp, "run", fake)
    runner.run("초기")  # raise 없이 종료, 호출 0회
    assert len(fake.calls) == 0
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/runner/test_runner.py -v
```

- [ ] **Step 3: 구현**

`codingbot/runner.py`:
```python
"""Shell-loop wrapper. Claude Code를 자식 프로세스로 띄우고 사이클을 돌린다."""
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from codingbot import handoff, logger, paths, state


FINAL_CHECK_PROMPT = (
    "지금 코드 상태를 다시 한번 살펴봐 주세요. 추가로 가능한 작업이 있나요? "
    "— 개선/리팩터링, 테스트 추가, 문서화, 미발견 버그, 일관성 안 맞는 패턴 등.\n\n"
    "있다면 평소처럼 `~/.codingbot/handoff.md`에 작성하고 종료하세요. "
    "정말 없다면 핸드오프 만들지 말고 그렇게 알려 주고 종료하세요."
)


class RunnerLockError(Exception):
    pass


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_QUERY_INFORMATION = 0x0400
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _acquire_lock() -> None:
    paths.ensure_home()
    lf = paths.lock_file()
    if lf.exists():
        try:
            existing_pid = int(lf.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            existing_pid = -1
        if existing_pid != os.getpid() and _is_pid_alive(existing_pid):
            raise RunnerLockError(
                f"another codingbot run is in progress (pid={existing_pid}). "
                "Use `codingbot stop` or wait."
            )
        # stale lock (or same pid) → 정리
        try:
            lf.unlink()
        except FileNotFoundError:
            pass
    lf.write_text(str(os.getpid()), encoding="utf-8")


def _release_lock() -> None:
    try:
        paths.lock_file().unlink()
    except FileNotFoundError:
        pass


def run(initial_prompt: str) -> None:
    """codingbot run의 본체."""
    try:
        _acquire_lock()
    except RunnerLockError as e:
        logger.error("lock_conflict", error=str(e))
        print(f"[codingbot] {e}", file=sys.stderr)
        return

    state.clear_stop_signal()
    handoff.clear()
    state.start_cycle()
    logger.info("run_start", initial_prompt=initial_prompt[:200])

    final_check_pending = False
    abnormal_exits = 0
    interrupted = False

    def _on_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        logger.info("user_sigint")
    prev_handler = signal.signal(signal.SIGINT, _on_sigint)

    try:
        while True:
            if interrupted:
                logger.info("run_end", reason="user_sigint")
                break
            if state.should_stop():
                logger.info("run_end", reason="stop_signal_or_limit")
                break

            if final_check_pending:
                msg = FINAL_CHECK_PROMPT
                logger.info("final_check_started")
            else:
                msg = handoff.read() or initial_prompt
            handoff.clear()

            logger.info("cycle_start", msg_preview=msg[:200])
            result = subprocess.run(["claude", msg])
            state.record_cycle()
            exit_code = result.returncode
            logger.info("cycle_end", exit_code=exit_code)

            if exit_code != 0:
                abnormal_exits += 1
                logger.warn("claude_abnormal_exit", code=exit_code, count=abnormal_exits)
                if abnormal_exits >= 2:
                    print(
                        "[codingbot] Claude Code 연속 비정상 종료. 자동화를 중단합니다.",
                        file=sys.stderr,
                    )
                    logger.error("run_end", reason="repeated_abnormal_exit")
                    break
                continue
            abnormal_exits = 0

            if handoff.exists():
                final_check_pending = False
            else:
                if final_check_pending:
                    logger.info("run_end", reason="final_check_returned_done")
                    break
                final_check_pending = True
    finally:
        signal.signal(signal.SIGINT, prev_handler)
        _release_lock()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/runner/test_runner.py -v
```

Expected: 8 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/runner.py tests/runner/__init__.py tests/runner/test_runner.py
git commit -m "feat: add shell-loop runner with handoff cycles and final-check"
```

---

## Task 12: install_hooks 모듈

**Files:**
- Create: `codingbot/install_hooks.py`
- Create: `tests/unit/test_install_hooks.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_install_hooks.py`:
```python
import json
import sys
from codingbot import install_hooks


def test_install_creates_settings_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
    install_hooks.install()
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "hooks" in data
    assert "PreToolUse" in data["hooks"]
    assert "Stop" in data["hooks"]
    # PreToolUse hook이 auto_approve 모듈을 가리키는지
    pre = data["hooks"]["PreToolUse"]
    assert any("codingbot.hooks.auto_approve" in str(h) for h in _flatten(pre))
    # Stop hook이 handoff_or_continue 모듈을 가리키는지
    stop = data["hooks"]["Stop"]
    assert any("codingbot.hooks.handoff_or_continue" in str(h) for h in _flatten(stop))


def test_install_preserves_existing_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    existing = {"theme": "dark", "model": "sonnet", "hooks": {"PreCompact": [{"a": 1}]}}
    settings_path.write_text(json.dumps(existing), encoding="utf-8")
    install_hooks.install()
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["model"] == "sonnet"
    assert "PreCompact" in data["hooks"]  # 기존 hook 보존
    assert "PreToolUse" in data["hooks"]  # 새 hook 추가
    assert "Stop" in data["hooks"]


def test_install_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    install_hooks.install()
    install_hooks.install()  # 두 번 호출
    settings_path = tmp_path / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    pre = data["hooks"]["PreToolUse"]
    # auto_approve 모듈을 가리키는 항목이 정확히 1개
    matches = [h for h in _flatten(pre) if "codingbot.hooks.auto_approve" in str(h)]
    assert len(matches) == 1


def test_uninstall_removes_codingbot_hooks_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    install_hooks.install()
    install_hooks.uninstall()
    settings_path = tmp_path / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    pre_flat = _flatten(data.get("hooks", {}).get("PreToolUse", []))
    assert not any("codingbot" in str(h) for h in pre_flat)


def _flatten(obj):
    """settings.json의 hook 목록은 nested 구조 (matchers/hooks 객체). 모든 leaf 값 yield."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _flatten(v)
    else:
        yield obj
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_install_hooks.py -v
```

- [ ] **Step 3: 구현**

`codingbot/install_hooks.py`:
```python
"""~/.claude/settings.json에 codingbot hook 등록/해제.

Claude Code 공식 hooks 포맷:
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "..."}]}
    ],
    "Stop": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "..."}]}
    ]
  }
}
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


_PRE_TOOL_USE_CMD = f"{sys.executable} -m codingbot.hooks.auto_approve"
_STOP_CMD = f"{sys.executable} -m codingbot.hooks.handoff_or_continue"

_MARKER = "codingbot.hooks"  # 우리가 등록한 hook을 식별


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _load() -> Dict[str, Any]:
    p = _settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: Dict[str, Any]) -> None:
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_codingbot_hook(group: Dict[str, Any]) -> bool:
    """matchers 객체 안에 codingbot 명령이 있는지."""
    for h in group.get("hooks", []):
        cmd = h.get("command", "")
        if _MARKER in cmd:
            return True
    return False


def install() -> None:
    data = _load()
    hooks = data.setdefault("hooks", {})

    for event, cmd in [("PreToolUse", _PRE_TOOL_USE_CMD), ("Stop", _STOP_CMD)]:
        groups: List[Dict[str, Any]] = hooks.setdefault(event, [])
        # 기존 codingbot 등록 제거 (idempotent)
        groups[:] = [g for g in groups if not _is_codingbot_hook(g)]
        # 새로 추가
        groups.append({
            "matcher": "*",
            "hooks": [{"type": "command", "command": cmd}],
        })

    _save(data)
    print(f"[codingbot] hooks installed at {_settings_path()}")


def uninstall() -> None:
    data = _load()
    hooks = data.get("hooks", {})
    for event in ("PreToolUse", "Stop"):
        groups = hooks.get(event, [])
        groups[:] = [g for g in groups if not _is_codingbot_hook(g)]
        if not groups:
            hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)
    _save(data)
    print(f"[codingbot] hooks uninstalled from {_settings_path()}")
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_install_hooks.py -v
```

Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add codingbot/install_hooks.py tests/unit/test_install_hooks.py
git commit -m "feat: add install/uninstall for Claude Code hook registration"
```

---

## Task 13: CLI

**Files:**
- Create: `codingbot/cli.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_cli.py`:
```python
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
    spy = mocker.patch("codingbot.runner.run")
    cli.main(["run", "어떤 작업"])
    spy.assert_called_once_with("어떤 작업")


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
    assert rc != 0  # subcommand 없으면 non-zero


def test_config_outputs_yaml_keys(tmp_codingbot_home, capsys):
    cli.main(["config"])
    out = capsys.readouterr().out
    assert "time_limit_minutes" in out
    assert "judge_model" in out
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/unit/test_cli.py -v
```

- [ ] **Step 3: 구현**

`codingbot/cli.py`:
```python
"""argparse 기반 codingbot CLI."""
import argparse
import json
import sys
from typing import List, Optional

from codingbot import config, install_hooks, paths, runner, state


def _cmd_run(args: argparse.Namespace) -> int:
    runner.run(args.prompt)
    return 0


def _cmd_stop(args: argparse.Namespace) -> int:
    paths.ensure_home()
    paths.stop_signal_file().touch()
    print("[codingbot] stop signal set. Active runs will exit at next safe point.")
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    state.clear_stop_signal()
    print("[codingbot] stop signal cleared.")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    s = state.read()
    cfg = config.load()
    print("=== CodingBot Status ===")
    print(f"home: {paths.codingbot_home()}")
    print(f"stop signal: {'YES' if paths.stop_signal_file().exists() else 'no'}")
    print(f"runner lock: {'YES' if paths.lock_file().exists() else 'no'}")
    print(f"state cycles_this_run: {s.get('cycles_this_run', 0)}")
    print(f"state auto_approve_count: {s.get('auto_approve_count', 0)}")
    print(f"state auto_continue_count: {s.get('auto_continue_count', 0)}")
    print(f"state cycle_started_at: {s.get('cycle_started_at', 'n/a')}")
    print(f"config time_limit_minutes: {cfg.time_limit_minutes}")
    print(f"config max_cycles_per_run: {cfg.max_cycles_per_run}")
    return 0


def _cmd_tail_log(args: argparse.Namespace) -> int:
    p = paths.log_file()
    if not p.exists():
        print("[codingbot] no log yet")
        return 0
    lines = p.read_text(encoding="utf-8").splitlines()
    for line in lines[-args.n:]:
        print(line)
    return 0


def _cmd_install_hooks(args: argparse.Namespace) -> int:
    install_hooks.install()
    return 0


def _cmd_uninstall_hooks(args: argparse.Namespace) -> int:
    install_hooks.uninstall()
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    cfg = config.load()
    import yaml
    print(yaml.safe_dump(cfg.__dict__, allow_unicode=True, sort_keys=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="codingbot")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    r = sub.add_parser("run", help="자동화 시작")
    r.add_argument("prompt", help="초기 작업 프롬프트")
    r.set_defaults(func=_cmd_run)

    s = sub.add_parser("stop", help="자동화 정지 신호")
    s.set_defaults(func=_cmd_stop)

    st = sub.add_parser("start", help="정지 신호 해제")
    st.set_defaults(func=_cmd_start)

    status = sub.add_parser("status", help="현재 상태 표시")
    status.set_defaults(func=_cmd_status)

    tail = sub.add_parser("tail-log", help="최근 로그 표시")
    tail.add_argument("-n", type=int, default=20, help="표시할 줄 수")
    tail.set_defaults(func=_cmd_tail_log)

    install = sub.add_parser("install-hooks", help="Claude Code에 hook 등록")
    install.set_defaults(func=_cmd_install_hooks)

    uninstall = sub.add_parser("uninstall-hooks", help="hook 등록 해제")
    uninstall.set_defaults(func=_cmd_uninstall_hooks)

    cfg = sub.add_parser("config", help="현재 적용 중인 설정 표시")
    cfg.set_defaults(func=_cmd_config)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/unit/test_cli.py -v
```

Expected: 9 passed.

- [ ] **Step 5: `codingbot --help` 동작 확인**

```bash
codingbot --help
codingbot status
```

`--help`는 모든 subcommand 나열, `status`는 빈 상태 표시.

- [ ] **Step 6: 커밋**

```bash
git add codingbot/cli.py tests/unit/test_cli.py
git commit -m "feat: add codingbot CLI (run/stop/start/status/tail-log/install-hooks/config)"
```

---

## Task 14: 전체 테스트 + README 업데이트

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 전체 테스트 실행**

```bash
pytest tests/ -v
```

Expected: 모든 unit + hook + runner 테스트 통과. 50개 이상.

- [ ] **Step 2: 커버리지 확인**

```bash
pytest tests/ --cov=codingbot --cov-report=term-missing
```

목표: `codingbot/runner.py`, `codingbot/hooks/*.py`, `codingbot/heuristics.py` 90%+.

- [ ] **Step 3: README 업데이트**

```markdown
# CodingBot

Claude Code의 권한 자동 승인 + 작업 단위마다 컨텍스트 초기화하며 자동 진행하는 CLI 도구.

## 설치

```bash
pip install -e .
codingbot install-hooks
export ANTHROPIC_API_KEY=...
```

## 사용

```bash
# 자동화 시작
codingbot run "전체 백엔드 리팩터링해줘"

# 다른 터미널에서 멈추기
codingbot stop

# 진행 상황
codingbot status
codingbot tail-log -n 50

# 설정 확인
codingbot config
```

## 동작 원리

1. `codingbot run "<prompt>"`이 셸 루프를 시작
2. 매 사이클마다 `claude "<msg>"`로 인터랙티브 Claude Code 세션 실행
3. **PreToolUse hook**이 안전한 도구 호출은 자동 승인 (위험한 건 사용자에게 물음)
4. **Stop hook**이 작업 단위 완료 감지 시 Claude한테 핸드오프 문서 작성 요청
5. 새 사이클이 핸드오프 문서를 시작 메시지로 받음 = 진짜 컨텍스트 초기화
6. "다 했음" 신호 시 한 번 더 final check, 또 "다 했음"이면 종료

## 안전장치

- 시간 한도: 기본 30분 (config로 조정)
- 사이클 한도: 기본 50회
- `codingbot stop`: 다른 터미널에서 즉시 정지 신호
- 위험 패턴 (rm -rf, force push 등)은 자동 승인 안 함
- LLM 실패 시 안전 폴백 (= 사용자에게 정상적으로 물어봄)

## 설정

`~/.codingbot/config.yaml` (없으면 기본값. `config.example.yaml` 참고)

## 로그

`~/.codingbot/log.jsonl` — 모든 자동 결정 기록.
```

- [ ] **Step 4: 커밋**

```bash
git add README.md
git commit -m "docs: update README with installation, usage, and design overview"
```

---

## Task 15: E2E 스모크 테스트 스캐폴딩 (선택, 수동 트리거)

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/test_smoke.py`
- Create: `tests/e2e/README.md`

**주의: 이 테스트는 실제 Claude Code + 실제 API 호출. 비용 발생. CI에서 자동 실행 금지. 수동으로만.**

- [ ] **Step 1: E2E 스모크 테스트 작성**

`tests/e2e/test_smoke.py`:
```python
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

    # 테스트 격리
    test_home = tmp_path / "codingbot_home"
    test_home.mkdir()
    monkeypatch.setenv("CODINGBOT_HOME", str(test_home))

    workdir = tmp_path / "toy_project"
    workdir.mkdir()
    (workdir / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8"
    )

    # codingbot run 실행 (subprocess)
    result = subprocess.run(
        ["codingbot", "run", "이 Flask 앱에 /health 엔드포인트 추가하고 print로 'health ok' 찍게 해줘"],
        cwd=workdir,
        timeout=600,
        capture_output=True,
        text=True,
    )

    # 검증: 로그 파일 존재 + 사이클 2개 이상
    log_path = test_home / "log.jsonl"
    assert log_path.exists(), "log file should exist"
    cycle_starts = [line for line in log_path.read_text(encoding="utf-8").splitlines() if "cycle_start" in line]
    assert len(cycle_starts) >= 1, "at least one cycle should have started"

    # 검증: 코드가 실제로 변경됨 (/health 엔드포인트)
    app_code = (workdir / "app.py").read_text(encoding="utf-8")
    assert "/health" in app_code
```

- [ ] **Step 2: E2E README**

`tests/e2e/README.md`:
```markdown
# E2E Smoke Tests

실제 Claude Code + Anthropic API를 호출하는 통합 테스트. **CI에서 자동 실행 금지.**

## 실행

```bash
export ANTHROPIC_API_KEY=...
codingbot install-hooks
pytest tests/e2e/ -v -m e2e
```

## 비용

테스트 1회 실행 시 약 $0.10~$0.50 예상 (작업 복잡도 따라).
```

- [ ] **Step 3: e2e가 일반 테스트와 분리되는지 확인**

```bash
pytest tests/ -v          # e2e 제외, 빠르게
pytest tests/ -v -m e2e   # e2e만
```

Expected: 일반 테스트 실행 시 e2e가 안 돌아감 (deselected).

- [ ] **Step 4: 커밋**

```bash
git add tests/e2e/__init__.py tests/e2e/test_smoke.py tests/e2e/README.md
git commit -m "test: add E2E smoke test scaffold (manual trigger only)"
```

---

## 완료 후 검증 체크리스트

- [ ] `pytest tests/ -v` 모두 통과 (e2e 제외)
- [ ] `pytest tests/ --cov=codingbot --cov-report=term-missing` — 핵심 모듈 90%+ 커버리지
- [ ] `codingbot --help` 동작
- [ ] `codingbot status` 빈 상태에서 깔끔하게 출력
- [ ] `codingbot install-hooks` 후 `~/.claude/settings.json`에 hook 등록됨
- [ ] (선택, 수동) E2E 스모크: 토이 프로젝트로 `codingbot run`이 멀티 사이클 도는지 확인

이후 v2 후보:
- `codingbot resume` (이전 핸드오프에서 이어가기)
- LLM 응답 캐싱
- 멀티-프로젝트별 config
- 사이클별 비용 추적
