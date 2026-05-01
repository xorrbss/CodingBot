# CodingBot 0.4.0 — e2e 자동화 사이클

릴리스 일자: 2026-05-01
사이클 가치: **C — 검증 자동화**
베이스: `v0.3.0` (`e4196b8`)

## 무엇이 바뀌나

운영 코드(`codingbot/*`)는 변경 없음. 변경은 전부 테스트 인프라:

- **fake `claude` 바이너리** (`tests/e2e/fake_claude.py`) — 시나리오 JSON 기반, stdlib only.
- **fixture 2개** (`tests/e2e/conftest.py`):
  - `fake_claude_shim`: `monkeypatch.setattr("codingbot.runner.subprocess.run", ...)`로 `["claude", ...]` 호출만 fake로 라우팅. (PATH 기반 shim은 Windows PATHEXT가 `.exe`를 우선 매칭하는 문제로 폐기)
  - `e2e_scenario`: 시나리오 dict → JSON → `CODINGBOT_E2E_SCENARIO` env.
- **3 시나리오** (`tests/e2e/test_runner_loop.py`):
  - S1 happy_1_cycle — 초기 프롬프트 → final-check → 종료 (cycles=2)
  - S2 handoff_multi — handoff 작성 → 다음 사이클 처리 → final-check → 종료 (cycles=3)
  - S3 abnormal_recover — exit 2 → continue → 정상 → final-check → 종료 (cycles=3)
- **fake_claude 단위 회귀 3건** (`tests/e2e/test_fake_claude.py`).
- **새 마커 `e2e_auto`** — 자동, 무료, 기본 수집. 기존 `e2e` (manual, $) 유지.

## 호환성

- public API breaking change 없음.
- `state.json` schema 변경 없음.
- 의존 그래프 변경 없음.
- 운영 코드(`codingbot/*`) **무수정** (`git diff v0.3.0..v0.4.0 -- codingbot/` 빈 diff).

## 테스트

- 0.3.0의 176 pass + 1 skipped → 0.4.0에서 182 pass + 1 skipped (+6).
- e2e_auto 6건 합산 wall time < 30초.

## 다음 후보 (0.5.0)

- transcript JSONL 시뮬레이션으로 hook 분기까지 통합 e2e.
- S4(연속 abnormal 2회 → exit 2), S5(stop signal), JudgeTimeout 분기.
- judge 캐싱, metrics export, 배포(D).
