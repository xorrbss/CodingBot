# CodingBot 0.6.0 — `status --watch` (S 사이클)

릴리스 일자: 2026-05-01
사이클 가치: **S — 운영 가시성 (한 화면에서 라이브로 본다)**
베이스: `v0.5.0` (`24f6cd1`)

## 무엇이 바뀌나

운영 코드 변경은 1파일 (`codingbot/cli.py`) — 신규 헬퍼/함수 + status subparser 옵션 3개. 외부 인터페이스는 옵션 추가만 (모두 미지정 시 0.5.0 동작 동일).

- **`codingbot status --watch`**: 화면을 주기적으로 클리어하고 기존 status 출력 + 최근 log 라인을 다시 그린다. Ctrl-C로 종료 (rc 0).
- **`--interval N`** (default 1): 갱신 주기(초).
- **`--tail N`** (default 10): 하단에 표시할 최근 log 줄 수.
- 화면 헤더: `--- CodingBot Status (refresh Ns) --- YYYY-MM-DD HH:MM:SS ---`. body는 0.3.0~0.5.0의 5개 status 섹션 그대로.
- `=== Last log ===` 섹션이 body 아래 추가 — `paths.log_file()` 마지막 N줄.

## 내부 변경

- `codingbot/cli.py`:
  - `_print_status_body()` 분리 — 기존 `_cmd_status` body의 print 블록.
  - `_read_log_tail(n) -> List[str]` 신규 — log.jsonl 마지막 n줄 (없으면 빈 리스트).
  - `_watch_status(args) -> int` 신규 — `os.system("cls"/"clear")` + 헤더 + body + log tail + `time.sleep(interval)` 루프. KeyboardInterrupt → rc 0.
  - `_cmd_status`: `args.watch`면 `_watch_status` 위임, 아니면 1회 출력.
  - `status` subparser에 `--watch / --interval / --tail` 옵션 3 추가.
- 137 → 193 LOC.

## 호환성

- public API breaking change 없음. `_cmd_status` 시그니처 동일. 기존 `codingbot status` (인자 없음) 동작 비트 동일.
- state.json schema, log 포맷, 의존 그래프 변경 없음.
- 신규 import는 stdlib (`os`, `time`, `datetime`)만.

## 테스트

- 0.5.0의 198 pass + 1 skipped → 0.6.0에서 **202 pass + 1 skipped** (+4).
- 신규 단위 4: `_read_log_tail` 정상/파일없음 2 + watch 루프 1회 실행 (`time.sleep` → KeyboardInterrupt patch) 2.

## 다음 후보 (0.7.0)

- risky_tool 차단 e2e (secret/install/priv 분기 hook 트랙).
- judge 캐싱 (B2): 0.3.0 카운터로 ROI 평가 후.
- abnormal exit 카운터 + S9 시나리오.
- metrics export (E), 배포 (D).
- watch 화면 lock pid 표시 / README 갱신.
