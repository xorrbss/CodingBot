"""JSONL 형식 감사 로그. 디스크 실패에 안전 (예외 삼킴)."""
import json
import sys
from datetime import datetime, timezone
from typing import Any

from codingbot import paths


def log(_level: str, _event: str, **fields: Any) -> None:
    """단일 이벤트를 log.jsonl에 한 줄 append. 실패해도 예외 안 던짐."""
    record = {
        **fields,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "level": _level,
        "event": _event,
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
