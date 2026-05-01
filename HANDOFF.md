# CodingBot 개발 핸드오프

**작성일**: 2026-05-01 (15th update — 0.6.0 ship + push 완료 + README polish-c)
**대상**: 다음 작업 세션

---

## (a) 지금까지 한 일

### 0.6.0 ship 완료 (S 사이클 — `status --watch`)

- 베이스: `v0.5.0` (`24f6cd1`)
- 사이클 가치: **S — 운영 가시성 (한 화면에서 라이브로 본다)**
- 범위: `codingbot status --watch [--interval N] [--tail N]` — 기존 status 출력을 주기적으로 재출력 + 최근 log 라인 표시. 기존 출력 포맷 보존.
- spec: `docs/superpowers/specs/2026-05-01-codingbot-0.6.0-design.md`
- plan: `docs/superpowers/plans/2026-05-01-codingbot-0.6.0.md`
- release notes: `docs/release-notes-0.6.0.md`
- origin/master = local master = `183f241` (release commit `d77bbcc` + README polish-c `183f241`) — push 완료
- 태그 `v0.6.0` (annotated, commit `d77bbcc`) origin 등록됨
- polish-c 반영: README "진행 상황" 블록에 `codingbot status --watch` 예시 2줄 추가 (commit `183f241`). 코드/테스트 무변경.
- 변경 파일:
  - `codingbot/cli.py`: `_print_status_body` 분리 + `_read_log_tail` 헬퍼 + `_watch_status` 루프 + status subparser 옵션 3 (`--watch`/`--interval`/`--tail`). 137 → 193 LOC.
  - `tests/unit/test_cli.py`: 신규 단위 4건 (`_read_log_tail` 2건 + watch 루프 1회 실행 2건).
- 변경 영향: 외부 인터페이스 추가만 (모두 옵션, 미지정 시 0.5.0 동작 동일). state schema/log 포맷/의존 그래프 변경 없음.
- 테스트: 202 pass + 1 skipped (0.5.0 198 → +4 cli watch).
- BLOCKED 0, LOC max 338(test_heuristics.py), cli.py 193, 모두 ≤ 500.

#### 결정 요약 (spec §2 발췌)

- 재출력은 `os.system("cls"/"clear")` + 기존 body 함수 호출 (KISS, 의존 없음).
- 종료는 `KeyboardInterrupt` → rc 0 (signal 모듈 불요).
- log tail은 전체 read 후 slice (yagni — log은 cycle당 수 라인). 회전 정책 들어오면 tail-style chunk read로 갈아탐.
- watch 헤더(`--- CodingBot Status (refresh Ns) --- TS ---`) + `=== Last log ===` 섹션만 추가, 기존 5개 status 섹션 포맷은 그대로.
- lock pid 표시는 0.6.0 비범위 (별 사이클).

### 0.5.0 ship 완료 (hook 통합 e2e 사이클 — fault-inject + S4 + S5/S6/S7/S8)

- 베이스: `v0.4.0` (`5c5d961`)
- 사이클 가치: C2 — 검증 자동화 (hook 분기까지 확장)
- 범위: `llm_judge._call` fault-inject 4라인 + hook_harness 신규 + transcript factory + 5 시나리오 (S4 runner + S5~S8 hook)
- spec: `docs/superpowers/specs/2026-05-01-codingbot-0.5.0-design.md`
- plan: `docs/superpowers/plans/2026-05-01-codingbot-0.5.0.md`
- release notes: `docs/release-notes-0.5.0.md`
- origin/master = local master = `24f6cd1` (release commit) — push 완료
- 태그 `v0.5.0` (annotated, commit `24f6cd1`) origin 등록됨

#### 이번 사이클 작업 요약 (Task 1~10)

