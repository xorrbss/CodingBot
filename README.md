# CodingBot

Claude Code의 권한 자동 승인 + 작업 단위마다 컨텍스트 초기화하며 자동 진행하는 CLI 도구.

## 설치

```bash
pip install -e .
codingbot install-hooks
export ANTHROPIC_API_KEY=...
```

## 사용

```bash
# 자동화 시작
codingbot run "전체 백엔드 리팩터링해줘"

# 다른 터미널에서 멈추기
codingbot stop

# 진행 상황
codingbot status
codingbot tail-log -n 50

# 설정 확인
codingbot config
```

## 동작 원리

1. `codingbot run "<prompt>"`이 셸 루프를 시작
2. 매 사이클마다 `claude "<msg>"`로 인터랙티브 Claude Code 세션 실행
3. **PreToolUse hook**이 안전한 도구 호출은 자동 승인 (위험한 건 사용자에게 물음)
4. **Stop hook**이 작업 단위 완료 감지 시 Claude한테 핸드오프 문서 작성 요청
5. 새 사이클이 핸드오프 문서를 시작 메시지로 받음 = 진짜 컨텍스트 초기화
6. "다 했음" 신호 시 한 번 더 final check, 또 "다 했음"이면 종료

## 안전장치

- 시간 한도: 기본 30분 (config로 조정)
- 사이클 한도: 기본 50회
- `codingbot stop`: 다른 터미널에서 즉시 정지 신호
- 위험 패턴 (rm -rf, force push 등)은 자동 승인 안 함
- LLM 실패 시 안전 폴백 (= 사용자에게 정상적으로 물어봄)

## 설정

`~/.codingbot/config.yaml` (없으면 기본값. `config.example.yaml` 참고)

## 로그

`~/.codingbot/log.jsonl` — 모든 자동 결정 기록.
