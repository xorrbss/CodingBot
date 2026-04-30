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
