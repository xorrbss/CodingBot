# CodingBot — Claude Code 자동화 도구 설계

- 작성일: 2026-04-30
- 대상: Claude Code CLI (Mac/Windows/Linux)
- 상태: 설계 확정, 구현 대기

## 1. 목적

사용자가 Claude Code로 "바이브 코딩"할 때 흐름이 끊기지 않도록 다음을 자동화한다:

1. 도구 사용 권한 프롬프트를 자동으로 승인 (안전한 것만)
2. Claude가 작업 단위를 끝낼 때마다 컨텍스트를 초기화하면서 다음 작업으로 자동 이행
3. 사용자가 자리를 비워도 안전하게 동작 — 시간/사이클 한도와 명시적 정지 신호로 보호

비목표:
- Claude Code 외 도구(Cursor, Codex 등) 지원
- LLM 응답의 정확성 검증

## 2. 핵심 결정

| 항목 | 결정 |
|---|---|
| 대상 도구 | Claude Code CLI |
| 통합 방식 | Hooks (PreToolUse + Stop) + Shell-loop wrapper |
| 자동 승인 범위 | 매 호출마다 LLM이 위험도 판단 (휴리스틱 화이트/블랙리스트가 명백한 케이스 처리) |
| 작업 이행 방식 | 사이클 종료 시 Claude가 핸드오프 문서 작성 → 새 세션이 그 문서를 시작 메시지로 받음 (진짜 컨텍스트 초기화) |
| 정지 조건 | 명시적 정지 명령(파일/CLI) + 시간 한도(기본 30분) + 사이클 한도(기본 50) |
| Final check | "다 했음" 신호 시 한 번 더 묻고, 그래도 "다 했음"이면 종료 |
| 판단 모델 | Claude Haiku (`claude-haiku-4-5`) — 빠르고 저렴 |
| 언어 | Python (cross-platform) |

## 3. 아키텍처

```
[사용자 터미널]
    $ codingbot run "<초기 프롬프트>"
            │
            ▼
[runner.py: 셸 루프]
    while not should_stop():
        msg = handoff.read() or initial_prompt or FINAL_CHECK_PROMPT
        subprocess.run(["claude", msg])      # 같은 터미널, 일반 인터랙티브 모드
        # 종료 후 다음 사이클 결정
            │
            ▼
[Claude Code 인터랙티브 세션]
    Hooks (settings.json):
      PreToolUse → auto_approve.py
      Stop      → handoff_or_continue.py
            │
            ▼
[공유 유틸: state.json / config.yaml / log.jsonl / handoff.md]
```

핵심 아이디어:
- **wrapper는 Claude 입출력을 가로채지 않음.** 같은 터미널에서 그냥 자식 프로세스로 실행, 종료를 기다린 후 다음 사이클 시작
- **PTY/ConPTY 등 복잡한 터미널 처리 불필요**
- **컨텍스트 초기화는 "새 프로세스"로 자연 달성** (이전 세션 메모리 0)

## 4. 디렉터리 구조

```
C:\project\CodingBot\
├── codingbot\
│   ├── __init__.py
│   ├── runner.py                  # 셸 루프 wrapper의 핵심
│   ├── hooks\
│   │   ├── __init__.py
│   │   ├── auto_approve.py        # PreToolUse hook entrypoint
│   │   └── handoff_or_continue.py # Stop hook entrypoint
│   ├── state.py                   # state.json 읽기/쓰기 + 락
│   ├── config.py                  # config.yaml 로딩 + 기본값
│   ├── transcript.py              # transcript .jsonl 파서
│   ├── heuristics.py              # 규칙 기반 판단
│   ├── llm_judge.py               # Claude API 호출 래퍼
│   ├── handoff.py                 # 핸드오프 파일 read/write/clear
│   ├── logger.py                  # 감사 로그 (JSONL)
│   └── cli.py                     # codingbot run/stop/start/status/install-hooks 명령
├── tests\
│   ├── conftest.py
│   ├── fixtures\
│   │   └── transcripts\           # 샘플 .jsonl
│   ├── unit\
│   ├── hooks\                     # hook 통합 테스트
│   ├── runner\                    # runner 통합 테스트
│   └── e2e\                       # 실제 Claude Code 스모크 테스트 (수동 트리거)
├── config.example.yaml
├── pyproject.toml
└── README.md
```

## 5. 컴포넌트 명세

### 5.1 `runner.py`

`codingbot run "<initial_prompt>"`의 본체. 셸 루프로 Claude Code 사이클을 반복.

의사코드:

