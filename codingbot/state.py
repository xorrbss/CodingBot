"""state.json 관리 + 정지 조건 검사."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import portalocker

from codingbot import config, logger, paths


def _initial_state() -> Dict[str, Any]:
    return {
        "cycle_started_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "cycles_this_run": 0,
        # 기존 (0.1.x 호환)
        "auto_approve_count": 0,
        "auto_continue_count": 0,
        # 0.3.0 신규: PreToolUse decision source
        "auto_approve_by_heuristic": 0,
        "auto_approve_by_llm": 0,
        "auto_defer_by_rule": 0,
        "auto_defer_by_heuristic": 0,
        "auto_defer_by_llm": 0,
        # 0.3.0 신규: Stop hook outcome
        "stop_block_continue": 0,
        "stop_block_handoff": 0,
        "stop_block_unstuck": 0,
        "stop_allow": 0,
        # 0.3.0 신규: judge call telemetry
        "judge_call_total": 0,
        "judge_timeout_total": 0,
        "judge_error_total": 0,
    }


def _read_unlocked(state_path: Path) -> Dict[str, Any]:
    if not state_path.exists():
        return _initial_state()
    try:
        with state_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warn("state_corrupt", error=str(e), fallback="reset")
        return _initial_state()


def _write_unlocked(state_path: Path, s: Dict[str, Any]) -> None:
    with state_path.open("w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def read() -> Dict[str, Any]:
    """state.json 읽기. 누락/손상 시 초기 상태 반환."""
    return _read_unlocked(paths.state_file())


def write(s: Dict[str, Any]) -> None:
    """state.json 쓰기 (락 보호)."""
    paths.ensure_home()
    state_path = paths.state_file()
    with portalocker.Lock(str(state_path) + ".lock", timeout=5):
        _write_unlocked(state_path, s)


def start_cycle() -> None:
    """새 자동화 실행 시작. 카운터 리셋."""
    write(_initial_state())


def _increment(key: str) -> None:
    """카운터를 락 안에서 read-modify-write. 동시 실행 시 카운트 손실 방지."""
    paths.ensure_home()
    state_path = paths.state_file()
    with portalocker.Lock(str(state_path) + ".lock", timeout=5):
        s = _read_unlocked(state_path)
        s[key] = s.get(key, 0) + 1
        _write_unlocked(state_path, s)


def record_cycle() -> None:
    _increment("cycles_this_run")


def record_auto_approve() -> None:
    _increment("auto_approve_count")


def record_auto_continue() -> None:
    _increment("auto_continue_count")


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

    started_at = s.get("cycle_started_at")
    if started_at:
        try:
            started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            elapsed_min = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
            if elapsed_min >= cfg.time_limit_minutes:
                return True
        except ValueError:
            pass

    if s.get("cycles_this_run", 0) >= cfg.max_cycles_per_run:
        return True

    return False
