"""Stop hook entrypoint.

stdin: {"transcript_path": str, ...}
stdout:
  - {"decision": "block", "reason": "..."}: Claude가 멈추지 않고 reason을 받아 진행
  - 빈 출력: Claude 정상 정지
exit code: 항상 0
"""
import json
import sys
from pathlib import Path

from codingbot import handoff, heuristics, llm_judge, logger, state, transcript


HANDOFF_INSTRUCTION = (
    "이 작업 단위가 완료된 것 같아요. 이어서 할 작업이 있으면 "
    "`~/.codingbot/handoff.md`에 다음을 작성하고 종료해 주세요: "
    "(a) 지금까지 한 일 (b) 다음에 할 일 (c) 새 세션이 알아야 할 중요 컨텍스트. "
    "더 할 일 없으면 핸드오프 만들지 말고 그렇게 답하고 종료하세요."
)

CONTINUE_INSTRUCTION = "작업이 아직 끝나지 않은 것 같아요. 계속 진행해 주세요."

UNSTUCK_INSTRUCTION = (
    "막힌 부분이 있으면 가능한 도구로 더 조사해 주세요. "
    "여전히 모르겠으면 정확히 뭐가 막혔는지 핸드오프에 적고 종료하세요."
)


def _block(reason: str, judge: str, outcome: str) -> None:
    state.record_auto_continue()
    logger.info("stop_hook", outcome=outcome, judge=judge)
    print(json.dumps({"decision": "block", "reason": reason}))


def _allow_stop(why: str, judge: str = "rule") -> None:
    logger.info("stop_hook", outcome="allow_stop", judge=judge, reason=why)


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        transcript_path = data.get("transcript_path", "")

        if state.should_stop():
            _allow_stop("stop_signal_or_limit_active")
            return 0

        if handoff.was_just_written():
            _allow_stop("handoff_already_written")
            return 0

        last_text = ""
        if transcript_path:
            t = transcript.last_assistant_text(Path(transcript_path)) or ""
            last_text = t

        if last_text:
            if heuristics.is_clearly_continuing(last_text):
                _block(CONTINUE_INSTRUCTION, judge="heuristic", outcome="continue")
                return 0
            if heuristics.is_clearly_done(last_text):
                _block(HANDOFF_INSTRUCTION, judge="heuristic", outcome="request_handoff")
                return 0

        try:
            msgs = transcript.read_recent(Path(transcript_path), n=5) if transcript_path else []
            verdict = llm_judge.classify(msgs)
        except llm_judge.JudgeError as e:
            logger.warn("llm_api_error", hook="handoff_or_continue", error=str(e))
            _allow_stop("llm_failed", judge="llm")
            return 0

        cat = verdict["category"]
        if cat == "continuing":
            _block(CONTINUE_INSTRUCTION, judge="llm", outcome="continue")
        elif cat == "task_unit_complete" or cat == "all_done":
            _block(HANDOFF_INSTRUCTION, judge="llm", outcome="request_handoff")
        elif cat == "blocked_unsure":
            _block(UNSTUCK_INSTRUCTION, judge="llm", outcome="unstuck")
        else:
            _allow_stop(f"unknown_category:{cat}", judge="llm")
        return 0

    except Exception as e:
        logger.error("hook_exception", hook="handoff_or_continue", error=str(e))
        return 0


if __name__ == "__main__":
    sys.exit(main())
