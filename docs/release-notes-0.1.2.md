# CodingBot 0.1.2 Release Notes

- 상태: 로컬 태그 완료 (push는 사용자 승인 게이트)
- 베이스: `v0.1.1` (commit `c2957db`)
- 대상: 0.1.1에서 이월된 transcript 정공법 마무리 (I-4 + I-5)
- 결정: 실제 Claude Code session JSONL 샘플 1건 확보됨 → 정공법 재구성 + tail-style 전환 동시 진행

## 요약

`transcript.py`의 두 알려진 이슈(I-4 메모리 로딩, I-5 schema 추정)를 같은 모듈 작업으로 해소. 0.1.0/0.1.1 시점에는 실제 세션 샘플이 없어 BLOCKED로 추적되던 항목. 다운스트림 인터페이스(`Message = {"role","content": str}`)는 그대로 유지되어 hook 코드와 LLM judge 변경 없음.

## 변경

### 수정

- **`I-5` transcript schema 정공법 재구성 (`91c1051`)** — 기존 구현은 `{"role","content":str}` 형태를 가정했으나 실제 Claude Code session JSONL은 top-level `type` 필드 + `message.content` 블록 리스트(assistant는 `text|thinking|tool_use`, user는 `str|tool_result list`) 구조. `iter_messages`를 새 schema에 맞춰 재구성:
  - `type=user/assistant`만 yield
  - assistant `content` list에서 `type=='text'` block만 join (thinking/tool_use 제외)
  - thinking/tool_use only assistant, tool_result only user는 skip
  - normalize 후 외부 인터페이스는 변경 없음 (`Message = {"role","content": str}`)
  - fixture(`tests/fixtures/transcripts/sample_simple.jsonl`) 새 schema로 갱신
  - 실제 session 추출본(`sample_real_session.jsonl`) 신규 — 회귀 fixture
  - hook 회귀 fixture 2건(`sample_continuing.jsonl`, `sample_done.jsonl`)도 새 schema로 갱신
  - 회귀 테스트 5건 추가 (entry type 필터, text block 추출, thinking-only skip, tool_result only skip, 실제 세션 fixture)
- **`I-4` `last_assistant_text` tail-style 전환 (`12ad542`)** — 기존엔 `iter_messages`로 전체 파일을 메모리에 로딩 후 reverse 탐색. 이제 `_iter_lines_reverse` 헬퍼로 파일 끝에서 64KB chunk 단위 역방향 read:
  - chunk 경계에 잘린 partial line은 leftover로 다음(이전) iteration에 prepend
  - 단일 line이 chunk_size를 넘어도 leftover 누적으로 처리
  - 손상 line은 silent skip (forward 스캔하는 `iter_messages`가 이미 warn)
  - 회귀 테스트 7건 추가 (multi-chunk, line>chunk, 끝의 thinking-only assistant 건너뛰기, no-trailing-newline, empty / missing / no-assistant)

### 문서

- `docs/superpowers/specs/2026-04-30-codingbot-design.md` §5.6 transcript: TODO[BLOCKED] 표시 제거, 새 schema/normalize 규칙/tail-style 명시.
- `codingbot/transcript.py` 상단 docstring의 I-5 BLOCKED 블록 제거. 새 동작 설명으로 교체.

## 호환성

- public API breaking change 없음. `read_recent / last_assistant_text / iter_messages` signature 동일.
- 다운스트림(`auto_approve._read_recent_context`, `handoff_or_continue`, `llm_judge.classify`)은 `m.get("role"), m.get("content")`만 사용 — 코드 수정 0건.
- 단, **이전 schema(`{"role","content":str}`) JSONL 파일은 이제 파싱되지 않음**. 이건 의도된 변경: 실제 Claude Code session 파일은 항상 새 schema이므로 영향 없음. 외부 사용자가 단위 테스트용으로 이전 schema 파일을 만들었다면 새 schema로 갱신 필요.

## 테스트

- 87 → 99 pass + 1 skipped (회귀 테스트 +12)
- e2e는 여전히 manual trigger only (`-m e2e`)

## 알려진 이슈 (남은 것)

- 없음 (`transcript.py` 상단 BLOCKED 1건이 유일했으며 본 릴리즈에서 해소).
- `// TODO`, `# TODO` grep 시 코드 BLOCKED 0건.

## 출시 체크리스트

- [x] I-4 + I-5 정공법 처리
- [x] `pyproject.toml` `version = "0.1.2"` bump
- [x] 회귀 테스트 통과 (99/99)
- [x] 본 문서를 release notes 0.1.2로 확정 (draft 표시 제거)
- [x] `git tag -a v0.1.2 -m "v0.1.2: transcript I-4/I-5"`
- [ ] 원격 push (`git push origin master && git push origin v0.1.2`) — **사용자 승인 게이트** (`docs/push-procedure.md` 참고)