| Task | 내용 | 커밋 |
|---|---|---|
| 1 | llm_judge fault-inject + 단위 회귀 3 | `6452b63` |
| 2 | transcript_jsonl_factory + hook_env fixture | `1b29ae2` / `eec93be` |
| 3 | hook_harness + 자체 단위 5 | `f7e4137` |
| 4 | S4 abnormal_repeat | `0dd285d` |
| 5 | S5 stop signal Stop hook | `158afae` |
| 6 | S6 judge timeout PreTool | `3b0b478` |
| 7 | S7 judge timeout Stop | `dcfc730` |
| 8 | S8 judge error Stop | `32cd040` |
| 9 | grand pass (198 + 1 skipped, e2e_auto 19 in 31s, BLOCKED 0, LOC max 282) | (no commit) |
| 10 | release: pyproject 0.5.0 + notes + HANDOFF + tag | (이 commit) |

#### 0.4.0 → 0.5.0 변경 요약

- `codingbot/llm_judge.py`: `_call` 진입부에 env `CODINGBOT_FAULT_INJECT ∈ {judge_timeout, judge_error}` 분기 4라인. 미설정 시 기존 동작 100% 동일.
- `tests/e2e/conftest.py`: `transcript_jsonl_factory`, `hook_env` factory fixture 추가.
- `tests/e2e/hook_harness.py` (신규): `HookResult` dataclass + `run_pre_tool_use` / `run_stop_hook` (`sys.executable -m codingbot.hooks.X`).
- `tests/e2e/test_hook_integration.py` (신규): S5/S6/S7/S8 4건.
- `tests/e2e/test_runner_loop.py`: S4 1건 추가.
- `tests/unit/test_llm_judge.py`: fault-inject 회귀 3건.
- `pyproject.toml`: 0.4.0 → 0.5.0.
- 의존 그래프 / public API / state schema 변경 없음.

### 0.4.0 ship 완료 (e2e 자동화 사이클 — fake claude + 3 시나리오 + e2e_auto 마커)

- 베이스: `v0.3.0` (`e4196b8`)
- 사이클 가치: C — 검증 자동화
- 범위: 운영 코드 무수정. `tests/e2e/`에 fake_claude + conftest fixtures + 6 회귀.
- spec: `docs/superpowers/specs/2026-05-01-codingbot-0.4.0-design.md`
- plan: `docs/superpowers/plans/2026-05-01-codingbot-0.4.0.md`
- release notes: `docs/release-notes-0.4.0.md`
- origin/master = local master = `5c5d961` (release commit) — push 완료
- 태그 `v0.4.0` (annotated, commit `5c5d961`) origin 등록됨

#### 이번 사이클 작업 요약 (Task 1~8)

| Task | 내용 | 커밋 |
|---|---|---|
| 1 | fake_claude.py + 단위 회귀 3 (+ e2e_auto 마커 + handoff 보존 assert hotfix) | `8fab000` / `2205e2c` |
| 2 | conftest fixtures (fake_claude_shim monkeypatch + e2e_scenario) + 임시 wire-up | `fe68696` / `02158cf` / `31544ae` |
| 3 | S1 happy_1_cycle | `6f46ac5` |
| 4 | S2 handoff_multi | `fab8d2a` |
| 5 | S3 abnormal_recover + wire-up 정리 | `15cdefa` |
| 6 | README dual-track (마커는 Task 1 hotfix에서 선반영) | `d3601a4` |
| 7 | grand pass: 182 + 1 skipped, LOC max 338, BLOCKED 0, 운영 diff 0 | (no commit) |
| 8 | release: pyproject 0.4.0 + notes + HANDOFF + tag | (이 commit) |

#### 0.3.0 → 0.4.0 변경 요약

- `tests/e2e/fake_claude.py` 신규 (stdlib only). 시나리오 step 단위 실행.
- `tests/e2e/conftest.py` 신규. `fake_claude_shim` (codingbot.runner.subprocess.run monkeypatch) + `e2e_scenario` factory.
- `tests/e2e/test_runner_loop.py` 신규 (S1/S2/S3).
- `tests/e2e/test_fake_claude.py` 신규 (3건).
- `pyproject.toml` 마커 `e2e_auto` 추가. version 0.3.0 → 0.4.0.
- `tests/e2e/README.md` dual-track 갱신.
- 운영 코드(`codingbot/*`) **무변경**. `git diff v0.3.0..v0.4.0 -- codingbot/`: 빈 diff.

