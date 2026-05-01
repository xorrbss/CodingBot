# E2E Tests

두 트랙 운영:

## 1. Auto (`e2e_auto`) — 무료, 기본 실행

`tests/e2e/fake_claude.py` shim으로 runner의 멀티사이클 흐름을 통합 회귀.
실 Claude / Anthropic API 호출 없음.

```bash
py -m pytest tests/e2e/ -m e2e_auto -v
```

기본 `py -m pytest`에도 자동 포함됨.

## 2. Manual (`e2e`) — 실제 API, 유료

실 Claude Code + Anthropic API 호출. 1회 실행 약 $0.10–0.50.

```bash
export ANTHROPIC_API_KEY=...
codingbot install-hooks
py -m pytest tests/e2e/ -v -m e2e
```

API 키나 `claude` CLI 부재 시 self-skip.
