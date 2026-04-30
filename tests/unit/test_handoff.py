from codingbot import handoff, paths


def test_exists_false_initially(tmp_codingbot_home):
    assert handoff.exists() is False


def test_write_then_read(tmp_codingbot_home):
    handoff.write("## 다음 작업\nDb refactor")
    assert handoff.read() == "## 다음 작업\nDb refactor"


def test_exists_after_write(tmp_codingbot_home):
    handoff.write("anything")
    assert handoff.exists() is True


def test_clear_removes_file(tmp_codingbot_home):
    handoff.write("anything")
    handoff.clear()
    assert handoff.exists() is False
    assert handoff.read() is None


def test_clear_no_file_ok(tmp_codingbot_home):
    handoff.clear()  # no exception


def test_read_empty_file_returns_none(tmp_codingbot_home):
    paths.handoff_file().touch()
    assert handoff.read() is None


def test_was_just_written_equals_exists(tmp_codingbot_home):
    """spec 결정: was_just_written == exists. clear()는 사이클 시작 시 호출됨."""
    assert handoff.was_just_written() is False
    handoff.write("x")
    assert handoff.was_just_written() is True
    handoff.clear()
    assert handoff.was_just_written() is False
