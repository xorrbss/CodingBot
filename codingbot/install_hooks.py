"""~/.claude/settings.json에 codingbot hook 등록/해제.

Claude Code 공식 hooks 포맷:
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "..."}]}
    ],
    "Stop": [
      {"matcher": "*", "hooks": [{"type": "command", "command": "..."}]}
    ]
  }
}
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


_PRE_TOOL_USE_CMD = f"{sys.executable} -m codingbot.hooks.auto_approve"
_STOP_CMD = f"{sys.executable} -m codingbot.hooks.handoff_or_continue"

_MARKER = "codingbot.hooks"


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _load() -> Dict[str, Any]:
    p = _settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: Dict[str, Any]) -> None:
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_codingbot_hook(group: Dict[str, Any]) -> bool:
    for h in group.get("hooks", []):
        cmd = h.get("command", "")
        if _MARKER in cmd:
            return True
    return False


def install() -> None:
    data = _load()
    hooks = data.setdefault("hooks", {})

    for event, cmd in [("PreToolUse", _PRE_TOOL_USE_CMD), ("Stop", _STOP_CMD)]:
        groups: List[Dict[str, Any]] = hooks.setdefault(event, [])
        groups[:] = [g for g in groups if not _is_codingbot_hook(g)]
        groups.append({
            "matcher": "*",
            "hooks": [{"type": "command", "command": cmd}],
        })

    _save(data)
    print(f"[codingbot] hooks installed at {_settings_path()}")


def uninstall() -> None:
    data = _load()
    hooks = data.get("hooks", {})
    for event in ("PreToolUse", "Stop"):
        groups = hooks.get(event, [])
        groups[:] = [g for g in groups if not _is_codingbot_hook(g)]
        if not groups:
            hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)
    _save(data)
    print(f"[codingbot] hooks uninstalled from {_settings_path()}")
