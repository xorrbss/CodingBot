# CodingBot 0.7.0

## What's new

- **`codingbot serve`** — 로컬 read-only 웹 대시보드. 카운터, judge 시계열(30분/60s bucket), 최근 log 50줄, lock+stop alert를 한 화면에서 본다.
  - default `http://127.0.0.1:8723`. `--port`, `--host`, `--no-browser` 지원.
  - 의존 추가 0개 (stdlib `http.server` + vanilla HTML/JS/SVG).
  - 데이터 소스: 기존 `~/.codingbot/state.json` + `log.jsonl` 만 read.

## Compatibility

- 기존 명령(`run`, `stop`, `start`, `status`, `tail-log`, `install-hooks`, `uninstall-hooks`, `config`) 동작 동일.
- `status --watch` (0.6.0)는 그대로 동작. `serve`와 공존.
- state schema, log 포맷 변경 없음.

## Notes

- 인증/원격 노출 없음. `--host 0.0.0.0`은 사용자 책임.
- 모든 endpoint는 GET. 쓰기 API 없음.
