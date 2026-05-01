"""로컬 read-only 웹 대시보드.

데이터 소스: state.json + log.jsonl (read-only).
의존: stdlib만.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from codingbot import paths

# log.jsonl event 분류
_JUDGE_LLM_EVENTS = {"auto_approve", "auto_defer_to_user", "stop_hook"}


def _parse_ts(s: str) -> Optional[datetime]:
    """ISO8601(Z) → aware datetime. 실패 또는 tz 없으면 None."""
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        return None
    return dt


def _compute_timeline(window_sec: int, bucket_sec: int = 60) -> List[dict]:
    """`log.jsonl`을 한 번 read해서 judge 메트릭을 시간 bucket으로 집계.

    반환: `[{"t": iso8601, "judge_call": int, "judge_timeout": int, "judge_error": int}, ...]`
    bucket 수 = window_sec // bucket_sec. 빈 bucket도 0으로 채움.
    오래된 라인 / 깨진 라인 / log 파일 부재 모두 안전.
    반환 dict의 "t"는 bucket의 종료 시각 (right edge).
    """
    n_buckets = window_sec // bucket_sec
    now = datetime.now(timezone.utc)
    # bucket[i]는 [now - (n_buckets-i)*bucket_sec, now - (n_buckets-i-1)*bucket_sec)
    buckets = [
        {
            "t": (now - timedelta(seconds=(n_buckets - i - 1) * bucket_sec)).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "judge_call": 0,
            "judge_timeout": 0,
            "judge_error": 0,
        }
        for i in range(n_buckets)
    ]

    p = paths.log_file()
    if not p.exists():
        return buckets

    cutoff = now - timedelta(seconds=window_sec)
    for raw in p.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(raw)
        except (ValueError, TypeError):
            continue
        ts = _parse_ts(rec.get("ts", ""))
        if ts is None or ts < cutoff:
            continue
        # bucket index: 가장 오래된 = 0, 가장 최근 = n_buckets-1
        delta = (now - ts).total_seconds()
        idx = n_buckets - 1 - int(delta // bucket_sec)
        if idx < 0 or idx >= n_buckets:
            continue
        event = rec.get("event")
        if event in _JUDGE_LLM_EVENTS and rec.get("judge") == "llm":
            buckets[idx]["judge_call"] += 1
        elif event == "llm_timeout":
            buckets[idx]["judge_timeout"] += 1
        elif event == "llm_api_error":
            buckets[idx]["judge_error"] += 1

    return buckets