```python
def run(initial_prompt: str):
    acquire_lock()                      # ~/.codingbot/.runner.lock
    clear_stop_signal()                 # ~/.codingbot/.codingbot-stop 있으면 삭제
    handoff.clear()
    state.start_cycle()
    final_check_pending = False
    abnormal_exits = 0

    try:
        while not should_stop():
            if final_check_pending:
                msg = FINAL_CHECK_PROMPT
            else:
                msg = handoff.read() or initial_prompt

            handoff.clear()
            exit_code = subprocess.run(["claude", msg]).returncode
            state.record_cycle()

            if exit_code != 0:
                abnormal_exits += 1
                if abnormal_exits >= 2:
                    log("claude_repeated_failure")
                    break
                continue                # 같은 메시지로 한 번 재시도
            abnormal_exits = 0

            if handoff.exists():
                final_check_pending = False
            else:
                if final_check_pending:
                    log("run_end", reason="final_check_returned_done")
                    break
                final_check_pending = True
    finally:
        release_lock()
```

`should_stop()`은 다음 중 하나라도 참이면 True:
- `~/.codingbot/.codingbot-stop` 파일 존재
- `now - cycle_started_at > config.time_limit_minutes`
- `state.cycles_this_run >= config.max_cycles_per_run`

`FINAL_CHECK_PROMPT` (상수):
> "지금 코드 상태를 다시 한번 살펴봐 주세요. 추가로 가능한 작업이 있나요? — 개선/리팩터링, 테스트 추가, 문서화, 미발견 버그, 일관성 안 맞는 패턴 등.
>
> 있다면 평소처럼 `~/.codingbot/handoff.md`에 작성하고 종료하세요. 정말 없다면 핸드오프 만들지 말고 그렇게 알려 주고 종료하세요."

### 5.2 `hooks/auto_approve.py` (PreToolUse hook)

stdin: `{"tool_name": "...", "tool_input": {...}, "transcript_path": "...", ...}`

흐름:
1. `should_stop()` 검사 → True면 exit 0 (자동 승인 안 함)
2. `heuristics.classify_tool_call(tool_name, tool_input)` 호출
   - `"safe"` → `{"decision": "approve", "reason": "..."}` 출력 후 exit 0
   - `"risky"` → exit 0 (decision 미출력 — Claude Code가 사용자에게 물어봄)
   - `"unknown"` → 다음 단계
3. `llm_judge.evaluate_tool_safety(tool_name, tool_input, recent_context)` 호출
   - `{decision: "approve" | "ask"}` 반환
   - `approve`면 출력 후 exit, `ask`면 그냥 exit 0
4. 모든 결정은 logger에 기록
5. 예외 시 → exit 0 (안전한 폴백)

### 5.3 `hooks/handoff_or_continue.py` (Stop hook)

stdin: `{"transcript_path": "...", ...}`

흐름:
1. `should_stop()` → exit 0
2. `handoff.was_just_written()` (현재 사이클 동안 핸드오프 파일이 새로 생겼나) → exit 0 (정상 종료)
3. `transcript.read_recent(n=5)`로 마지막 메시지들 읽음
4. `heuristics.is_clearly_continuing(last_msg)` → True면 `{"decision": "block", "reason": CONTINUE_INSTRUCTION}` 출력
5. `heuristics.is_clearly_done(last_msg)` → True면 `{"decision": "block", "reason": HANDOFF_INSTRUCTION}` 출력
6. 위 휴리스틱 둘 다 False → `llm_judge.classify(transcript)` 호출
   - `"continuing"` → block + CONTINUE_INSTRUCTION
   - `"task_unit_complete"` → block + HANDOFF_INSTRUCTION
   - `"blocked_unsure"` → block + UNSTUCK_INSTRUCTION
   - `"all_done"` → block + HANDOFF_INSTRUCTION (Claude 스스로 핸드오프 안 만들고 답할 거란 기대)
7. 예외 시 → exit 0

표준 instruction 상수:
- `HANDOFF_INSTRUCTION`: "이 작업 단위가 완료된 것 같아요. 이어서 할 작업이 있으면 `~/.codingbot/handoff.md`에 (a) 지금까지 한 일 (b) 다음에 할 일 (c) 새 세션이 알아야 할 중요 컨텍스트를 작성하고 종료해 주세요. 더 할 일 없으면 핸드오프 만들지 말고 그렇게 답하고 종료하세요."
- `CONTINUE_INSTRUCTION`: "작업이 아직 끝나지 않은 것 같아요. 계속 진행해 주세요."
- `UNSTUCK_INSTRUCTION`: "막힌 부분이 있으면 가능한 도구로 더 조사해 주세요. 여전히 모르겠으면 정확히 뭐가 막혔는지 핸드오프에 적고 종료하세요."

### 5.4 `state.py`

위치: `~/.codingbot/state.json`

스키마:
```json
{
  "cycle_started_at": "2026-04-30T14:00:00Z",
  "cycles_this_run": 3,
  "auto_approve_count": 12,
  "auto_continue_count": 2,
  "last_session_id": "..."
}
```

