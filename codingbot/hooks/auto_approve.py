"""PreToolUse hook entrypoint.

stdin: {"tool_name": str, "tool_input": dict, "transcript_path": str, ...}
stdout: {"decision": "approve", "reason": "..."} 또는 빈 출력 (사용자 승인 받게)
exit code: 항상 0 (Claude Code 흐름 막지 않음)
"""
import json
import sys
from pathlib import Path

from codingbot import heuristics, llm_judge, logger, state, transcript


def _read_recent_context(transcript_path: str, n_chars: int = 1500) -> str:
    if not transcript_path:
        return ""
    try:
        msgs = transcript.read_recent(Path(transcript_path), n=5)
    except Exception:
        return ""
    parts = []
    for m in msgs:
        parts.append(f"[{m.get('role','?')}] {str(m.get('content',''))[:300]}")
    return "\n".join(parts)[-n_chars:]


def _approve(reason: str, judge: str) -> None:
    state.record_auto_approve()
    logger.info("auto_approve", decision="approve", judge=judge, reason=reason)
    print(json.dumps({"decision": "approve", "reason": reason}))


def _skip(why: str, judge: str) -> None:
    logger.info("auto_skip", judge=judge, reason=why)


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        transcript_path = data.get("transcript_path", "")

        if state.should_stop():
            _skip("stop_signal_active", "rule")
            return 0

        verdict = heuristics.classify_tool_call(tool_name, tool_input)
        if verdict == "safe":
            _approve(f"safe ({tool_name})", judge="heuristic")
            return 0
        if verdict == "risky":
            _skip(f"risky ({tool_name})", judge="heuristic")
            return 0

        try:
            ctx = _read_recent_context(transcript_path)
            result = llm_judge.evaluate_tool_safety(tool_name, tool_input, ctx)
        except llm_judge.JudgeError as e:
            logger.warn("llm_api_error", hook="auto_approve", error=str(e))
            _skip("llm_failed", judge="llm")
            return 0

        if result["decision"] == "approve":
            _approve(result.get("reason", ""), judge="llm")
        else:
            _skip(result.get("reason", "ask"), judge="llm")
        return 0

    except Exception as e:
        logger.error("hook_exception", hook="auto_approve", error=str(e))
        return 0


if __name__ == "__main__":
    sys.exit(main())
