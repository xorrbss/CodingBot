# CodingBot 0.8.0

## What's new

- **risky_tool 차단 hook 통합 e2e (S9~S13)** — 0.2.0이 도입한 secret/install/priv segment 분류 + chain bypass 차단이 `auto_approve` hook subprocess 분기 → stdout defer → state 카운터까지 가는 통합 경로를 e2e_auto 5건으로 회귀 고정.
  - S9: `cat .env` (secret)
  - S10: `pip install requests` (install)
  - S11: `sudo rm /tmp/x` (priv)
  - S12: `echo ok && cat .env` (chain bypass — 0.2.0 보안 주장의 핵심)
  - S13 (대조): `ls` (safe — false positive 회귀 동시 차단)

## Compatibility

- 운영 코드 변경 0. `git diff v0.7.0..v0.8.0 -- codingbot/`: 빈 diff.
- 모든 기존 명령(`run`, `stop`, `start`, `status`, `tail-log`, `serve`, `install-hooks`, `uninstall-hooks`, `config`) 동작 동일.
- state schema, log 포맷, 의존 그래프 변경 없음.

## Notes

- e2e_auto 트랙: 20 → 25건 (~37s).
- 풀 테스트: 226 + 5 = 231 pass + 1 skipped.
- BLOCKED 0, LOC max 338(`tests/unit/test_heuristics.py`) 유지.
