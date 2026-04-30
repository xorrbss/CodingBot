# CodingBot 개발 핸드오프

**작성일**: 2026-04-30 (4th update — 0.1.1 ship + spec drift 해소 + push procedure)
**대상**: 다음 작업 세션

---

## (a) 지금까지 한 일

### 0.1.1 출시 완료 (이번 세션)

- 로컬 annotated 태그 `v0.1.1` 생성됨 (commit `c2957db`)
- `pyproject.toml` `version = "0.1.1"`
- 원격(remote) 여전히 미설정 → push는 사용자 게이트 (`docs/push-procedure.md`)

### 이번 세션 작업 요약 (D → B → C → 추가)

| 단계 | 내용 | 산출 커밋 |
|---|---|---|
| D | spec drift 6건 패치 (runner exit code, state API 확장, lru_cache, transcript I-4/I-5 BLOCKED, lazy import, 에러 표) | `d5d811b` |
| B | `0.1.1` release notes 초안 작성 | `44b23d0` |
| C | 원격 push 절차 문서화 (`docs/push-procedure.md`) | `fbed975` |
| 후속 | `.heartbeat` 추적 해제 (initial commit에 잘못 포함되어 있던 런타임 파일) | `051eb37` |
| 후속 | push procedure / release notes에 `.heartbeat` 해소 반영 | `f291a74` |
| 출시 | `pyproject` 0.1.0→0.1.1 + release notes 확정 + `v0.1.1` 태그 | `c2957db` |

### 0.1.0 → 0.1.1에 포함된 변경 (히스토리 재확인용)

| ID | 내용 | 커밋 |
|---|---|---|
| M-11 | `auto_approve._skip` → `_defer_to_user` rename | `a6575f1` |
| I-3 | `config.load` `@lru_cache(maxsize=1)` + conftest cache_clear | `cf4c3ef` |
| I-2 | `state.record_*` 락 안 read-modify-write (`_increment` 헬퍼) | `57a6c90` |
| M-5 | `runner.run() -> int`, CLI에서 그대로 전파 | `7f80344` |
| chore | `.heartbeat` untrack | `051eb37` |

(0.1.0 직전 final review 항목 I-1/I-5는 `v0.1.0`에 포함됨)

### Git history (HEAD 기준)

```
c2957db release: 0.1.1                                          ← v0.1.1 tag
f291a74 docs: reflect .heartbeat untrack in push procedure + 0.1.1 notes
051eb37 chore: untrack .heartbeat runtime file
fbed975 docs: add push procedure for first remote setup
44b23d0 docs: add 0.1.1 release notes draft
d5d811b docs(spec): reflect 0.1.0 post-ship interface changes
c3fba70 docs(handoff): update for v0.1.0 ship + post-ship polish
7f80344 fix(runner,cli): propagate runner exit code to CLI (M-5)
57a6c90 fix(state): atomic read-modify-write for record_* counters (I-2)
cf4c3ef perf(config): lru_cache config.load for hook hot path (I-3)
a6575f1 refactor(auto_approve): rename _skip to _defer_to_user (M-11)
8ac96f1 docs(transcript): mark schema mismatch as TODO[BLOCKED]   ← v0.1.0 tag
e867dc7 perf(llm_judge): lazy-import anthropic SDK inside _client()
... (이전 commits)
```

### 테스트 현황

- **87/87 pass + 1 skipped** (이전 세션부터 변동 없음 — 이번 세션은 docs/release만 변경)
- e2e는 여전히 manual trigger only (`-m e2e`)

---

## (b) 다음에 할 일

### 0.1.2 후보 (현재 외부 입력 대기)

1. **I-4 + I-5 transcript 정공법** — 두 항목 모두 `transcript.py` 수정. 분리하면 작업 중복.
   - I-5: 실제 Claude Code session JSONL 1건 확보 → 정확한 스키마 확인
     → `iter_messages()`/`last_assistant_text()` 재구성 + fixture 갱신
   - I-4: 같은 작업에서 `last_assistant_text`를 tail-style 읽기로 전환
     (현재는 전체 파일 메모리 로딩 — 큰 transcript에서 비효율)
   - **차단 요인**: 실제 transcript 샘플 1건. 사용자 환경에서 확보 필요.

### 원격 push (사용자 결정)

- 현재 `git remote` 비어있음
- 절차/주의사항 모두 `docs/push-procedure.md`에 정리됨
- 사용자 명시 승인 후 실행:
  - origin URL 결정
  - 비밀/큰 바이너리 사전 점검
  - `git push -u origin master`
  - `git push origin v0.1.0 v0.1.1`

