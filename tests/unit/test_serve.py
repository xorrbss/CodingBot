"""serve 모듈 단위 테스트."""
import json
from datetime import datetime, timedelta, timezone

from codingbot import paths


def _ts(offset_sec: int) -> str:
    """현재 UTC 기준 offset_sec(음수면 과거)의 ISO8601(Z) 문자열."""
    t = datetime.now(timezone.utc) + timedelta(seconds=offset_sec)
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def _line(event: str, **fields) -> str:
    offset = fields.pop("_offset", 0)
    record = {**fields, "ts": _ts(offset), "level": "info", "event": event}
    return json.dumps(record, ensure_ascii=False)


def test_compute_timeline_buckets_judge_events(tmp_codingbot_home):
    """judge=llm event(approve/defer/stop_hook)와 llm_timeout/llm_api_error를 60s bucket에 집계."""
    from codingbot import serve
    lines = [
        _line("auto_approve", judge="llm", reason="ok", _offset=-30),
        _line("auto_approve", judge="llm", reason="ok", _offset=-30),
        _line("auto_defer_to_user", judge="llm", reason="ask", _offset=-90),
        _line("stop_hook", judge="llm", outcome="continue", _offset=-150),
        _line("llm_timeout", _offset=-30),
        _line("llm_api_error", _offset=-90),
        _line("auto_approve", judge="heuristic", reason="safe", _offset=-30),  # heuristic은 제외
    ]
    paths.log_file().write_text("\n".join(lines) + "\n", encoding="utf-8")

    buckets = serve._compute_timeline(window_sec=300, bucket_sec=60)

    assert len(buckets) == 5  # 300/60
    # 마지막 bucket(=현재): approve 2 + timeout 1
    assert buckets[-1]["judge_call"] == 2
    assert buckets[-1]["judge_timeout"] == 1
    assert buckets[-1]["judge_error"] == 0
    # bucket[-2] (60~120s 전): defer 1 + api_error 1
    assert buckets[-2]["judge_call"] == 1
    assert buckets[-2]["judge_error"] == 1


def test_compute_timeline_ignores_old_lines(tmp_codingbot_home):
    from codingbot import serve
    # window 밖 (-1000s)
    paths.log_file().write_text(
        _line("auto_approve", judge="llm", _offset=-1000) + "\n", encoding="utf-8",
    )
    buckets = serve._compute_timeline(window_sec=300, bucket_sec=60)
    assert sum(b["judge_call"] for b in buckets) == 0


def test_compute_timeline_skips_malformed_lines(tmp_codingbot_home):
    from codingbot import serve
    paths.log_file().write_text(
        "not-json\n"
        + _line("auto_approve", judge="llm", _offset=-30) + "\n"
        + "{also bad\n",
        encoding="utf-8",
    )
    buckets = serve._compute_timeline(window_sec=120, bucket_sec=60)
    assert buckets[-1]["judge_call"] == 1


def test_compute_timeline_skips_naive_timestamp_lines(tmp_codingbot_home):
    """tz suffix 없는 ts는 잘못된 라인으로 간주하고 silently skip."""
    from codingbot import serve
    paths.log_file().write_text(
        '{"event":"auto_approve","judge":"llm","ts":"2024-01-01T00:00:00","level":"info"}\n'
        + _line("auto_approve", judge="llm", _offset=-30) + "\n",
        encoding="utf-8",
    )
    buckets = serve._compute_timeline(window_sec=120, bucket_sec=60)
    # 정상 라인 1개만 카운트, naive ts는 무시
    assert sum(b["judge_call"] for b in buckets) == 1
    assert buckets[-1]["judge_call"] == 1


def test_compute_timeline_empty_log(tmp_codingbot_home):
    from codingbot import serve
    # log 파일 자체가 없음
    assert not paths.log_file().exists()
    buckets = serve._compute_timeline(window_sec=180, bucket_sec=60)
    assert len(buckets) == 3
    assert all(b["judge_call"] == 0 and b["judge_timeout"] == 0 and b["judge_error"] == 0 for b in buckets)


def test_read_lock_pid_returns_int_when_file_exists(tmp_codingbot_home):
    from codingbot import serve
    paths.lock_file().write_text("13422", encoding="utf-8")
    assert serve._read_lock_pid() == 13422


def test_read_lock_pid_returns_none_when_missing(tmp_codingbot_home):
    from codingbot import serve
    assert serve._read_lock_pid() is None


def test_read_lock_pid_returns_none_for_corrupt_content(tmp_codingbot_home):
    from codingbot import serve
    paths.lock_file().write_text("not-a-pid", encoding="utf-8")
    assert serve._read_lock_pid() is None


def test_read_stop_signal_reflects_file_presence(tmp_codingbot_home):
    from codingbot import serve
    assert serve._read_stop_signal() is False
    paths.stop_signal_file().touch()
    assert serve._read_stop_signal() is True
