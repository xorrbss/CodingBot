# CodingBot 개발 핸드오프

**작성일**: 2026-05-01 (6th update — 0.1.2 로컬 태그 완료)
**대상**: 다음 작업 세션

---

## (a) 지금까지 한 일

### 0.1.2 로컬 태그 완료

- `pyproject.toml` `version = "0.1.2"`
- 로컬 annotated 태그 `v0.1.2` 생성 (commit `<release-commit>`)
- **push는 미실행 — 사용자 승인 게이트**:
  - 현재 origin: `git@github.com:xorrbss/CodingBot.git`, master `fb449c8` (0.1.1 ship 후 HANDOFF 갱신까지 포함), tags `v0.1.0`/`v0.1.1`
  - 0.1.2 commits 4건(`91c1051`, `12ad542`, `cbb79e6`, `16e70f1`)과 `v0.1.2` 태그는 **로컬에만 존재**. push procedure는 `docs/push-procedure.md`.

### 이번 세션 작업 요약 (Unit-1 → Unit-2 → Unit-3)

| 단계 | 내용 | 산출 커밋 |
|---|---|---|
| Unit-1 (I-5) | transcript schema 정공법 재구성 + fixture 4개 갱신 + 실제 세션 fixture 신규 + 회귀 테스트 5건 + docstring TODO 제거 | `91c1051` |
| Unit-2 (I-4) | `last_assistant_text` tail-style 전환 (`_iter_lines_reverse` 64KB chunk 역방향) + 회귀 테스트 7건 | `12ad542` |
| Unit-3 (release draft) | `pyproject` 0.1.2 bump + release notes 0.1.2 draft + spec drift 정리 (§5.6 BLOCKED 해소 표시) | `cbb79e6` |
| Unit-3 (release finalize) | release notes draft 표시 제거, HANDOFF 갱신, 본 commit 위에 `v0.1.2` 태그 | (이 commit) |

### 0.1.1 → 0.1.2에 포함된 변경

| ID | 내용 | 커밋 |
|---|---|---|
| I-5 | transcript schema 정공법 (top-level `type`, `message.content` blocks) | `91c1051` |
| I-4 | `last_assistant_text` tail-style 64KB chunk 역방향 read | `12ad542` |
| release | pyproject 0.1.2 + release notes draft + spec drift 정리 | `cbb79e6` |

### Git history (HEAD 기준)

```
<release finalize>  release: 0.1.2 finalize (notes/handoff)         ← v0.1.2 tag
cbb79e6  release: 0.1.2 draft (transcript I-4/I-5 정공법)
12ad542  perf(transcript): tail-style read for last_assistant_text (I-4)
91c1051  fix(transcript): reconstruct iter_messages with real session schema (I-5)
fb449c8  docs(handoff): mark remote push completed
0247e27  docs(handoff): update for 0.1.1 ship + spec drift / push procedure / heartbeat untrack
c2957db  release: 0.1.1                                              ← v0.1.1 tag
... (이전 commits)
```

### 테스트 현황

- **99 pass + 1 skipped** (이전 87 + 회귀 12건: I-5 schema 5 + I-4 tail-style 7)
- e2e는 여전히 manual trigger only (`-m e2e`)
- `// TODO`, `# TODO` grep 시 코드 BLOCKED **0건**

---

## (b) 다음에 할 일

### 0.1.2 출시 마무리 (사용자 승인 게이트)

```bash
# 사전 점검
git status                   # clean working tree
git log v0.1.2 --no-patch -1 # tag 메시지 확인
git log origin/master..HEAD --oneline  # push 대상 확인 (4 commits)

# push (사용자 명시 승인 후)
git push origin master
git push origin v0.1.2
```

push 후 `docs/push-procedure.md` D 섹션의 사후 확인 수행.

### 0.1.x 추가 polish 후보 (우선순위 낮음)

- 현재 알려진 BLOCKED 0건. 무리 없이 0.1.x 범위 내.
- e2e 수동 검증 (실제 Claude Code run에서 hook 동작 확인 — 비용 발생).
- HANDOFF의 "지금까지 한 일" 항목이 누적되고 있어 0.2.0 시점에 archive 정리 검토.

---

## (c) 새 세션이 알아야 할 중요 컨텍스트

### 환경 (변경 없음)

- Working dir: `C:/project/CodingBot`
- Windows 11. Git Bash
- Python: 3.11 (`py -m pytest`로 실행, `.venv` 없음)
- Git user: `CodingBot Dev <dev@codingbot.local>`

### 0.1.2에서 변경된 인터페이스 (spec §5.6 반영됨)

- `transcript.iter_messages(path)` — 이제 실제 Claude Code session JSONL의 top-level `type` + `message.content` blocks 기반. `type ∈ {user, assistant}`만 yield. assistant는 `text` block만 join. thinking/tool_use only assistant, tool_result only user는 skip. 외부 인터페이스(`Message = {"role","content": str}`)는 유지.
- `transcript.last_assistant_text(path)` — 64KB chunk 역방향 read. 큰 transcript에서도 메모리 일정.
- 다운스트림(`auto_approve`, `handoff_or_continue`, `llm_judge`)은 코드 수정 0건.
- 이전 schema(`{"role","content":str}`) JSONL 파일은 더 이상 파싱 안 됨 (의도 — 실제 Claude Code 세션은 항상 새 schema).

### 0.1.0 이후 누적된 인터페이스 변경 (spec에 반영됨)

- `runner.run(prompt) -> int` (0=정상, 1=락 충돌, 2=Claude 연속 비정상)
- `state._increment(key)` 신규 (private). `record_*`는 모두 이걸 경유
- `config.load`에 `@lru_cache(maxsize=1)`. 테스트는 `tmp_codingbot_home` fixture가 자동 `cache_clear()`
- `auto_approve._defer_to_user` (이전 `_skip`)
- `llm_judge.py`에서 `import anthropic`은 `_client()` 안 lazy
- (0.1.2) `transcript` 모듈 위 항목

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
모든 파일 ≤ 145 LOC (transcript.py 143)

### 테스트 격리 패턴 (변경 없음)

- `tests/conftest.py`의 `tmp_codingbot_home` fixture: `CODINGBOT_HOME` env 격리 + `config.load.cache_clear()`
- Hook 테스트는 subprocess 기반. `_run_hook` helper에 `timeout=60`
- transcript fixture: `tests/fixtures/transcripts/` 아래 4개 (`sample_simple`, `sample_continuing`, `sample_done`, `sample_real_session`). 모두 새 schema.

### 참고 위치

- spec: `docs/superpowers/specs/2026-04-30-codingbot-design.md` (§5.6 0.1.2 drift 반영됨)
- plan: `docs/superpowers/plans/2026-04-30-codingbot.md` (구현 체크리스트 — historical artifact, 갱신 안 함)
- release notes: `docs/release-notes-0.1.1.md`, `docs/release-notes-0.1.2.md`
- push procedure: `docs/push-procedure.md`

---

## 이어가는 방법

다음 세션 시작 시:

> "CodingBot **0.1.2** 로컬 태그 완료 (transcript I-4/I-5 정공법).
> master HEAD와 `v0.1.2`는 로컬만, origin은 `0247e27`/`v0.1.1`까지.
> 99/99 green, BLOCKED 0건. 0.1.2 push할까, 아니면 다른 작업?"

push → `docs/push-procedure.md` 절차.
다른 작업 → 0.1.x polish 후보 또는 e2e 수동 검증.
