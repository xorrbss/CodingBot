# CodingBot 0.3.0 — 관측(metrics) 사이클

**Release date:** 2026-05-01
**Base:** v0.2.0

## 요약

0.2.0의 안전망(카테고리 분류, llm_judge timeout, runner CLI 검사)이 실제로
얼마나 발동하는지 가시화한다. 새 모듈/외부 의존/의존 그래프 변경 없음.

## 신규

- **state.json 카운터 12개 추가**:
  - PreToolUse decision source: `auto_approve_by_heuristic`, `auto_approve_by_llm`,
    `auto_defer_by_rule`, `auto_defer_by_heuristic`, `auto_defer_by_llm`
  - Stop hook outcome: `stop_block_continue`, `stop_block_handoff`,
    `stop_block_unstuck`, `stop_allow`
  - Judge call telemetry: `judge_call_total`, `judge_timeout_total`,
    `judge_error_total`
- **`JudgeTimeout` 예외 분리**: `JudgeError`의 서브클래스. `anthropic.APITimeoutError`를
  명시 매핑하여 timeout과 일반 API 실패 구분 가능. 기존 `except JudgeError`는 그대로 둘 다 catch.
- **`codingbot status` 출력 섹션화**: Status / Cycle / Decisions (PreToolUse) /
  Decisions (Stop) / Judge / Config 5개 섹션.

## 변경 (호환)

- `_approve` / `_defer_to_user`: 기존 `record_auto_approve` / `record_auto_continue`
  호출은 유지. 신규 source-별 카운터 호출이 *추가*됨.
- `auto_approve` / `handoff_or_continue` hook: judge 호출 직전에 `record_judge_call`,
  except 분기에서 `record_judge_timeout` / `record_judge_error` 추가.

## 비범위 (후속 사이클)

- e2e 자동 검증 골격 (0.4.x 후보)
- judge 캐싱 (0.3.0 측정 데이터로 ROI 평가 후 결정)
- 외부 metrics export / dashboard

## 게이트 통과

- 176 pass + 1 skipped, BLOCKED 0건
- 모든 파일 ≤ 500 LOC (max `heuristics.py` 282)
- 의존 그래프 변경 없음
- 외부 인터페이스 breaking change 없음
