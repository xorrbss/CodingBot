"""로컬 read-only 웹 대시보드.

데이터 소스: state.json + log.jsonl (read-only).
의존: stdlib만.
"""
import json
import re
import sys
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from codingbot import paths, state

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


def _read_lock_pid() -> Optional[int]:
    """`paths.lock_file()` 의 PID를 int로. 부재 또는 비숫자면 None."""
    p = paths.lock_file()
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _read_stop_signal() -> bool:
    """`paths.stop_signal_file()` 존재 여부."""
    return paths.stop_signal_file().exists()


_STATIC_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _read_log_tail_lines(n: int) -> List[str]:
    p = paths.log_file()
    if not p.exists() or n <= 0:
        return []
    return p.read_text(encoding="utf-8").splitlines()[-n:]


def _load_static(name: str) -> Optional[bytes]:
    if not _STATIC_NAME_RE.match(name) or name in (".", ".."):
        return None
    target = files("codingbot.static") / name
    if not target.is_file():
        return None
    return target.read_bytes()


def _content_type_for(name: str) -> str:
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    return "application/octet-stream"


def _payload_state() -> bytes:
    s = state.read()
    enriched = {
        **s,
        "lock_pid": _read_lock_pid(),
        "stop_signal": _read_stop_signal(),
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    return json.dumps(enriched, ensure_ascii=False).encode("utf-8")


def _payload_log_tail(n: int) -> bytes:
    return json.dumps({"lines": _read_log_tail_lines(n)}, ensure_ascii=False).encode("utf-8")


def _payload_timeline(window_sec: int) -> bytes:
    return json.dumps(
        {"buckets": _compute_timeline(window_sec=window_sec, bucket_sec=60)},
        ensure_ascii=False,
    ).encode("utf-8")


def _route(method: str, path: str) -> Tuple[int, str, bytes]:
    """순수 라우팅 함수. (status, content_type, body) 반환."""
    if method != "GET":
        return 405, "text/plain; charset=utf-8", b"method not allowed"

    parsed = urlparse(path)
    p = parsed.path
    qs = parse_qs(parsed.query)

    if p == "/":
        body = _load_static("index.html") or b""
        if not body:
            return 404, "text/plain; charset=utf-8", b"index not found"
        return 200, _content_type_for("index.html"), body

    if p.startswith("/static/"):
        name = p[len("/static/"):]
        body = _load_static(name)
        if body is None:
            return 404, "text/plain; charset=utf-8", b"not found"
        return 200, _content_type_for(name), body

    if p == "/api/state":
        return 200, "application/json", _payload_state()

    if p == "/api/log/tail":
        try:
            n = int(qs.get("n", ["50"])[0])
        except ValueError:
            n = 50
        return 200, "application/json", _payload_log_tail(n)

    if p == "/api/timeline":
        try:
            window = int(qs.get("window", ["1800"])[0])
        except ValueError:
            window = 1800
        return 200, "application/json", _payload_timeline(window)

    return 404, "text/plain; charset=utf-8", b"not found"


class _Handler(BaseHTTPRequestHandler):
    """라우팅은 순수 함수 _route에 위임. 이 클래스는 응답 write만 한다."""

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        status, ctype, body = _route("GET", self.path)
        self._respond(status, ctype, body)

    def do_POST(self) -> None:  # noqa: N802
        status, ctype, body = _route("POST", self.path)
        self._respond(status, ctype, body)

    def log_message(self, format, *args) -> None:  # noqa: A002
        # default는 stderr에 access log를 찍음. 운영자 콘솔이 시끄러워져 끔.
        return


def _open_browser(host: str, port: int) -> None:
    try:
        webbrowser.open(f"http://{host}:{port}/")
    except Exception:
        pass


def run_serve(host: str, port: int, open_browser: bool) -> int:
    """블로킹 모드로 서버 시작. Ctrl-C → 0. port 충돌 → 1."""
    try:
        server = ThreadingHTTPServer((host, port), _Handler)
    except OSError as e:
        print(f"[codingbot] cannot bind {host}:{port} — {e}", file=sys.stderr)
        return 1

    if open_browser:
        threading.Thread(target=_open_browser, args=(host, port), daemon=True).start()

    print(f"[codingbot] serving on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
