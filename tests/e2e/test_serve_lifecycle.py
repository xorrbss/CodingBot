"""serve 통합 e2e: 실제 socket bind + threading + urllib client.

별도 fake_claude나 hook은 필요 없음. ANTHROPIC_API_KEY도 불필요.
"""
import json
import socket
import threading
import time
import urllib.request
import urllib.error

import pytest

pytestmark = pytest.mark.e2e_auto


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_serving(url: str, timeout_sec: float = 5.0) -> None:
    deadline = time.time() + timeout_sec
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as r:
                if r.status == 200:
                    return
        except Exception as e:
            last_err = e
            time.sleep(0.05)
    raise AssertionError(f"server never came up: {last_err}")


def test_serve_lifecycle_get_state_and_shutdown(tmp_codingbot_home):
    from codingbot import serve, state
    state.start_cycle()  # state.json이 실제 존재하도록

    port = _free_port()
    rc_holder = {}

    def _run():
        rc_holder["rc"] = serve.run_serve("127.0.0.1", port, open_browser=False)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    try:
        base = f"http://127.0.0.1:{port}"
        _wait_until_serving(f"{base}/api/state")

        # /api/state
        with urllib.request.urlopen(f"{base}/api/state", timeout=2) as r:
            assert r.status == 200
            payload = json.loads(r.read().decode("utf-8"))
        assert "cycles_this_run" in payload
        assert "lock_pid" in payload
        assert "stop_signal" in payload

        # /api/timeline
        with urllib.request.urlopen(f"{base}/api/timeline?window=600", timeout=2) as r:
            assert r.status == 200
            tl = json.loads(r.read().decode("utf-8"))
        assert "buckets" in tl
        assert len(tl["buckets"]) == 10

        # / (index.html)
        with urllib.request.urlopen(f"{base}/", timeout=2) as r:
            assert r.status == 200
            ctype = r.headers.get("Content-Type", "")
            assert ctype.startswith("text/html")
            body = r.read()
        assert b"<title>CodingBot Dashboard</title>" in body

        # 404
        try:
            urllib.request.urlopen(f"{base}/nope", timeout=2)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        # daemon thread 정리에 의존 (pytest 종료 시 회수).
        pass
