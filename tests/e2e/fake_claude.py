"""가짜 `claude` CLI — runner.run() e2e용.

호출형: `claude <prompt>` (positional args 무시).

env:
    CODINGBOT_E2E_SCENARIO: 시나리오 JSON 절대경로 (필수).
    CODINGBOT_HOME:         step 카운터/handoff 기록 위치 (필수, runner가 자동 설정).

시나리오 JSON 스키마:
    {"name": str, "steps": [{"exit_code": int, "handoff": str | null}, ...]}

exit codes:
    0~127: scenario step의 exit_code 그대로
    90:    CODINGBOT_E2E_SCENARIO 미설정 또는 파일 부재
    91:    step 인덱스가 steps 길이를 초과
"""
import json
import os
import sys
from pathlib import Path


def main() -> int:
    scenario_path = os.environ.get("CODINGBOT_E2E_SCENARIO")
    if not scenario_path or not Path(scenario_path).exists():
        print(
            "[fake_claude] CODINGBOT_E2E_SCENARIO not set or missing",
            file=sys.stderr,
        )
        return 90

    scenario = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
    steps = scenario["steps"]

    home = Path(os.environ["CODINGBOT_HOME"])
    home.mkdir(parents=True, exist_ok=True)

    step_file = home / ".e2e_step"
    idx = int(step_file.read_text(encoding="utf-8")) if step_file.exists() else 0

    if idx >= len(steps):
        print(
            f"[fake_claude] step out of range: {idx} >= {len(steps)}",
            file=sys.stderr,
        )
        return 91

    step = steps[idx]
    if step.get("handoff") is not None:
        (home / "handoff.md").write_text(step["handoff"], encoding="utf-8")

    step_file.write_text(str(idx + 1), encoding="utf-8")
    return int(step["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
