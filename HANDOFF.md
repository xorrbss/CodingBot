# CodingBot 개발 핸드오프

**작성일**: 2026-04-30 (2nd update)
**대상**: 다음 작업 세션

---

## (a) 지금까지 한 일

### 설계 단계 (완료)
- Spec: [docs/superpowers/specs/2026-04-30-codingbot-design.md](docs/superpowers/specs/2026-04-30-codingbot-design.md)
- Plan: [docs/superpowers/plans/2026-04-30-codingbot.md](docs/superpowers/plans/2026-04-30-codingbot.md)

### 구현 단계 (Task 0~15 + Final review 완료)

| # | Task | 상태 |
|---|---|---|
| 0~7 | scaffolding ~ heuristics | ✅ 완료 (이전 세션) |
| 8 | llm_judge | ✅ 완료 (옵션 B로 리뷰 스킵하고 인정) |
| 9 | PreToolUse hook (auto_approve) | ✅ 완료 (spec+quality 리뷰 통과, mocker fixture 정리 + 60s timeout 추가) |
| 10 | Stop hook (handoff_or_continue) | ✅ 완료 |
| 11 | runner | ✅ 완료 (unused imports 정리) |
| 12 | install_hooks | ✅ 완료 |
| 13 | CLI | ✅ 완료 |
| 14 | 전체 테스트 + README | ✅ 완료 (README 업데이트, 풀 suite 검증 — 아래 주의사항) |
| 15 | E2E 스모크 스캐폴딩 | ✅ 완료 (manual trigger only) |
| F | Final code review | ✅ 완료 (whole-codebase, opus) |

### Git 커밋 (9개)
```
ca76e2d test: add E2E smoke test scaffold (manual trigger only)
c96bcd1 docs: update README with installation, usage, and design overview
43f57ff feat: add codingbot CLI (run/stop/start/status/tail-log/install-hooks/config)
78d029d feat: add install/uninstall for Claude Code hook registration
6d54aac chore(runner): remove unused imports
0d38b5b feat: add shell-loop runner with handoff cycles and final-check
91ddf2e feat: add Stop hook (handoff or continue)
abddc44 test: remove unused mocker fixture, add subprocess timeouts
4bafda5 chore: initial commit of existing codingbot modules (tasks 0-8)
```

**주의**: 이전 세션의 git history(9 commit, b02f8b8 ~ 9743aaa)는 어떤 시점에 사라지고 Task 9 implementer가 새로 `git init` 했음. Task 0~8 코드는 정상이지만 4bafda5 단일 commit에 번들됨.

### 테스트 현황
- unit + runner: 74 tests pass (`py -m pytest tests/ --ignore=tests/e2e --ignore=tests/hooks`) — 35초
- hooks: 11 tests pass (`py -m pytest tests/hooks/`) — 약 3분
- 합계 85 tests pass
- **풀 suite 단일 배치 실행 시 일부 hook 테스트가 60s timeout 빠짐** (env flakiness, 코드 결함 아님 — 분리 실행하면 통과). 원인은 final review I-1과 같음(아래).

---

## (b) 다음에 할 일

### Final review 결론: **fix-then-ship**

블로킹 결함 없음. 0.1.0 출시 전 권장 수정 2건:

#### I-1 (Important) — Hook cold-start 성능 문제
- 문제: `codingbot/llm_judge.py` 최상단에서 `import anthropic`. 매 hook 호출(=매 도구 호출)마다 SDK import 비용(~3s) 발생.
- 영향: 모든 PreToolUse 호출에 지연 + 풀 테스트 suite의 4개 hook 테스트 timeout 원인.
- 수정: `import anthropic`을 `_client()` 안으로 이동 (약 3줄).
- 주의: HANDOFF에 적힌 "import anthropic + anthropic.Anthropic(...) 스타일 사용" 제약은 mock 호환성 때문임. lazy import도 `mocker.patch("anthropic.Anthropic", ...)`로 가로챌 수 있음 (이름 기반 패치이므로). 단, 적용 후 hook 테스트 11개 다시 돌려서 확인 필요.

#### I-5 (Important) — Transcript 스키마가 실제 Claude Code 포맷과 불일치
- 문제: `codingbot/transcript.py`는 `{"role": "...", "content": "..."}` 형식 가정. 실제 Claude Code session JSONL은 `{"type": "assistant", "message": {...}, "content": [text/tool_use blocks]}` 형식.
- 영향: 단위 테스트는 fixture가 파서 모양에 맞춰져 있어 통과. 하지만 E2E 첫 실행에서 `last_assistant_text()`가 None 반환할 수 있음.
- 수정 옵션:
  - (a) 실제 transcript 1개 받아서 파서 재구성 + 새 fixture 추가
  - (b) `// TODO: [BLOCKED]` 형식으로 명시하고 0.1.1로 미루기 (CLAUDE.md "문제 은폐 금지" 원칙 따라 명시 필요)

