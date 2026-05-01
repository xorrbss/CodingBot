"""hook subprocess 통합 e2e — 0.5.0 spec §3.4."""
import pytest

from codingbot import paths, state
from tests.e2e.hook_harness import run_stop_hook


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
