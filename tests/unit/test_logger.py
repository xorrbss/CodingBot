import json
from codingbot import logger, paths


def test_log_event_appends_jsonl(tmp_codingbot_home):
    logger.log("info", "cycle_start", cycle=1, msg="hi")
    log_path = paths.log_file()
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["level"] == "info"
    assert record["event"] == "cycle_start"
    assert record["cycle"] == 1
    assert record["msg"] == "hi"
    assert "ts" in record


def test_multiple_events_append(tmp_codingbot_home):
    logger.log("info", "first")
    logger.log("warn", "second")
    lines = paths.log_file().read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "first"
    assert json.loads(lines[1])["event"] == "second"


def test_log_helpers(tmp_codingbot_home):
    logger.info("e1", x=1)
    logger.warn("e2", x=2)
    logger.error("e3", x=3)
    lines = paths.log_file().read_text(encoding="utf-8").strip().split("\n")
    levels = [json.loads(line)["level"] for line in lines]
    assert levels == ["info", "warn", "error"]


def test_log_resilient_to_disk_error(tmp_codingbot_home, monkeypatch):
    """디스크 쓰기 실패 시 예외 던지지 말 것 (호출 흐름 보호)."""
    def boom(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr("pathlib.Path.open", boom)
    # 예외가 전파되면 안 됨
    logger.log("info", "test_event")


def test_reserved_fields_not_overridden_by_caller(tmp_codingbot_home):
    """caller가 ts/level/event를 fields로 넘겨도 무시되어야 함 (예약 키)."""
    import json
    logger.log("info", "real_event", ts="FAKE", level="DEBUG", event="OTHER", x=1)
    line = paths.log_file().read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["ts"] != "FAKE"
    assert record["level"] == "info"
    assert record["event"] == "real_event"
    assert record["x"] == 1