### 0.3.0 push 완료 (관측(metrics) 사이클 — state 카운터 12 + JudgeTimeout + status 섹션화)

- 베이스: `v0.2.0` (`3434973`)
- 사이클 가치: B — 관측 가능성 (0.2.0 안전망의 발동률 가시화)
- 범위: state.json 카운터 12 신규 + record_* 6 함수 + JudgeTimeout(JudgeError) 서브클래스 + auto_approve/handoff_or_continue 카운터 호출 + cli status 섹션화
- spec: `docs/superpowers/specs/2026-05-01-codingbot-0.3.0-design.md`
- plan: `docs/superpowers/plans/2026-05-01-codingbot-0.3.0.md`
- release notes: `docs/release-notes-0.3.0.md`
- origin/master = local master = `e4196b8` (release commit) — push 완료
- 태그 `v0.3.0` (annotated, commit `e4196b8`) origin 등록됨

#### 이번 사이클 작업 요약 (Task 1~8)

| Task | 내용 | 커밋 |
|---|---|---|
| 1 | `_initial_state` 12 신규 카운터 키 + 회귀 1 | `1dbec11` |
| 2 | `record_*` 6 함수 (`auto_approve_by`, `auto_defer_by`, `stop_outcome`, `judge_call/timeout/error`) + 검증 + 회귀 10 | `7b7f129` |
| 2b | PEP 8: pytest import top으로 이동 | `37591cf` |
| 3 | `JudgeTimeout(JudgeError)` 서브클래스 + `APITimeoutError` 매핑 + 회귀 3 | `c317449` |
| 4 | `auto_approve` hook: source-별 카운터 + JudgeTimeout 분기 + 회귀 6 | `e2a9918` |
| 5 | `handoff_or_continue` hook: outcome 카운터 (`_OUTCOME_TO_COUNTER` dict) + JudgeTimeout 분기 + 회귀 5 | `978f1f2` |
| 5b | block_unstuck 회귀 추가 + import 정리 | `24f55c1` |
| 6 | `cli status` 5 섹션 (Status/Cycle/Decisions PreToolUse/Decisions Stop/Judge/Config) + 회귀 2 | `f79d2cd` |
| 7 | grand pass: 176 + 1 skipped, LOC max 282, BLOCKED 0 | (no commit) |
| 8 | release: pyproject 0.3.0 + release notes + HANDOFF + tag | (이 commit) |

#### 0.2.0 → 0.3.0에 포함된 변경 요약

- state: `_initial_state` 12 키 추가 (auto_approve_by_*, auto_defer_by_*, stop_*, judge_*) + `record_*` 6 함수 + 검증 튜플
- llm_judge: `JudgeTimeout(JudgeError)` 신규 + `_call`에서 `anthropic.APITimeoutError` isinstance 매핑
- hooks/auto_approve: `_approve`/`_defer_to_user`에 source-별 카운터, judge 호출 직전 `record_judge_call`, except 분기 timeout/error 분리
- hooks/handoff_or_continue: `_OUTCOME_TO_COUNTER` dict, `_block`/`_allow_stop`에 outcome 카운터, judge 분기 동일 패턴
- cli: `_cmd_status` 5 섹션화, 12 신규 카운터 모두 노출
- public API breaking change 없음. `JudgeError`로 catch하면 `JudgeTimeout`도 잡힘 (하위 호환).

### 0.2.0 push 완료 (신뢰성 사이클 — A2 위험 패턴 + A3 fallback)

- 베이스: `v0.1.2` (`16e70f1`)
- 사이클 가치: A — 신뢰성/안전성
- 범위: bash segment 기반 분류 + 3 카테고리(secret/install/priv) + chain 우회 차단 + llm_judge timeout + runner claude CLI 부재 처리
- spec: `docs/superpowers/specs/2026-05-01-codingbot-0.2.0-design.md`
- plan: `docs/superpowers/plans/2026-05-01-codingbot-0.2.0.md`
- release notes: `docs/release-notes-0.2.0.md`
- origin/master = local master = `3434973` 직후 본 정리 commit
- 태그 `v0.2.0` (annotated, commit `3434973`) origin 등록됨

