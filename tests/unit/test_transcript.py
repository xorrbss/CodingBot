from pathlib import Path
from codingbot import transcript

FIXTURES = Path(__file__).parent.parent / "fixtures" / "transcripts"
SIMPLE = FIXTURES / "sample_simple.jsonl"
REAL = FIXTURES / "sample_real_session.jsonl"


def test_read_recent_returns_last_n():
    msgs = transcript.read_recent(SIMPLE, n=2)
    assert len(msgs) == 2
    assert msgs[-1]["role"] == "assistant"
    assert "구현 시작합니다" in msgs[-1]["content"]


def test_read_recent_more_than_total():
    msgs = transcript.read_recent(SIMPLE, n=100)
    assert len(msgs) == 5


def test_last_assistant_text():
    text = transcript.last_assistant_text(SIMPLE)
    assert text is not None
    assert "구현 시작합니다" in text


def test_iter_messages_yields_all():
    msgs = list(transcript.iter_messages(SIMPLE))
    assert len(msgs) == 5
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "사용자 인증 모듈 구현해줘"


def test_missing_file_returns_empty(tmp_path):
    msgs = transcript.read_recent(tmp_path / "nope.jsonl", n=5)
    assert msgs == []


def test_corrupt_line_skipped(tmp_path):
    p = tmp_path / "broken.jsonl"
    p.write_text(
        '{"type":"user","message":{"role":"user","content":"ok"}}\n'
        'this is not json\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"still ok"}]}}\n',
        encoding="utf-8",
    )
    msgs = transcript.read_recent(p, n=10)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


# ----- 정공법 schema 회귀 테스트 (I-5) -----


def test_skips_non_message_entry_types(tmp_path):
    """queue-operation, attachment, system, last-prompt 등은 모두 무시."""
    p = tmp_path / "noise.jsonl"
    p.write_text(
        '{"type":"queue-operation","operation":"enqueue"}\n'
        '{"type":"attachment","attachment":{"type":"hook_success"}}\n'
        '{"type":"system","subtype":"hook"}\n'
        '{"type":"last-prompt","lastPrompt":"x"}\n'
        '{"type":"user","message":{"role":"user","content":"hello"}}\n',
        encoding="utf-8",
    )
    msgs = list(transcript.iter_messages(p))
    assert len(msgs) == 1
    assert msgs[0] == {"role": "user", "content": "hello"}


def test_assistant_text_blocks_only(tmp_path):
    """assistant content는 text block만 추출. thinking/tool_use는 버림."""
    p = tmp_path / "asst.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"thinking","thinking":"내부 추론 — 노출 금지"},'
        '{"type":"text","text":"외부 답변 1"},'
        '{"type":"tool_use","id":"t","name":"Read","input":{}},'
        '{"type":"text","text":"외부 답변 2"}'
        ']}}\n',
        encoding="utf-8",
    )
    msgs = list(transcript.iter_messages(p))
    assert len(msgs) == 1
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"] == "외부 답변 1\n\n외부 답변 2"
    assert "내부 추론" not in msgs[0]["content"]


def test_assistant_with_no_text_block_skipped(tmp_path):
    """assistant entry에 text block이 하나도 없으면(thinking/tool_use only) yield 안 함."""
    p = tmp_path / "asst_notext.jsonl"
    p.write_text(
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"thinking","thinking":"x"}'
        ']}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"tool_use","id":"t","name":"Read","input":{}}'
        ']}}\n',
        encoding="utf-8",
    )
    msgs = list(transcript.iter_messages(p))
    assert msgs == []


def test_user_tool_result_list_skipped(tmp_path):
    """user content가 tool_result list만 있으면 skip — 진짜 user 입력이 아님."""
    p = tmp_path / "user_tr.jsonl"
    p.write_text(
        '{"type":"user","message":{"role":"user","content":['
        '{"type":"tool_result","tool_use_id":"t1","content":"file contents"}'
        ']}}\n',
        encoding="utf-8",
    )
    msgs = list(transcript.iter_messages(p))
    assert msgs == []


def test_real_session_sample_parses():
    """실제 Claude Code session JSONL 샘플로 last_assistant_text 동작 확인."""
    text = transcript.last_assistant_text(REAL)
    assert text is not None
    assert text  # 비어있지 않음
    # 마지막 assistant text는 "다음 세션 시작용 프롬프트" 블록이어야 함
    assert "다음 세션" in text
