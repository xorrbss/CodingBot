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
