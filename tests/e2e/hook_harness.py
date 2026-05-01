"""hook subprocess 호출 harness — 실제 hook entrypoint를 띄워 stdin/stdout 캡처.

design ref: docs/superpowers/specs/2026-05-01-codingbot-0.5.0-design.md §3.3
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class HookResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def decision(self) -> Optional[dict]:
        """stdout이 JSON dict면 파싱, 아니면 None.

        None은 명시적 의미: PreToolUse `_defer_to_user` 또는 Stop `_allow_stop`.
        """
        s = self.stdout.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(parsed, dict):
            return parsed
        return None


def _run_hook(module: str, stdin_dict: dict, env: dict, timeout: float) -> HookResult:
    proc = subprocess.run(
        [sys.executable, "-m", module],
        input=json.dumps(stdin_dict),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    return HookResult(
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def run_pre_tool_use(stdin_dict: dict, env: dict, timeout: float = 30.0) -> HookResult:
    return _run_hook("codingbot.hooks.auto_approve", stdin_dict, env, timeout)


def run_stop_hook(stdin_dict: dict, env: dict, timeout: float = 30.0) -> HookResult:
    return _run_hook("codingbot.hooks.handoff_or_continue", stdin_dict, env, timeout)