### 더 작은 polish (필요 시)

- 모두 0.1.x 범위에서 무리 없음. 우선순위 낮음.
- 현재 HEAD에서 `// TODO`, `# TODO` grep 시 I-5 BLOCKED 1건만 남아있음.

---

## (c) 새 세션이 알아야 할 중요 컨텍스트

### 환경 (변경 없음)

- Working dir: `C:/project/CodingBot`
- Windows 11. Git Bash
- Python: 3.11 (`py -m pytest`로 실행, `.venv` 없음)
- Git user: `CodingBot Dev <dev@codingbot.local>`
- `.heartbeat`은 이제 `.gitignore`에 등록되어 추적 안 됨 (커밋 `051eb37`).
  워킹 트리에는 남아있고 `codingbot run`이 갱신함.

### 아키텍처 핵심 (변하지 않음)

- Hooks(PreToolUse + Stop) + shell-loop runner
- LLM 위험도 판단 + 휴리스틱 화이트/블랙리스트
- 사이클간 컨텍스트 초기화는 핸드오프 문서로
- Final check + 정지 조건 (stop signal / 30분 / 50회)

### 0.1.0 이후 변경된 인터페이스 (spec에도 반영됨)

- `runner.run(prompt) -> int` (이전 None) — 0=정상, 1=락 충돌, 2=Claude 연속 비정상
- `state._increment(key)` 신규 (private). `record_*`는 모두 이걸 경유
- `config.load`에 `@lru_cache(maxsize=1)` — 테스트는 `tmp_codingbot_home`
  fixture가 자동으로 `cache_clear()` 호출
- `auto_approve._defer_to_user` (이전 `_skip`)
- `llm_judge.py`에서 `import anthropic`은 module top에서 사라지고
  `_client()` 안에 lazy. mock fixture(`mocker.patch("anthropic.Anthropic", ...)`)
  는 이름 기반 patch라 그대로 작동.

### 모듈 의존 그래프 (변경 없음)

```
paths            (leaf)
logger          → paths
config          → logger, paths
heuristics      → config
transcript      → logger
llm_judge       → config
state           → config, logger, paths
handoff         → paths
runner          → handoff, logger, paths, state
cli             → config, install_hooks, paths, runner, state
install_hooks   (leaf)
hooks/auto_approve         → heuristics, llm_judge, logger, state, transcript
hooks/handoff_or_continue  → handoff, heuristics, llm_judge, logger, state, transcript
```
모든 파일 ≤ 140 LOC

### 테스트 격리 패턴 (변경 없음)

- `tests/conftest.py`의 `tmp_codingbot_home` fixture가:
  - `CODINGBOT_HOME` env 격리
  - `config.load.cache_clear()` 호출 — 이전 테스트의 캐시 무효화
- Hook 테스트는 subprocess 기반. `_run_hook` helper에 `timeout=60`

### TODO[BLOCKED] 위치 (현재 1건)

- `codingbot/transcript.py` 상단 docstring — I-5 schema mismatch.
  실제 샘플 확보 후 **0.1.2**에서 해소 (이전 핸드오프는 0.1.1로 잡혀 있었음 — 외부 입력 못 받아 이월).

### 참고 위치

- spec: `docs/superpowers/specs/2026-04-30-codingbot-design.md` (0.1.0 이후 drift 반영됨)
- plan: `docs/superpowers/plans/2026-04-30-codingbot.md` (구현 체크리스트 — historical artifact, 갱신 안 함)
- release notes: `docs/release-notes-0.1.1.md`
- push procedure: `docs/push-procedure.md`
- README: 사용자 문서 (변경 불필요)

---

## 이어가는 방법

다음 세션 시작 시:

> "이전 세션에서 CodingBot **0.1.1** 로컬 태그됨 (`c2957db`). polish 4건 +
> `.heartbeat` untrack + spec/release-notes/push-procedure 문서 정비 완료.
> 87/87 green. 남은 건 I-4+I-5 정공법(실제 transcript 샘플 필요, 0.1.2 후보)과
> 원격 push (origin URL + 사용자 승인 필요). 어디부터 갈까요?"

사용자가 transcript 샘플 제공 가능 → I-5+I-4 정공법 진행 → 0.1.2 준비.
origin URL 제공 + push 승인 → `docs/push-procedure.md` 절차 실행.
둘 다 보류 → 더 작은 polish 후보 탐색 또는 e2e 수동 검증.
