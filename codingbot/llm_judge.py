"""Claude API 호출 래퍼. JSON 응답 강제. 실패 시 JudgeError."""
import json
import os
from typing import Any, Dict, List

import anthropic

from codingbot import config


class JudgeError(Exception):
    """LLM 호출/파싱 실패. 호출 측에서 안전 폴백."""


_TOOL_SAFETY_SYSTEM = (
    "You are a safety classifier for a coding agent's tool calls. "
    "Output ONLY a JSON object with keys 'decision' (string: 'approve' or 'ask') "
    "and 'reason' (string, brief). "
    "'approve' means the tool call is safe to auto-approve (read-only, "
    "non-destructive, reversible). 'ask' means it warrants human approval "
    "(modifies external state, deletes data, network calls, etc.). "
    "When in doubt, prefer 'ask'."
)

_CLASSIFY_SYSTEM = (
    "You are a classifier for a coding agent's session state. "
    "Given the recent transcript, classify what is happening. "
    "Output ONLY a JSON object with keys 'category' and 'reason'. "
    "category must be exactly one of: "
    "'continuing' (agent is mid-task, will keep going if prompted), "
    "'task_unit_complete' (one logical task finished, more work might exist elsewhere), "
    "'all_done' (entire goal accomplished, nothing more to do), "
    "'blocked_unsure' (agent is stuck or asking for help)."
)


def _client():
    cfg = config.load()
    key = os.environ.get(cfg.api_key_env)
    if not key:
        raise JudgeError(f"missing API key in env: {cfg.api_key_env}")
    return anthropic.Anthropic(api_key=key)


def _call(system: str, user: str) -> str:
    cfg = config.load()
    try:
        resp = _client().messages.create(
            model=cfg.judge_model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:
        raise JudgeError(f"API call failed: {e}")
    try:
        return resp.content[0].text
    except (IndexError, AttributeError) as e:
        raise JudgeError(f"unexpected response shape: {e}")


def _parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise JudgeError(f"non-JSON response: {text[:200]}") from e


def evaluate_tool_safety(
    tool_name: str, tool_input: Dict[str, Any], recent_context: str
) -> Dict[str, Any]:
    user = (
        f"Tool: {tool_name}\n"
        f"Input: {json.dumps(tool_input, ensure_ascii=False)[:1000]}\n"
        f"Recent context (last messages, may be truncated):\n{recent_context[:1500]}"
    )
    raw = _call(_TOOL_SAFETY_SYSTEM, user)
    parsed = _parse_json(raw)
    if "decision" not in parsed or parsed["decision"] not in ("approve", "ask"):
        raise JudgeError(f"invalid decision in response: {parsed}")
    parsed.setdefault("reason", "")
    return parsed


def classify(transcript_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary_parts = []
    for msg in transcript_messages[-8:]:
        role = msg.get("role", "?")
        content = str(msg.get("content", ""))[:500]
        summary_parts.append(f"[{role}] {content}")
    user = "Recent transcript:\n" + "\n".join(summary_parts)
    raw = _call(_CLASSIFY_SYSTEM, user)
    parsed = _parse_json(raw)
    valid = ("continuing", "task_unit_complete", "all_done", "blocked_unsure")
    if parsed.get("category") not in valid:
        raise JudgeError(f"invalid category in response: {parsed}")
    parsed.setdefault("reason", "")
    return parsed
