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


def test_route_root_returns_index_html(tmp_codingbot_home):
    from codingbot import serve
    status, ctype, body = serve._route("GET", "/")
    assert status == 200
    assert ctype.startswith("text/html")
    # placeholder든 본문이든 비지 않음
    assert len(body) > 0


def test_route_static_index_html(tmp_codingbot_home):
    from codingbot import serve
    status, ctype, body = serve._route("GET", "/static/index.html")
    assert status == 200
    assert ctype.startswith("text/html")


def test_route_static_path_traversal_blocked(tmp_codingbot_home):
    from codingbot import serve
    status, _, _ = serve._route("GET", "/static/../../etc/passwd")
    assert status == 404


def test_route_static_unknown_file_returns_404(tmp_codingbot_home):
    from codingbot import serve
    status, _, _ = serve._route("GET", "/static/does-not-exist.css")
    assert status == 404


def test_route_api_state_returns_json(tmp_codingbot_home):
    from codingbot import state, serve
    state.start_cycle()
    status, ctype, body = serve._route("GET", "/api/state")
    assert status == 200
    assert ctype == "application/json"
    payload = json.loads(body.decode("utf-8"))
    # 0.6.0 카운터 키 일부 포함
    assert "cycles_this_run" in payload
    assert "judge_call_total" in payload
    # serve가 덧붙이는 키
    assert "lock_pid" in payload
    assert "stop_signal" in payload
    assert "ts" in payload


def test_route_api_log_tail_returns_lines(tmp_codingbot_home):
    from codingbot import serve
    paths.log_file().write_text(
        '{"event":"a"}\n{"event":"b"}\n{"event":"c"}\n', encoding="utf-8"
    )
    status, ctype, body = serve._route("GET", "/api/log/tail?n=2")
    assert status == 200
    assert ctype == "application/json"
    payload = json.loads(body.decode("utf-8"))
    assert payload["lines"] == ['{"event":"b"}', '{"event":"c"}']


def test_route_api_log_tail_default_n(tmp_codingbot_home):
    from codingbot import serve
    paths.log_file().write_text("\n".join(f'{{"i":{i}}}' for i in range(80)) + "\n", encoding="utf-8")
    status, _, body = serve._route("GET", "/api/log/tail")
    payload = json.loads(body.decode("utf-8"))
    # default n = 50
    assert len(payload["lines"]) == 50


def test_route_api_timeline_default_window(tmp_codingbot_home):
    from codingbot import serve
    status, ctype, body = serve._route("GET", "/api/timeline")
    assert status == 200
    assert ctype == "application/json"
    payload = json.loads(body.decode("utf-8"))
    # default window 1800s, bucket 60s = 30
    assert "buckets" in payload
    assert len(payload["buckets"]) == 30


def test_route_unknown_path_404(tmp_codingbot_home):
    from codingbot import serve
    status, _, _ = serve._route("GET", "/nope")
    assert status == 404


def test_route_non_get_returns_405(tmp_codingbot_home):
    from codingbot import serve
    status, _, _ = serve._route("POST", "/api/state")
    assert status == 405


def test_route_static_dotdot_returns_404(tmp_codingbot_home):
    """`/static/..` (단일 토큰)는 명시적으로 404."""
    from codingbot import serve
    status, _, _ = serve._route("GET", "/static/..")
    assert status == 404
    status, _, _ = serve._route("GET", "/static/.")
    assert status == 404


def test_read_log_tail_lines_zero_returns_empty(tmp_codingbot_home):
    """n<=0이면 빈 리스트 (`[-0:]` 가 전체 반환되는 함정 회피)."""
    from codingbot import serve
    paths.log_file().write_text("a\nb\nc\n", encoding="utf-8")
    assert serve._read_log_tail_lines(0) == []
    assert serve._read_log_tail_lines(-3) == []
