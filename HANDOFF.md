# CodingBot 개발 핸드오프

**작성일**: 2026-04-30 (3rd update — 0.1.0 ship + post-ship polish)
**대상**: 다음 작업 세션

---

## (a) 지금까지 한 일

### 0.1.0 출시 완료

- 로컬 태그 `v0.1.0` 생성됨 (annotated, commit `8ac96f1`)
- 원격(remote) 미설정 → push는 다음 단계
- pyproject 버전 `0.1.0` (변경 없음)

### Final review 권장 수정 2건 (0.1.0 직전)

| ID | 내용 | 커밋 |
|---|---|---|
| I-1 | `import anthropic` lazy → `_client()` 내부 | `e867dc7` |
| I-5 | transcript schema mismatch — `TODO: [BLOCKED]`로 명시 | `8ac96f1` |

I-1 효과: hook tests 11/11 ~180s → 28s (6배), 풀 suite timeout 4건 사라짐.
I-5 결정: 실제 transcript 샘플 없는 상태에서 schema 추정 구현은 CLAUDE.md
"가정 금지" + "편법 금지" 위반 → 옵션 (b) 정공법 (TODO[BLOCKED] + 0.1.1로 미룸).

### 0.1.0 이후 polish 4건 (이번 세션)

| ID | 내용 | 커밋 |
|---|---|---|
| M-11 | `auto_approve._skip` → `_defer_to_user` rename | `a6575f1` |
| I-3 | `config.load` `@lru_cache(maxsize=1)` + conftest cache_clear | `cf4c3ef` |
| I-2 | `state.record_*` 락 안 read-modify-write (`_increment` 헬퍼) | `57a6c90` |
| M-5 | `runner.run() -> int`, CLI에서 그대로 전파 (테스트 +2건) | `7f80344` |

### Git history (HEAD 기준)

```
7f80344 fix(runner,cli): propagate runner exit code to CLI (M-5)
57a6c90 fix(state): atomic read-modify-write for record_* counters (I-2)
cf4c3ef perf(config): lru_cache config.load for hook hot path (I-3)
a6575f1 refactor(auto_approve): rename _skip to _defer_to_user (M-11)
8ac96f1 docs(transcript): mark schema mismatch as TODO[BLOCKED]   ← v0.1.0 태그
e867dc7 perf(llm_judge): lazy-import anthropic SDK inside _client()
99cbe38 docs: update handoff for tasks 9-15 + final review
... (이전 9 commits, 출시 직전 작업)
```

### 테스트 현황

- **87/87 pass in ~36s** (이전 85 + M-5 회귀 방지 2건)
- 풀 suite 단일 배치 실행에서 timeout 사라짐 (I-1 효과)
- e2e는 여전히 manual trigger only (`-m e2e`)

---

## (b) 다음에 할 일

### 0.1.1 출시 시 (권장)

1. **I-4 + I-5 묶어서 처리** — 두 항목 모두 `transcript.py` 수정. 분리하면 작업 중복.
   - I-5: 실제 Claude Code session JSONL 1건 확보 → 정확한 스키마 확인
     → `iter_messages()`/`last_assistant_text()` 재구성 + fixture 갱신
   - I-4: 같은 작업에서 `last_assistant_text`를 tail-style 읽기로 전환
     (현재는 전체 파일 메모리 로딩 — 큰 transcript에서 비효율)
   - **차단 요인**: 실제 transcript 샘플 1건. 사용자 환경에서 확보 필요.

2. **버전 bump**: `pyproject.toml` `version = "0.1.1"` + `git tag v0.1.1`

### 원격 push (사용자 결정)

- 현재 `git remote` 비어있음
- GitHub/GitLab 등 origin 설정 시 `git push -u origin master --tags` 필요
- (push는 공유 상태 변경이므로 명시적 사용자 승인 필요)

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
- `.heartbeat` 파일은 런타임 상태 — 코드 커밋에 절대 섞지 말 것

### 아키텍처 핵심 (변하지 않음)

- Hooks(PreToolUse + Stop) + shell-loop runner
- LLM 위험도 판단 + 휴리스틱 화이트/블랙리스트
- 사이클간 컨텍스트 초기화는 핸드오프 문서로
- Final check + 정지 조건 (stop signal / 30분 / 50회)

### 이번 세션에서 변경된 인터페이스

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

### 테스트 격리 패턴 (업데이트)

- `tests/conftest.py`의 `tmp_codingbot_home` fixture가:
  - `CODINGBOT_HOME` env 격리
  - **NEW**: `config.load.cache_clear()` 호출 — 이전 테스트의 캐시 무효화
- Hook 테스트는 subprocess 기반. `_run_hook` helper에 `timeout=60`
- I-1 적용 후 hook 테스트가 빨라져 timeout 여유 충분

### TODO[BLOCKED] 위치 (현재 1건)

- `codingbot/transcript.py` 상단 docstring — I-5 schema mismatch.
  실제 샘플 확보 후 0.1.1에서 해소.

### 참고 위치

- spec: `docs/superpowers/specs/2026-04-30-codingbot-design.md`
- plan: `docs/superpowers/plans/2026-04-30-codingbot.md`
- README: 사용자 문서 (변경 불필요)

---

## 이어가는 방법

다음 세션 시작 시:

> "이전 세션에서 CodingBot 0.1.0 로컬 태그됨. final review I-1/I-5 + polish 4건
> (M-11/I-3/I-2/M-5) 모두 반영. 87/87 green. 남은 건 I-4+I-5 정공법 (실제
> transcript 샘플 필요)과 원격 push. 어디부터 갈까요?"

사용자가 transcript 샘플 제공 가능 → I-5+I-4 정공법 진행.
샘플 없으면 → 원격 설정/push 또는 0.1.1 release notes 준비 등 다른 작업.
