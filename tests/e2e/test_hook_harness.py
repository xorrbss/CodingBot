"""hook_harness 자체 단위 — 실제 hook 모듈을 호출하지 않고도 harness 동작 확인."""
import pytest

from tests.e2e.hook_harness import HookResult, run_pre_tool_use, run_stop_hook


pytestmark = pytest.mark.e2e_auto


def test_hook_result_decision_none_when_stdout_empty():
    r = HookResult(exit_code=0, stdout="", stderr="")
    assert r.decision is None


def test_hook_result_decision_parsed_when_stdout_json():
    r = HookResult(exit_code=0, stdout='{"decision":"approve","reason":"ok"}', stderr="")
    assert r.decision == {"decision": "approve", "reason": "ok"}


def test_hook_result_decision_none_when_stdout_not_json():
    r = HookResult(exit_code=0, stdout="not json at all", stderr="")
    assert r.decision is None


def test_run_pre_tool_use_invokes_subprocess(hook_env, transcript_jsonl_factory):
    """real hook subprocess까지 가보고 exit_code 0을 받는지 (heuristic-safe path)."""
    transcript = transcript_jsonl_factory([{"role": "assistant", "text": "ok"}])
    r = run_pre_tool_use(
        stdin_dict={
            "tool_name": "Read",  # safe_tools — heuristic safe 경로, judge 미호출
            "tool_input": {"file_path": "/tmp/x"},
            "transcript_path": str(transcript),
        },
        env=hook_env(),
    )
    assert r.exit_code == 0
    assert r.decision == {"decision": "approve", "reason": "safe (Read)"}


def test_run_stop_hook_invokes_subprocess(hook_env, transcript_jsonl_factory):
    """Stop hook subprocess가 실제로 떠서 exit_code 0이고 결과 포맷 정상."""
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "계속해서 다음 단계로 진행하겠습니다"},  # _CONTINUING_PATTERNS 매치
    ])
    r = run_stop_hook(
        stdin_dict={"transcript_path": str(transcript)},
        env=hook_env(),
    )
    assert r.exit_code == 0
    assert r.decision is not None
    assert r.decision.get("decision") == "block"
