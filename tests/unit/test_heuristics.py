import pytest
from codingbot import heuristics


# classify_tool_call

def test_safe_tool_by_name(tmp_codingbot_home):
    assert heuristics.classify_tool_call("Read", {"file_path": "/a"}) == "safe"
    assert heuristics.classify_tool_call("Glob", {"pattern": "*.py"}) == "safe"
    assert heuristics.classify_tool_call("Grep", {"pattern": "x"}) == "safe"
    assert heuristics.classify_tool_call("TodoWrite", {"todos": []}) == "safe"


def test_safe_bash_commands(tmp_codingbot_home):
    safe_cmds = ["git status", "git log -n 5", "ls", "pwd", "cat README.md"]
    for cmd in safe_cmds:
        assert heuristics.classify_tool_call("Bash", {"command": cmd}) == "safe", cmd


def test_risky_patterns(tmp_codingbot_home):
    risky_cmds = [
        "rm -rf node_modules",
        "git push --force origin main",
        "git push -f",
        "DROP TABLE users",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
    ]
    for cmd in risky_cmds:
        assert heuristics.classify_tool_call("Bash", {"command": cmd}) == "risky", cmd


def test_unknown_tool(tmp_codingbot_home):
    assert heuristics.classify_tool_call("Edit", {"file_path": "x"}) == "unknown"
    assert heuristics.classify_tool_call("Bash", {"command": "npm install"}) == "unknown"


# is_clearly_done / is_clearly_continuing

def test_clearly_done_korean():
    assert heuristics.is_clearly_done("작업 완료했습니다.") is True
    assert heuristics.is_clearly_done("모든 단계 마쳤습니다.") is True
    assert heuristics.is_clearly_done("✓ 완료") is True


def test_clearly_done_english():
    assert heuristics.is_clearly_done("All done.") is True
    assert heuristics.is_clearly_done("Finished implementing.") is True


def test_not_clearly_done_when_continuing():
    assert heuristics.is_clearly_done("이제 다음 단계로 진행할게요") is False
    assert heuristics.is_clearly_done("Let me continue with the next step") is False


def test_clearly_continuing_korean():
    assert heuristics.is_clearly_continuing("이제 db.py를 살펴볼게요") is True
    assert heuristics.is_clearly_continuing("다음으로 api.py 정리하겠습니다") is True


def test_clearly_continuing_when_question_to_user_returns_false():
    assert heuristics.is_clearly_continuing("이렇게 하는 게 맞을까요?") is False
    assert heuristics.is_clearly_continuing("어떻게 할지 알려주세요") is False


def test_clearly_continuing_let_me():
    assert heuristics.is_clearly_continuing("Let me continue with the next step") is True
    assert heuristics.is_clearly_continuing("Let me implement the auth module") is True


def test_clearly_done_korean_informal():
    assert heuristics.is_clearly_done("작업 마쳤어요") is True
    assert heuristics.is_clearly_done("끝났어요!") is True
