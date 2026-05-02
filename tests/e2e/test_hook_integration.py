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


def test_s9_secret_segment_blocked(
    hook_env, transcript_jsonl_factory, tmp_codingbot_home
):
    """S9: Bash `cat .env` → heuristic risky(secret) → _defer_to_user, judge 미호출."""
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "임의 텍스트 — heuristic risky 분기는 transcript 미사용"},
    ])

    r = run_pre_tool_use(
        stdin_dict={
            "tool_name": "Bash",
            "tool_input": {"command": "cat .env"},
            "transcript_path": str(transcript),
        },
        env=hook_env(),
    )

    assert r.exit_code == 0
    assert r.decision is None  # _defer_to_user — stdout 빈 출력
    counters = state.read()
    assert counters.get("auto_defer_by_heuristic", 0) == 1
    assert counters.get("judge_call_total", 0) == 0  # heuristic risky → judge 미호출


def test_s10_install_segment_blocked(
    hook_env, transcript_jsonl_factory, tmp_codingbot_home
):
    """S10: Bash `pip install requests` → heuristic risky(install) → _defer_to_user."""
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "임의 텍스트"},
    ])

    r = run_pre_tool_use(
        stdin_dict={
            "tool_name": "Bash",
            "tool_input": {"command": "pip install requests"},
            "transcript_path": str(transcript),
        },
        env=hook_env(),
    )

    assert r.exit_code == 0
    assert r.decision is None
    counters = state.read()
    assert counters.get("auto_defer_by_heuristic", 0) == 1
    assert counters.get("judge_call_total", 0) == 0


def test_s11_priv_segment_blocked(
    hook_env, transcript_jsonl_factory, tmp_codingbot_home
):
    """S11: Bash `sudo rm /tmp/x` → heuristic risky(priv) → _defer_to_user."""
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "임의 텍스트"},
    ])

    r = run_pre_tool_use(
        stdin_dict={
            "tool_name": "Bash",
            "tool_input": {"command": "sudo rm /tmp/x"},
            "transcript_path": str(transcript),
        },
        env=hook_env(),
    )

    assert r.exit_code == 0
    assert r.decision is None
    counters = state.read()
    assert counters.get("auto_defer_by_heuristic", 0) == 1
    assert counters.get("judge_call_total", 0) == 0


def test_s12_chain_bypass_still_blocked(
    hook_env, transcript_jsonl_factory, tmp_codingbot_home
):
    """S12: Bash `echo ok && cat .env` → 첫 segment 안전해도 chain 내부 secret 차단.

    0.2.0 보안 주장의 핵심 — _split_bash_segments가 chain operator로 분리한 뒤
    각 segment를 독립 검사하므로 chain 우회가 불가능함을 hook 통합 e2e로 고정.
    """
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "임의 텍스트"},
    ])

    r = run_pre_tool_use(
        stdin_dict={
            "tool_name": "Bash",
            "tool_input": {"command": "echo ok && cat .env"},
            "transcript_path": str(transcript),
        },
        env=hook_env(),
    )

    assert r.exit_code == 0
    assert r.decision is None
    counters = state.read()
    assert counters.get("auto_defer_by_heuristic", 0) == 1
    assert counters.get("auto_approve_count", 0) == 0  # 첫 segment "echo ok"가 approve 분기로 새지 않음
    assert counters.get("judge_call_total", 0) == 0


def test_s13_safe_bash_still_approves(
    hook_env, transcript_jsonl_factory, tmp_codingbot_home
):
    """S13 (대조): Bash `ls` → heuristic safe → _approve, defer 카운터 미증가.

    risky 분기 회귀와 함께 false positive(안전 명령이 defer로 새는 것) 회귀도
    함께 닫는다.
    """
    transcript = transcript_jsonl_factory([
        {"role": "assistant", "text": "임의 텍스트"},
    ])

    r = run_pre_tool_use(
        stdin_dict={
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "transcript_path": str(transcript),
        },
        env=hook_env(),
    )

    assert r.exit_code == 0
    assert r.decision is not None
    assert r.decision["decision"] == "approve"
    counters = state.read()
    assert counters.get("auto_approve_count", 0) == 1
    assert counters.get("auto_approve_by_heuristic", 0) == 1
    assert counters.get("auto_defer_by_heuristic", 0) == 0
    assert counters.get("judge_call_total", 0) == 0
