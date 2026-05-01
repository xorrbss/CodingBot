import json
import pytest
from codingbot import llm_judge


def _mock_response(client_mock, text: str):
    msg = type("Msg", (), {"text": text})()
    response = type("R", (), {"content": [msg]})()
    client_mock.messages.create.return_value = response


def test_evaluate_tool_safety_approve(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, '{"decision": "approve", "reason": "테스트 명령은 안전"}')
    result = llm_judge.evaluate_tool_safety(
        tool_name="Bash",
        tool_input={"command": "pytest"},
        recent_context="some context",
    )
    assert result["decision"] == "approve"
    assert "안전" in result["reason"]


def test_evaluate_tool_safety_ask(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, '{"decision": "ask", "reason": "확인 필요"}')
    result = llm_judge.evaluate_tool_safety("Edit", {"file_path": "x"}, "")
    assert result["decision"] == "ask"


def test_classify_returns_category(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(
        mock_anthropic,
        '{"category": "task_unit_complete", "reason": "auth.py 끝남"}',
    )
    result = llm_judge.classify(transcript_messages=[{"role": "assistant", "content": "끝"}])
    assert result["category"] == "task_unit_complete"


def test_invalid_json_response_raises(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, "not json")
    with pytest.raises(llm_judge.JudgeError):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")


def test_api_error_raises(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    mock_anthropic.messages.create.side_effect = Exception("rate_limit")
    with pytest.raises(llm_judge.JudgeError):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")


def test_no_api_key_raises(tmp_codingbot_home, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm_judge.JudgeError):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")


def test_timeout_passed_to_sdk(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, '{"decision": "approve", "reason": "ok"}')
    llm_judge.evaluate_tool_safety("Bash", {"command": "ls"}, "")
    call_kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert call_kwargs.get("timeout") == 15


def test_timeout_from_config(tmp_codingbot_home, mock_anthropic, monkeypatch):
    from codingbot import config, paths
    paths.config_file().write_text("judge_timeout_secs: 5\n", encoding="utf-8")
    config.load.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _mock_response(mock_anthropic, '{"decision": "approve", "reason": "ok"}')
    llm_judge.evaluate_tool_safety("Bash", {"command": "ls"}, "")
    call_kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert call_kwargs.get("timeout") == 5


def test_api_error_chains_cause(tmp_codingbot_home, mock_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    underlying = RuntimeError("network fail")
    mock_anthropic.messages.create.side_effect = underlying
    with pytest.raises(llm_judge.JudgeError) as exc_info:
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")
    assert exc_info.value.__cause__ is underlying


def test_judge_timeout_is_subclass_of_judge_error():
    """JudgeTimeout은 JudgeError의 서브클래스 (하위 호환)."""
    assert issubclass(llm_judge.JudgeTimeout, llm_judge.JudgeError)


def test_api_timeout_raises_judge_timeout(tmp_codingbot_home, mock_anthropic, monkeypatch):
    """anthropic.APITimeoutError → JudgeTimeout (JudgeError 아닌 더 구체)."""
    import anthropic
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    # APITimeoutError는 httpx.Request 인자 필요. mock으로 우회.
    timeout_exc = anthropic.APITimeoutError(request=type("R", (), {})())
    mock_anthropic.messages.create.side_effect = timeout_exc
    with pytest.raises(llm_judge.JudgeTimeout):
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")


def test_non_timeout_exception_raises_judge_error_not_timeout(tmp_codingbot_home, mock_anthropic, monkeypatch):
    """일반 Exception은 JudgeError로만 raise (JudgeTimeout 아님)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    mock_anthropic.messages.create.side_effect = RuntimeError("rate_limit")
    with pytest.raises(llm_judge.JudgeError) as exc_info:
        llm_judge.evaluate_tool_safety("Bash", {"command": "x"}, "")
    assert not isinstance(exc_info.value, llm_judge.JudgeTimeout)
