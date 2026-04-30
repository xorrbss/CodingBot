# CodingBot 0.1.1 Release Notes

- 상태: 로컬 태그 완료 (push는 사용자 승인 게이트)
- 베이스: `v0.1.0` (commit `8ac96f1`)
- 대상: 0.1.0 출시 직후 polish 5건 (모두 호환성 유지, 사용자 영향 미미)
- 결정: I-4/I-5 transcript 정공법은 실제 JSONL 샘플 확보 필요 → **0.1.2로 이월**

## 요약

내부 구조 polish 위주. 사용자 워크플로우는 변경 없음. 단, `codingbot run` 종료 코드가 의미 있는 값으로 채워지므로 CI/스크립트 통합 시 활용 가능.

## 변경

### 개선

- **`runner.run()` 의미 있는 종료 코드 (`M-5`, `7f80344`)** — `codingbot run`이 이제 `0` (정상), `1` (락 충돌), `2` (Claude Code 연속 비정상 종료) 중 하나를 반환. CLI에서 그대로 전파됨. 이전엔 항상 `0`.
- **PreToolUse hook 응답성 개선 (`I-3`, `cf4c3ef`)** — `config.load()`에 `@lru_cache(maxsize=1)` 적용. 같은 hook subprocess 안에서 YAML 재파싱 비용 제거. (참고: 0.1.0 직전 `I-1` lazy import와 합쳐 hook 11/11 ~180s → ~28s.)

### 수정

- **카운터 동시성 버그 (`I-2`, `57a6c90`)** — `state.record_cycle / record_auto_approve / record_auto_continue`이 락 안 read-modify-write로 동작. 이전엔 `read()` 후 `write()` 사이에 다른 hook이 끼어들면 카운트 손실 가능.

### 리팩토링 (사용자 영향 없음)

- **`auto_approve._skip` → `_defer_to_user` (`M-11`, `a6575f1`)** — private helper rename. "skip"이 부정확한 표현이었음 (자동 승인 안 하고 사용자에게 묻는 것이 의도). 로그 이벤트도 `auto_skip` → `auto_defer_to_user`.

### Chore

- **`.heartbeat` 추적 해제 (`051eb37`)** — 원래 `4bafda5` initial commit에 잘못 포함되어 있던 런타임 상태 파일을 `.gitignore`로 옮김. 첫 원격 push 전 BLOCKER였음. 워킹 트리 사본은 유지되므로 기존 사용자 영향 없음.

### 문서

- spec 문서(`docs/superpowers/specs/2026-04-30-codingbot-design.md`) 0.1.0 이후 인터페이스 drift 6건 반영 (runner exit code, `_increment`, `lru_cache`, lazy import, transcript TODO[BLOCKED], 에러 핸들링 표).

## 알려진 이슈 (이월)

- **`I-5` transcript schema 추정** (`8ac96f1`에서 BLOCKED 표시) — 실제 Claude Code session JSONL 샘플 1건 확보 후 `0.1.x`에서 정공법 재구성 예정.
- **`I-4` `last_assistant_text` 메모리 로딩** — 큰 transcript에서 비효율. `I-5`와 함께 tail-style 읽기로 전환 예정.

## 호환성

- public API breaking change 없음
- `codingbot run` 종료 코드 의미 추가 — `0`만 보던 스크립트는 영향 없음

## 테스트

- 87/87 pass (이전 85 + `M-5` 회귀 방지 2건)
- e2e는 여전히 manual trigger only (`-m e2e`)

## 출시 체크리스트

- [x] `I-5 + I-4` 정공법 처리 여부 결정 — 0.1.2로 이월 (외부 샘플 필요)
- [x] `pyproject.toml` `version = "0.1.1"` bump
- [x] `git tag -a v0.1.1 -m "v0.1.1: post-ship polish"`
- [x] 본 문서를 `docs/release-notes-0.1.1.md`로 확정 (draft 표시 제거)
- [ ] 원격 설정되어 있다면 `git push --tags` — **사용자 승인 게이트** (`docs/push-procedure.md` 참고)
