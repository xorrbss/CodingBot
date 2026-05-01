# CodingBot 0.2.0 Release Notes

- 베이스: `v0.1.2` (commit `16e70f1`)
- 사이클 가치: A — 신뢰성/안전성
- 범위: A2 위험 패턴 감지 강화 + A3 fallback 정공 정리

## 요약

자동 결정의 안전망을 강화한 사이클. bash 명령을 segment로 분해해 카테고리(secret/install/priv) 매칭. chain 우회(`safe; danger`) 본질적 차단. llm_judge에 timeout 추가, runner에 claude CLI 부재 명시 처리.

## 변경

### 추가 (heuristics)
- `_split_bash_segments` — shlex 기반 segment 분해 (chain operator + command substitution)
- `_is_secret_segment` — `.env`, ssh key, aws creds, env dump, API_KEY 변수
- `_is_install_segment` — pip/npm/apt/brew/choco/winget/gem/cargo/go install 류
- `_is_priv_segment` — sudo/runas/chmod 777/chown root 등
- `_classify_bash` — segment list 위에서 카테고리 → legacy → safe-prefix 순 검사
  - install 카테고리 안에 pipe-to-shell sub-check (curl|sh 류 RCE) 통합
  - legacy substring 검사는 unquoted token에 한정 (`echo "; rm -rf /"` false positive 차단)

### 추가 (config)
- `judge_timeout_secs: int = 15` — llm_judge API timeout
- `risky_categories: dict = {secret, install, priv: True}` — 카테고리 enable/disable

### 수정
- `llm_judge._call`: `timeout=cfg.judge_timeout_secs` 인자 전달, 모든 `JudgeError`에 `from e`
- `runner.run`: 진입 시 `shutil.which("claude")` 검사. 부재 시 return code `3` (신규: 환경 오류)
- `config.example.yaml`: 카테고리/timeout 도큐
- `tests/runner/test_runner.py`: autouse `_claude_present` fixture (기본 PATH 가정)
- `tests/unit/test_heuristics.py::test_unknown_tool`: `npm install`은 이제 install 카테고리로 risky로 분류되므로 `mkdir foo`로 대체

### 회귀 codify (코드 변경 없음)
- config yaml 손상 → default 회귀 테스트 (`test_corrupt_yaml_falls_back_to_defaults`, 기존 보유)
- state.json 손상 → initial state 회귀 테스트 (`test_corrupt_state_resets`, 기존 보유)
- transcript 손상 line → skip 회귀 테스트 (`test_corrupt_line_skipped`, 기존 보유)

## 호환성

- public API breaking change 없음. `classify_tool_call` 시그니처/리턴 동일.
- `runner.run -> int`: return code `3` 추가 (신규 환경 오류 의미).
- `Config` 신규 필드는 default 있어 기존 user config 호환.

## 테스트

- 99 → 148 pass + 1 skipped (회귀 +49)
- BLOCKED 0건
- 모든 코드 파일 ≤ 500 LOC (최대 `heuristics.py` 282)

## 출시 체크리스트

- [x] heuristics segment 기반 분류 + 3 카테고리
- [x] llm_judge timeout
- [x] runner claude CLI 부재 처리
- [x] config 신규 2 필드
- [x] 회귀 baseline codify (audit only — 기존 보유)
- [x] `pyproject.toml` `version = "0.2.0"` bump
- [x] 본 release notes
- [ ] `git tag -a v0.2.0`
- [ ] 원격 push — **사용자 승인 게이트**
