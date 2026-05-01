# CodingBot 0.5.0 — hook 통합 e2e 사이클

릴리스 일자: 2026-05-01
사이클 가치: **C2 — 검증 자동화 (hook 분기까지 확장)**
베이스: `v0.4.0` (`5c5d961`)

## 무엇이 바뀌나

운영 코드 변경은 1파일 (`codingbot/llm_judge.py`)에 4라인 분기 추가뿐. 외부 인터페이스 변경 없음. 나머지는 테스트 인프라 확장.

- **`llm_judge._call` fault-inject 분기**: env `CODINGBOT_FAULT_INJECT ∈ {judge_timeout, judge_error}` 설정 시 즉시 해당 예외 raise. 미설정이면 동작 100% 동일.
- **`tests/e2e/conftest.py`**: `transcript_jsonl_factory`, `hook_env` fixture 추가.
- **`tests/e2e/hook_harness.py`** (신규): `HookResult` dataclass + `run_pre_tool_use` / `run_stop_hook` — 진짜 hook subprocess (`sys.executable -m codingbot.hooks.X`).
- **`tests/e2e/test_hook_integration.py`** (신규): 4 시나리오
  - S5: stop signal 활성 → Stop hook `_allow_stop`
  - S6: ambiguous tool + judge timeout → PreToolUse `_defer_to_user`
  - S7: heuristic 미매치 + judge timeout → Stop hook `_allow_stop("llm_timeout")`
  - S8: heuristic 미매치 + judge error → Stop hook `_allow_stop("llm_failed")`
- **`tests/e2e/test_runner_loop.py`**: S4 추가 — 연속 abnormal exit → exit 2.
- **`tests/unit/test_llm_judge.py`**: fault-inject 단위 회귀 3건.

## 호환성

- public API breaking change 없음. `JudgeError`, `JudgeTimeout` 동일.
- env `CODINGBOT_FAULT_INJECT` 미설정 시 prod 동작 0.4.0과 비트 동일.
- state.json schema 변경 없음.
- 의존 그래프 변경 없음.

## 테스트

- 0.4.0의 182 pass + 1 skipped → 0.5.0에서 **198 pass + 1 skipped** (+16).
- e2e_auto 19건 PASS, wall time ~31초 (< 60초).

## 다음 후보 (0.6.0)

- risky_tool 차단 e2e (secret/install/priv 분기 hook 트랙).
- judge 캐싱 (B2): 0.3.0 카운터로 ROI 평가 후.
- metrics export (E), 배포 (D).
- abnormal exit 카운터 도입 (state.json schema 확장).
