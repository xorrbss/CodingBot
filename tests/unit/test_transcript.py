from pathlib import Path
from codingbot import transcript

FIXTURE = Path(__file__).parent.parent / "fixtures" / "transcripts" / "sample_simple.jsonl"


def test_read_recent_returns_last_n():
    msgs = transcript.read_recent(FIXTURE, n=2)
    assert len(msgs) == 2
    assert msgs[-1]["role"] == "assistant"
    assert "구현 시작합니다" in msgs[-1]["content"]


def test_read_recent_more_than_total():
    msgs = transcript.read_recent(FIXTURE, n=100)
    assert len(msgs) == 5


def test_last_assistant_text():
    text = transcript.last_assistant_text(FIXTURE)
    assert "구현 시작합니다" in text


def test_iter_messages_yields_all():
    msgs = list(transcript.iter_messages(FIXTURE))
    assert len(msgs) == 5
    assert msgs[0]["role"] == "user"


def test_missing_file_returns_empty(tmp_path):
    msgs = transcript.read_recent(tmp_path / "nope.jsonl", n=5)
    assert msgs == []


def test_corrupt_line_skipped(tmp_path):
    p = tmp_path / "broken.jsonl"
    p.write_text(
        '{"role": "user", "content": "ok"}\n'
        'this is not json\n'
        '{"role": "assistant", "content": "still ok"}\n',
        encoding="utf-8",
    )
    msgs = transcript.read_recent(p, n=10)
    assert len(msgs) == 2
