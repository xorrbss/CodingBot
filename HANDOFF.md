# CodingBot 개발 핸드오프

**작성일**: 2026-04-30
**대상**: 다음 작업 세션

---

## (a) 지금까지 한 일

### 설계 단계 (완료)
- Spec 작성/승인: [docs/superpowers/specs/2026-04-30-codingbot-design.md](docs/superpowers/specs/2026-04-30-codingbot-design.md)
- Implementation plan 작성/승인: [docs/superpowers/plans/2026-04-30-codingbot.md](docs/superpowers/plans/2026-04-30-codingbot.md)

### 구현 단계 (Task 0~7 완료, Task 8 절반)

Subagent-driven development로 진행 중. 각 task는 (1) implementer → (2) spec compliance reviewer → (3) code quality reviewer 사이클.

| # | Task | 상태 | 마지막 커밋 |
|---|---|---|---|
| 0 | 프로젝트 스캐폴딩 + Git init | ✅ 완료 (양 리뷰 통과) | b02f8b8 |
| 1 | paths 모듈 + conftest fixture | ✅ 완료 | d327ea2 |
| 2 | logger 모듈 (+ ts override fix) | ✅ 완료 | 162d8b6 |
| 3 | config 모듈 (+ example yaml fix) | ✅ 완료 | bd0d75c |
| 4 | state 모듈 + should_stop() | ✅ 완료 | cc03eb3 |
| 5 | handoff 모듈 | ✅ 완료 | 316e079 |
| 6 | transcript 파서 | ✅ 완료 | e510c55 |
| 7 | heuristics 모듈 (+ pattern fix) | ✅ 완료 | b61f4bb |
| 8 | llm_judge 모듈 | 🟡 implementer 완료, 리뷰 미실행 | 9743aaa |
| 9 | PreToolUse hook (auto_approve) | ⏳ 대기 | — |
| 10 | Stop hook (handoff_or_continue) | ⏳ 대기 | — |
| 11 | runner 모듈 | ⏳ 대기 | — |
| 12 | install_hooks 모듈 | ⏳ 대기 | — |
| 13 | CLI | ⏳ 대기 | — |
| 14 | 전체 테스트 + README | ⏳ 대기 | — |
| 15 | E2E 스모크 테스트 스캐폴딩 | ⏳ 대기 | — |
| F | 최종 코드 리뷰 | ⏳ 대기 | — |

총 9개 commit 만들어졌음. `git log --oneline`으로 확인 가능.

---

## (b) 다음에 할 일

### 즉시 (Task 8 마무리)

Task 8 (llm_judge) implementer는 완료했지만 spec compliance + code quality reviewer를 못 돌렸음. 두 옵션:

1. **Reviewer 디스패치 후 진행** — plan 충실
2. **그냥 Task 9로 진행** — 실용적 (구현은 plan과 동일하므로 검증된 패턴)

추천: 옵션 1 (한 번 더 검증 가치 있음). 아래 프롬프트로 디스패치:

```
Task 8 spec + quality review.
Working dir: C:/project/CodingBot. HEAD = 9743aaa.
Files: codingbot/llm_judge.py, tests/unit/test_llm_judge.py.
Spec: API JudgeError + evaluate_tool_safety + classify functions, import anthropic style, JSON validation. 6 tests.
Verify: read both files, git show --stat HEAD, run pytest, check anthropic import style.
```

### 이후 Task 9~15

각 task마다 plan 파일 그대로 따라가면 됨. plan에 implementer 프롬프트에 들어갈 코드/테스트가 거의 그대로 적혀 있음.

각 task 디스패치 패턴 (Task 0~7에서 검증된 형식):
```
Implement Task N: [title] for CodingBot.
Working dir: C:/project/CodingBot. Tasks 0-(N-1) done. venv `.venv/Scripts/python.exe`.

Files: [목록]
Step 1 (Tests first): [test code]
Step 2 (Run, expect fail)
Step 3 (Implementation): [code]
Step 4 (Run, expect pass)
Step 5 (Commit): [git commands]

Self-review + Report: Status / SHA
```

특히 주의:
- **Task 9, 10 (hooks)**: subprocess 기반 통합 테스트, stdin/stdout 인터페이스 검증
- **Task 11 (runner)**: subprocess.run mock, lock 처리, final_check 로직
- **Task 12 (install_hooks)**: `~/.claude/settings.json` 수정. 테스트는 monkeypatch로 HOME/USERPROFILE
- **Task 13 (CLI)**: argparse 분기, 각 command 별 테스트
- **Task 14**: 전체 pytest 통과 확인 (지금까지 누적된 테스트가 ~50+개) + README 업데이트
- **Task 15**: E2E는 `pytest -m e2e`로 분리, CI에서 자동 실행 안 됨

