# E2E Smoke Tests

실제 Claude Code + Anthropic API를 호출하는 통합 테스트. **CI에서 자동 실행 금지.**

## 실행

```bash
export ANTHROPIC_API_KEY=...
codingbot install-hooks
pytest tests/e2e/ -v -m e2e
```

## 비용

테스트 1회 실행 시 약 $0.10~$0.50 예상 (작업 복잡도 따라).
