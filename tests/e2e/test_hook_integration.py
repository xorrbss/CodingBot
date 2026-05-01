"""hook subprocess 통합 e2e — 0.5.0 spec §3.4."""
import pytest

from codingbot import paths, state
from tests.e2e.hook_harness import run_pre_tool_use, run_stop_hook


pytestmark = pytest.mark.e2e_auto


def test_s5_stop_signal_active_allows_stop(
    hook_env, transcript_jsonl_factory, tmp_codingbot_home
):
    """S5: stop signal 파일 존재 → Stop hook이 빈 stdout (_allow_stop), stop_allow +1."""
    paths.stop_signal_file().touch()
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "임의 텍스트 — should_stop 단계에서 분기됨"},
    ])

    r = run_stop_hook(
        stdin_dict={"transcript_path": str(transcript)},
        env=hook_env(),
    )

    assert r.exit_code == 0
    assert r.decision is None  # 빈 stdout = _allow_stop
    counters = state.read()
    assert counters.get("stop_allow", 0) == 1


def test_s6_judge_timeout_pretool_defers_to_user(
    hook_env, transcript_jsonl_factory
):
    """S6: ambiguous tool + judge_timeout fault inject → _defer_to_user, 카운터 증가."""
    from codingbot import state

    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "다음 단계 진행 중입니다."},
    ])

    r = run_pre_tool_use(
        stdin_dict={
            # WebFetch는 default safe_tools에 없고 Bash도 아니며, url 값에 risky_pattern 매치 없음
            # → heuristic verdict "unknown" → judge 분기 진입 → fault-inject로 timeout
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://example.com/doc"},
            "transcript_path": str(transcript),
        },
        env=hook_env(CODINGBOT_FAULT_INJECT="judge_timeout"),
    )

    assert r.exit_code == 0
    assert r.decision is None  # _defer_to_user — stdout 빈 출력
    counters = state.read()
    assert counters.get("judge_timeout_total", 0) == 1
    assert counters.get("judge_call_total", 0) == 1


def test_s7_judge_timeout_stop_allows_stop(
    hook_env, transcript_jsonl_factory
):
    """S7: heuristic 미매치 + judge_timeout → Stop hook _allow_stop("llm_timeout"), 카운터 증가."""
    from codingbot import state

    # is_clearly_done / is_clearly_continuing 둘 다 미매치하도록 중립 텍스트
    transcript = transcript_jsonl_factory([
        {"role": "user", "text": "여기까지 좀 봐주세요"},
        {"role": "assistant", "text": "현재 상태 요약: 변경된 파일 3개."},
    ])

    r = run_stop_hook(
        stdin_dict={"transcript_path": str(transcript)},
        env=hook_env(CODINGBOT_FAULT_INJECT="judge_timeout"),
    )

    assert r.exit_code == 0
    assert r.decision is None  # _allow_stop
    counters = state.read()
    assert counters.get("judge_timeout_total", 0) == 1
    assert counters.get("judge_call_total", 0) == 1


def test_s8_judge_error_stop_allows_stop(
    hook_env, transcript_jsonl_factory
):
    """S8: heuristic 미매치 + judge_error → Stop hook _allow_stop("llm_failed"), error 카운터 증가."""
    from codingbot import state

    transcript = transcript_jsonl_factory([
        {"role": "user", "text": "확인 부탁"},
        {"role": "assistant", "text": "지금 작업 단위의 중간 점검 메모입니다."},
    ])

    r = run_stop_hook(
        stdin_dict={"transcript_path": str(transcript)},
        env=hook_env(CODINGBOT_FAULT_INJECT="judge_error"),
    )

    assert r.exit_code == 0
    assert r.decision is None
    counters = state.read()
    assert counters.get("judge_error_total", 0) == 1
    assert counters.get("judge_timeout_total", 0) == 0  # 분기 분리 검증
    assert counters.get("judge_call_total", 0) == 1