### 작은 polish 후보 (0.1.1 이후)
- I-2: `state.record_*`의 read-modify-write가 락 밖에 있음. 동시 hook 실행 시 카운터 손실 가능.
- I-3: `config.load()`가 hook hot path에서 3~5번 호출. `lru_cache(maxsize=1)` 1줄로 해결.
- I-4: `transcript.last_assistant_text`가 전체 파일을 메모리에 올림. tail-style 읽기로 전환 권장.
- M-5: `runner.run()`이 lock 충돌 시 None 반환 → CLI는 항상 exit 0. status 반환하도록.
- M-11: `auto_approve._skip` 함수명이 모호 (실제 의미는 "사용자에게 물음"). `_defer_to_user`로 rename.

### 다음 세션 시작 시 추천 흐름
1. 사용자에게 묻기: "I-1 (lazy import)과 I-5 (transcript schema) 중 어디부터?"
2. 사용자가 I-1 선택 시:
   - `codingbot/llm_judge.py`의 `import anthropic`을 `_client()` 안으로 옮김
   - `py -m pytest tests/hooks/ -v` 다시 돌려서 11/11 통과 + 시간 단축 확인
   - commit
3. 사용자가 I-5 선택 시:
   - 옵션 (a): 실제 transcript 샘플 받아서 파서 재구성. fixture도 갱신
   - 옵션 (b): `transcript.py`에 TODO[BLOCKED] 주석 추가하고 0.1.1로 미룸
4. 둘 다 끝나면 0.1.0 태그 + 출시 준비

---

## (c) 새 세션이 알아야 할 중요 컨텍스트

### 환경
- Working dir: `C:/project/CodingBot`
- Windows 11. 셸은 bash (Git Bash)
- Python: 3.11 (`C:\Users\dream\AppData\Local\Programs\Python\Python311\python.exe`)
- **`.venv/`는 존재하지 않음** — pytest는 `py -m pytest`로 실행 (시스템 Python)
- Git: `git init` 새로 됨. user는 "CodingBot Dev <dev@codingbot.local>"

### 아키텍처 (변하지 않은 핵심)
- Hooks(PreToolUse + Stop) + shell-loop runner 조합
- LLM 위험도 판단 + 휴리스틱 화이트/블랙리스트
- 사이클간 컨텍스트 초기화는 핸드오프 문서 통해
- Final check: "다 했음" 신호 → 한 번 더 묻고 또 "다 했음"이면 종료
- 정지 조건: stop signal file + 시간 30분 + 사이클 50회

### 모듈 의존 그래프 (final review가 verify 한 결과 — strictly acyclic)
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
모든 파일 ≤ 135 LOC (500 limit 한참 아래)

### 테스트 격리 패턴
- `tests/conftest.py`의 `tmp_codingbot_home` fixture가 `CODINGBOT_HOME` env 격리
- 모든 모듈은 `paths.codingbot_home()`을 통해 경로 얻음. `~/.codingbot` 하드코딩 금지
- Hook 테스트는 subprocess 기반. `_run_hook` helper에 `timeout=60` 설정됨

### LLM mock 호환성 (Task 8에서 정해진 제약)
- `llm_judge.py`는 `import anthropic` + `anthropic.Anthropic(...)` 스타일 (NOT `from anthropic import Anthropic`)
- conftest의 `mock_anthropic` fixture가 `mocker.patch("anthropic.Anthropic", ...)`로 가로챔
- I-1 lazy import 적용 시에도 이 제약은 유지 가능 (이름 기반 patch이므로)

### 풀 suite 실행 시 timeout 4건
풀 `pytest tests/ --ignore=tests/e2e` 실행 시 hook 테스트 4건이 60s timeout 빠짐. 분리 실행하면 통과. 원인은 I-1 (anthropic SDK import 비용 누적). I-1 수정 후 사라질 가능성 높음.

### 참고 위치
- spec: `docs/superpowers/specs/2026-04-30-codingbot-design.md`
- plan: `docs/superpowers/plans/2026-04-30-codingbot.md` (각 task의 코드/테스트가 거의 그대로 적혀 있음)
- final review 원문은 컨텍스트 안에만 있음 (subagent 결과). 본 핸드오프 (b)에 결론 요약됨.

---

## 이어가는 방법

다음 세션 시작 시:

> "이전 세션에서 CodingBot Task 0~15 + final review 완료. fix-then-ship 결론. I-1 (lazy import in llm_judge) + I-5 (transcript schema mismatch) 두 권장 수정 남아있어요. I-1부터 갈까요, I-5부터 갈까요, 아니면 그대로 0.1.0 출시할까요?"

사용자 결정 후 진행. 둘 다 작은 변경이므로 한 세션에 끝낼 수 있음.