#### 이번 사이클 작업 요약 (Task 1~11)

| Task | 내용 | 커밋 |
|---|---|---|
| 1 | `_split_bash_segments` (shlex chain + substitution) + 회귀 10 | `c218fd5` |
| 2 | `_is_secret_segment` (.env/ssh/aws/env/$KEY) + 회귀 7 | `08a313c` |
| 3 | `_is_install_segment` (pip/npm/apt/...) + 회귀 7 | `8871619` |
| 4 | `_is_priv_segment` (sudo/chmod 777/chown root) + 회귀 6 | `b59e9ab` |
| 5 | config `judge_timeout_secs`, `risky_categories` + 도큐 + 회귀 4 | `400e375` |
| 6 | `_classify_bash` 통합 + chain bypass + pipe-to-shell + 회귀 11 | `e71980f` |
| 7 | llm_judge `timeout` 인자 + `from e` 일관화 + 회귀 3 | `97b5f77` |
| 8 | runner `shutil.which` 검사 + return code 3 + autouse fixture + 회귀 1 | `c432023` |
| 9 | fallback 회귀 audit (기존 보유 — 추가 없음) | (no commit) |
| 10 | grand pass: 148 + 1 skipped, LOC 282 max, BLOCKED 0 | (no commit) |
| 11 | release: pyproject 0.2.0 + release notes + HANDOFF | (이 commit) |

#### 0.1.2 → 0.2.0에 포함된 변경 요약

- heuristics: `_split_bash_segments` + `_is_secret_segment` + `_is_install_segment` + `_is_priv_segment` + `_classify_bash` 통합
- config: `judge_timeout_secs` + `risky_categories` 신규 필드 (default 호환)
- llm_judge: `_call`에 `timeout` 인자 + `from e` chaining
- runner: `claude` CLI 부재 시 return code 3
- public API breaking change 없음. `classify_tool_call` 동일.

### 0.1.2 push 완료

