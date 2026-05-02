# CodingBot 0.9.0

## What's new

- **`judge_enabled` flag — judge OFF 모드 (P 사이클: privacy/cost)** — Anthropic API 호출을 0건으로 운영할 수 있는 옵션. `~/.codingbot/config.yaml`에 `judge_enabled: false` 설정 시 `llm_judge._call`이 `_client()` 호출 없이 즉시 `JudgeError("judge disabled by config")` raise. 기존 hook fallback 경로(S6/S7/S8 회귀로 검증된 `_defer_to_user`/`_allow_stop`)가 안전 처리.
  - PreToolUse: heuristic 미매치(unknown) 도구 호출은 매번 사용자에게 위임
  - Stop: heuristic 미매치는 정상 종료 허용
  - 카운터(`judge_call_total`/`judge_timeout_total`/`judge_error_total`)는 호출되지 않으므로 0 유지
  - `ANTHROPIC_API_KEY` 환경변수 부재해도 정상 동작

## Compatibility

- 운영 코드 변경 = `codingbot/config.py` (+1 필드, +1 whitelist 항목) + `codingbot/llm_judge.py` (+3 라인 short-circuit). 합계 ~5 LOC.
- `judge_enabled` 미지정 시 default `True` → 0.8.0 동작 100% 보존.
- public API breaking change 없음. 기존 명령·schema·로그 포맷 동일.

## Notes

- 신규 회귀 +4: `test_config.py` 2건 (default True / yaml override), `test_llm_judge.py` 2건 (`evaluate_tool_safety`/`classify` 모두 `_client` 미호출 + `JudgeError` raise).
- 풀 테스트: 240 pass + 1 skipped (0.8.0 236 → +4).
- BLOCKED 0, LOC max 338(`tests/unit/test_heuristics.py`) 유지.
- 비범위(별도 사이클 후보): CLI judge 교체(`claude -p` 기반 — 19th update에서 17~35s startup overhead로 비현실적 판정), judge 응답 캐싱, abnormal exit + S14.