API: `start_cycle()`, `record_cycle()`, `read()`, `write(state)`. 동시 쓰기 보호는 OS 파일 락(`portalocker`) 사용.

### 5.5 `config.py`

위치: `~/.codingbot/config.yaml`. 없으면 패키지 내 기본값.

기본값:
```yaml
enabled: true
time_limit_minutes: 30
max_cycles_per_run: 50
judge_model: "claude-haiku-4-5-20251001"
api_key_env: "ANTHROPIC_API_KEY"
safe_tools: ["Read", "Glob", "Grep", "TodoWrite"]
risky_patterns:
  - "rm -rf"
  - "git push --force"
  - "git push -f"
  - "git reset --hard"
  - "DROP TABLE"
  - "DROP DATABASE"
  - ":(){:|:&};:"             # fork bomb
  - "mkfs"
  - "dd if="
log_level: "info"
```

### 5.6 `transcript.py`

Claude Code transcript는 `.jsonl` 포맷. 각 줄은 한 메시지의 JSON.

API:
- `read_recent(path, n=5) -> list[Message]`
- `last_assistant_text(path) -> str | None`
- `iter_messages(path) -> Iterator[Message]`

### 5.7 `heuristics.py`

순수 함수 모음.

- `classify_tool_call(tool_name, tool_input) -> "safe" | "risky" | "unknown"`
  - `tool_name in config.safe_tools` → safe
  - Bash이고 `tool_input.command`가 명백히 안전 (예: `git status`, `ls`, `pwd`, `cat <file>`) → safe
  - `tool_input`의 텍스트가 `risky_patterns` 중 하나 매칭 → risky
  - 그 외 → unknown
- `is_clearly_done(text) -> bool`: 마지막 assistant 메시지에 명백한 완료 신호 ("완료했습니다", "마쳤습니다", "✓ 완료", "All done", "Finished") + 도구 호출이나 후속 단계 언급 없음
- `is_clearly_continuing(text) -> bool`: "다음으로", "이제", "계속해서" 등 후속 단계 명시 + 사용자에게 묻는 표현 없음

### 5.8 `llm_judge.py`

Anthropic SDK 래퍼. 모든 호출은 짧은 시스템 프롬프트 + JSON 응답 강제.

- `evaluate_tool_safety(tool_name, tool_input, recent_context) -> dict`
  - 응답 스키마: `{"decision": "approve" | "ask", "reason": str}`
- `classify(transcript_messages) -> dict`
  - 응답 스키마: `{"category": "continuing" | "task_unit_complete" | "blocked_unsure" | "all_done", "reason": str}`

실패 처리: 1회 재시도 후 raise. 호출하는 hook이 try/except로 감싸 exit 0 폴백.

캐싱: 미사용(v1).

### 5.9 `handoff.py`

위치: `~/.codingbot/handoff.md`.

API:
- `read() -> str | None` (없거나 빈 파일이면 None)
- `write(content)`
- `clear()` (파일 삭제)
- `exists() -> bool`
- `was_just_written() -> bool` — 단순히 `exists()`와 동일. runner가 매 사이클 시작 시 `clear()`하므로, 사이클 도중에 파일이 있다는 것 = 이번 사이클 안에서 Claude가 작성했다는 것.

### 5.10 `logger.py`

`~/.codingbot/log.jsonl`에 한 줄씩 append.

필드: `ts`, `level`, `event`, 그 외 이벤트별 필드.

이벤트 종류: `cycle_start`, `cycle_end`, `auto_approve`, `auto_skip`, `stop_hook`, `handoff_received`, `final_check_started`, `run_end`, `llm_api_error`, `claude_abnormal_exit`, `user_sigint`, `time_limit_exceeded`, `cycle_limit_exceeded`, `lock_conflict`.

### 5.11 `cli.py`

서브커맨드:
- `codingbot run "<prompt>"`: 자동화 시작 (runner.py 호출)
- `codingbot stop`: `~/.codingbot/.codingbot-stop` 파일 생성
- `codingbot start`: 정지 파일 삭제
- `codingbot status`: 현재 락/state/최근 활동 표시
- `codingbot install-hooks`: Claude Code `~/.claude/settings.json`에 hook 등록 자동화 (이미 있으면 스킵)
- `codingbot uninstall-hooks`: 등록 해제
- `codingbot tail-log [-n N]`: 최근 N개 로그 라인 표시
- `codingbot config`: 현재 적용 중인 config 출력 (디버깅용)

## 6. 데이터 흐름 (요약)

### 일반 사이클