---

## (c) 새 세션이 알아야 할 중요 컨텍스트

### 프로젝트 위치 + 환경
- 작업 디렉터리: `C:/project/CodingBot`
- 플랫폼: Windows 10. 셸은 bash (Git Bash) 사용
- Python: 3.14.3 (`requires-python = ">=3.11"`)
- 가상환경: `.venv/` (이미 `pip install -e ".[dev]"` 됨). 활성화는 `.venv/Scripts/python.exe`로 직접 호출이 가장 안정적
- Git: 이미 init됨. user.name/email은 "CodingBot Dev <dev@codingbot.local>"로 설정됨

### 아키텍처 핵심 결정 (브레인스토밍 거치며 정해진 것들)
- **Hooks 기반 + Shell-loop wrapper** 조합. wrapper는 Claude Code 입출력을 가로채지 않음. 그저 자식 프로세스로 띄우고 종료를 기다린 후 다음 세션 시작.
- **자동 승인 범위**: 매번 LLM이 위험도 판단 (휴리스틱 화이트/블랙리스트가 명백한 케이스 처리)
- **컨텍스트 초기화**: `/clear` 자동 실행은 Claude Code가 hook에서 슬래시 명령을 부를 수 없어 불가능. 대신 새 세션을 핸드오프 문서로 시작 = 진짜 컨텍스트 초기화 효과.
- **Final check 규칙**: Claude가 "다 했음" 하면 한 번 더 물어보고, 또 "다 했음"이면 종료. 매 "다 했음" 신호마다 한 번씩 final check.
- **정지 조건**: 사용자 명시 정지(파일/CLI) + 시간 한도 30분 + 사이클 한도 50회

### 리뷰 사이클에서 발견되어 수정한 이슈들 (다음 세션이 비슷한 패턴 주의)
1. **Task 2 logger**: `**fields`가 ts/level/event 덮어쓸 수 있음 → dict literal에서 `**fields`를 앞으로
2. **Task 3 config example**: yaml에 fork-bomb 패턴 누락 → 추가
3. **Task 7 heuristics**: "Let me continue" 패턴 + 한국어 informal done 누락 → 추가
4. **모든 hook**: 절대 raise하지 말 것 (Claude Code 흐름 막으면 안 됨). top-level try/except + exit 0 폴백 패턴 일관됨

### 테스트 격리 패턴
- `tests/conftest.py`의 `tmp_codingbot_home` fixture가 `CODINGBOT_HOME` 환경변수를 monkeypatch해서 격리
- 모든 모듈은 `paths.codingbot_home()` 통해 경로 얻음. 절대 `~/.codingbot` 하드코딩 금지

### LLM 호출 mock 호환성
- `codingbot/llm_judge.py`는 반드시 `import anthropic` + `anthropic.Anthropic(...)` 스타일 사용 (NOT `from anthropic import Anthropic`).
- 그래야 conftest.py의 `mock_anthropic` fixture가 `mocker.patch("anthropic.Anthropic", ...)`로 정확히 가로챌 수 있음
- 이 패턴은 Task 8 ✅ 적용됨

### Skill 사용 흐름
- 이 작업은 superpowers:subagent-driven-development skill로 진행 중
- 각 task: implementer (sonnet 모델) → spec reviewer (sonnet) → code quality reviewer (sonnet)
- Reviewer가 issue 발견 시 implementer 재디스패치 → fix → re-review

### 참고 위치
- 전체 spec: `docs/superpowers/specs/2026-04-30-codingbot-design.md`
- 전체 plan (각 task의 코드/테스트 그대로 있음): `docs/superpowers/plans/2026-04-30-codingbot.md`

### 비용/시간 추정
- Task 8 review + Task 9~15 + 최종 리뷰 = 약 25~30회 subagent 디스패치 남음
- 각 디스패치 ~30초~3분, 총 ~1~2시간 + 토큰 비용

---

## 이어가는 방법

다음 세션에서 사용자에게 다음과 같이 시작:

> "이전 세션에서 CodingBot Task 0~7 완료, Task 8 implementer 완료(리뷰 미실행) 상태로 핸드오프 받았어요. Task 8 reviewer 디스패치부터 이어갈까요, 아니면 Task 8 그대로 인정하고 Task 9부터 진행할까요?"

사용자 결정 후 plan을 따라 task별로 implementer → reviewer 사이클 계속.