- origin: `https://github.com/xorrbss/CodingBot.git`
- origin/master = local master = HEAD (`5d98f4d` 직후 본 정리 commit)
- 태그 `v0.1.2` (annotated, commit `16e70f1`) origin에 등록됨
- `git status` clean (`.claude/`는 gitignore에 추가됨)
- 6th update 시점에는 "0.1.2 로컬 태그만 완료, push 미실행"으로 기록되어 있었으나 실제로는 그 후 push가 진행됨. 본 commit에서 HANDOFF를 실제 상태에 맞춰 정정함.

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
<this commit>  docs(handoff): drift 정리 — 0.1.2 push 완료 반영 + .claude gitignore
5d98f4d  docs(handoff): correct origin master SHA (fb449c8, not 0247e27)
16e70f1  release: 0.1.2 finalize (notes/handoff)                    ← v0.1.2 tag
cbb79e6  release: 0.1.2 draft (transcript I-4/I-5 정공법)
12ad542  perf(transcript): tail-style read for last_assistant_text (I-4)
91c1051  fix(transcript): reconstruct iter_messages with real session schema (I-5)
fb449c8  docs(handoff): mark remote push completed
0247e27  docs(handoff): update for 0.1.1 ship + spec drift / push procedure / heartbeat untrack
c2957db  release: 0.1.1                                              ← v0.1.1 tag
... (이전 commits)
```

### 테스트 현황

- **202 pass + 1 skipped** (0.5.0 시점 198 → 0.6.0 S 사이클에서 +4: cli `_read_log_tail` 2 + status --watch 루프 1회 실행 2)
- 이전: 198 pass + 1 skipped (0.4.0 시점 182 → 0.5.0에서 +16: llm_judge fault-inject 3 + e2e fixtures 3 + hook_harness 5 + S4 1 + S5~S8 4)
- 이전: 182 pass + 1 skipped (0.3.0 시점 176 → 0.4.0에서 +6: fake_claude 단위 3 + S1/S2/S3 통합 3)
- 이전: 176 pass + 1 skipped (0.2.0 시점 148 → 0.3.0에서 +28: state 11 + llm_judge 3 + auto_approve 6 + handoff_or_continue 6 + cli 2)
- 이전: 148 pass + 1 skipped (0.1.2 시점 99 → 0.2.0에서 +49: split 10 + secret 7 + install 7 + priv 6 + chain bypass 11 + config 4 + llm_judge 3 + runner 1)
- e2e: 두 트랙 — `e2e_auto` (자동, 무료, 19건, ~31초) + `e2e` (manual, $, smoke)
- `BLOCKED` grep 시 코드 **0건**
- 모든 코드 파일 ≤ 500 LOC (max `tests/unit/test_heuristics.py` 338, 다음 `codingbot/heuristics.py` 282)

---

## (b) 다음에 할 일

0.6.0 ship + push 완료. release 게이트 모두 닫힘. 다음 후보:

### 0.6.x polish 후보 (남은 것)

- (a) e2e 수동 검증 (실제 Claude Code run + watch 화면 직접 확인).
- (b) watch 헤더에 lock pid 표시 (현재 비범위).
- ~~(c) README의 status 섹션에 --watch 안내 추가~~ → commit `183f241`에서 완료.

### 0.7.0 brainstorm 후보 (사이클 가치 결정 → spec → plan)

- risky_tool 차단 e2e (secret/install/priv hook 트랙).
- judge 캐싱 (0.3.0 측정 데이터로 ROI 평가 후 결정).
- abnormal exit state 카운터 + S9 시나리오.
- 외부 metrics export / dashboard.
- D 가치(배포/패키징): pip install codingbot, GitHub Releases 자동화 등.

---

## (c) 새 세션이 알아야 할 중요 컨텍스트

### 0.5.0에서 변경된 것

- `codingbot/llm_judge.py`: `_call` 진입부에 env `CODINGBOT_FAULT_INJECT ∈ {judge_timeout, judge_error}` 분기 4라인 추가. prod 영향 0 (env 미설정 시 미진입). 분기 진입 시 메시지 prefix `fault inject:`로 로그 식별 가능.
- 새 fixture: `transcript_jsonl_factory`, `hook_env` (`tests/e2e/conftest.py`).
- 새 모듈: `tests/e2e/hook_harness.py` — `HookResult` + `run_pre_tool_use` / `run_stop_hook` (subprocess `sys.executable -m codingbot.hooks.X`).
- 새 e2e 테스트 파일: `tests/e2e/test_hook_integration.py` (S5/S6/S7/S8).

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

- `runner.run(prompt) -> int` (0=정상, 1=락 충돌, 2=Claude 연속 비정상, **3=환경 오류 — 0.2.0 신규**)
- `state._increment(key)` 신규 (private). `record_*`는 모두 이걸 경유
- `config.load`에 `@lru_cache(maxsize=1)`. 테스트는 `tmp_codingbot_home` fixture가 자동 `cache_clear()`
- `auto_approve._defer_to_user` (이전 `_skip`)
- `llm_judge.py`에서 `import anthropic`은 `_client()` 안 lazy. **0.2.0**: `messages.create(timeout=cfg.judge_timeout_secs)` + `JudgeError` `from e` 일관화
- (0.1.2) `transcript` 모듈 schema 정공법
- **0.2.0**: `heuristics.classify_tool_call` 외부 동일, 내부는 segment 기반. `Config`에 `judge_timeout_secs:int=15` + `risky_categories:dict={secret,install,priv:True}` 신규
- **0.3.0**: `state` 모듈에 `record_auto_approve_by(judge)`, `record_auto_defer_by(judge)`, `record_stop_outcome(outcome)`, `record_judge_call()`, `record_judge_timeout()`, `record_judge_error()` 신규. judge/outcome 인자는 검증 튜플 위반 시 `ValueError`. `state.read()`에 카운터 키 12개 추가 (default 0). `llm_judge`에 `JudgeTimeout(JudgeError)` 서브클래스 + `_call`이 `anthropic.APITimeoutError`를 명시 매핑. 외부 인터페이스 breaking change 없음.

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
모든 파일 ≤ 500 LOC. 0.2.0에서 `heuristics.py` 103 → 282. 0.3.0에서 `state.py` 107 → 173, `cli.py` 116 → 137, hooks 약간 증가.

### 테스트 격리 패턴 (변경 없음)

- `tests/conftest.py`의 `tmp_codingbot_home` fixture: `CODINGBOT_HOME` env 격리 + `config.load.cache_clear()`
- Hook 테스트는 subprocess 기반. `_run_hook` helper에 `timeout=60`
- transcript fixture: `tests/fixtures/transcripts/` 아래 4개 (`sample_simple`, `sample_continuing`, `sample_done`, `sample_real_session`). 모두 새 schema.

### 참고 위치

- spec (0.1.x): `docs/superpowers/specs/2026-04-30-codingbot-design.md`
- spec (0.2.0): `docs/superpowers/specs/2026-05-01-codingbot-0.2.0-design.md`
- spec (0.3.0): `docs/superpowers/specs/2026-05-01-codingbot-0.3.0-design.md`
- spec (0.4.0): `docs/superpowers/specs/2026-05-01-codingbot-0.4.0-design.md`
- spec (0.5.0): `docs/superpowers/specs/2026-05-01-codingbot-0.5.0-design.md`
- spec (0.6.0): `docs/superpowers/specs/2026-05-01-codingbot-0.6.0-design.md`
- plan (0.1.x): `docs/superpowers/plans/2026-04-30-codingbot.md` (historical)
- plan (0.2.0): `docs/superpowers/plans/2026-05-01-codingbot-0.2.0.md`
- plan (0.3.0): `docs/superpowers/plans/2026-05-01-codingbot-0.3.0.md`
- plan (0.4.0): `docs/superpowers/plans/2026-05-01-codingbot-0.4.0.md`
- plan (0.5.0): `docs/superpowers/plans/2026-05-01-codingbot-0.5.0.md`
- plan (0.6.0): `docs/superpowers/plans/2026-05-01-codingbot-0.6.0.md`
- release notes: `docs/release-notes-0.1.1.md`, `docs/release-notes-0.1.2.md`, `docs/release-notes-0.2.0.md`, `docs/release-notes-0.3.0.md`, `docs/release-notes-0.4.0.md`, `docs/release-notes-0.5.0.md`, `docs/release-notes-0.6.0.md`
- push procedure: `docs/push-procedure.md`

---

## 이어가는 방법

다음 세션 시작 시:

> "CodingBot **0.6.0 ship + push 완료** (S 사이클 — `status --watch [--interval N] [--tail N]`, 운영 코드 +56 LOC). origin/master = `183f241` (README polish 포함), `v0.6.0` push됨.
> 202 pass + 1 skipped, BLOCKED 0건, 모든 파일 ≤ 500 LOC (cli.py 193).
> HANDOFF (a)/(b), 0.6.0 spec/plan/release notes 모두 정합.
>
> 다음 후보 — 골라줘:
> - 0.6.x polish: (a) e2e 수동 검증, (b) watch 헤더에 lock pid 표시
> - 0.7.0 사이클 brainstorm: (d) risky_tool 차단 e2e [A], (e) judge 캐싱 [B2], (f) abnormal exit 카운터 + S9 [A/C], (g) metrics export [E], (h) 배포 패키징 [D]"

선택지 요약:
- 0.6.x polish → 작은 단위 (a/b), 한 세션 안에서 마무리.
- 0.7.0 brainstorm → 사이클 가치(A/B/C/D/E/S) 결정 + spec + plan + 다중 task. 한 세션 이상 가능.