```
1. runner: claude "<msg>" 실행
2. PreToolUse 발생 시마다 auto_approve.py가 자동 승인 결정
3. Claude가 작업 단위 끝낼 때 멈추려 함
4. Stop hook → handoff_or_continue.py:
   - 정지 신호면 exit 0
   - 핸드오프 방금 작성됐으면 exit 0 (정상 종료 진행)
   - 그 외 휴리스틱/LLM으로 분기:
     • 계속해야 함 → block + 이어가기 메시지
     • 작업 단위 완료 → block + 핸드오프 작성 메시지
5. Claude가 핸드오프 작성 → 다시 Stop hook → 이번엔 was_just_written이 True → exit 0
6. claude 종료 → runner가 다음 사이클 결정
```

### "다 했음" 처리 (final check)

```
사이클 N에서 핸드오프 안 만들고 종료:
  runner: handoff.exists()? No
  → final_check_pending = True
  → 다음 사이클은 FINAL_CHECK_PROMPT로 시작

사이클 N+1 (final check):
  Claude가 코드 다시 살펴봄
  케이스 1: 새 작업 발견 → 핸드오프 작성 → 일반 사이클 복귀, final_check_pending = False
  케이스 2: 정말 없음 → 핸드오프 안 만듦 → runner: 두 번째 "다 했음" → break
```

### 정지 시나리오

- 사용자: 다른 터미널에서 `codingbot stop` → 정지 파일 생성 → 다음 hook/사이클 경계에서 정상 종료
- 시간 한도 초과: runner가 사이클 경계에서 break
- 사이클 한도 초과: 동일
- Ctrl+C: runner가 SIGINT 받아 자식 종료 후 break

## 7. 에러 핸들링

핵심 원칙:
1. 자동화 실패 = 안전한 폴백. Hook 실패해도 Claude Code 자체 흐름은 안 막음.
2. 모든 실패는 로그에 기록.

| 케이스 | 동작 |
|---|---|
| LLM API 실패 (PreToolUse) | exit 0, 사용자에게 정상적으로 물어봄 |
| LLM API 실패 (Stop) | block 안 함, 정상 정지 |
| Claude 비정상 exit 1회 | 같은 메시지로 1회 재시도 |
| Claude 비정상 exit 2회 연속 | runner break + 에러 메시지 |
| Hook 자체 예외 | top-level catch, exit 0 |
| 핸드오프 파일 누락/빈 파일 | "다 했음"으로 처리 |
| state.json 손상 | 초기화 후 진행, 로그 남김 |
| config.yaml 손상 | 기본값 폴백 |
| 동시 실행 | runner.lock으로 거부, stale lock은 자동 정리 |
| 무한 루프 위험 | 시간 한도 + 사이클 한도 |

## 8. 테스팅

### 레벨 1: 유닛 테스트 (빠름, CI 매번)
- `heuristics.py` 케이스 매트릭스
- `transcript.py` fixture 파싱
- `handoff.py`, `state.py`, `config.py` 파일 I/O (tmp_path)
- `llm_judge.py` 모킹된 클라이언트

### 레벨 2: Hook 통합 테스트
- subprocess로 hook 스크립트 실행, stdin/stdout/exit code 검증
- LLM 호출은 mock
- 케이스: safe/risky/unknown × 정지 상태 여부 × LLM 응답별 분기

### 레벨 3: Runner 통합 테스트
- `subprocess.run`을 mock으로 대체. 핸드오프 작성/안 작성 시뮬레이트
- 케이스: 정상 종료, 시간/사이클 한도, 정지 파일, 비정상 exit, 동시 실행 락, SIGINT

### 레벨 4: E2E 스모크 (수동, 비용 있음)
- 토이 프로젝트로 `codingbot run` 실제 실행
- 멀티 사이클, 자동 승인, 핸드오프, final check 모두 검증
- CI 푸시마다 X. 별도 manual trigger.

### 인프라
- pytest + pytest-mock
- `tests/conftest.py` 공통 fixture: `tmp_codingbot_home`, `mock_anthropic_client`, `fixture_transcripts`
- coverage 목표: 핵심 모듈 90%+

## 9. 비범위 / 향후 작업

v1 범위 밖 (필요 시 v2):
- Claude Code 외 도구 지원 (Codex CLI 등)
- `codingbot resume` (이전 핸드오프에서 이어가기)
- LLM 응답 캐싱
- 실제 키보드 핫키 정지 (현재는 정지 파일/명령으로 대체)
- 멀티-프로젝트 별 config 분리
- 사이클별 비용 추적 / 토큰 사용 리포트

## 10. 설치 / 사용법 (개요)

```
$ pip install codingbot
$ codingbot install-hooks         # ~/.claude/settings.json에 hook 자동 등록
$ export ANTHROPIC_API_KEY=...
$ codingbot run "백엔드 리팩터링해줘"

# 다른 터미널에서 멈추고 싶을 때:
$ codingbot stop

# 진행 상황 확인:
$ codingbot status
$ codingbot tail-log -n 50
```
