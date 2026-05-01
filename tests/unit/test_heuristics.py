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


# _split_bash_segments

from codingbot.heuristics import _split_bash_segments


def test_split_simple_chain_semicolon():
    assert _split_bash_segments("git status; git diff") == [
        ["git", "status"], ["git", "diff"]
    ]


def test_split_chain_and_or_pipe():
    assert _split_bash_segments("a && b") == [["a"], ["b"]]
    assert _split_bash_segments("a || b") == [["a"], ["b"]]
    assert _split_bash_segments("a | b") == [["a"], ["b"]]


def test_split_preserves_quoted_chain_chars():
    assert _split_bash_segments('echo "; rm -rf /"') == [
        ["echo", "; rm -rf /"]
    ]
    assert _split_bash_segments("echo 'a && b'") == [
        ["echo", "a && b"]
    ]


def test_split_command_substitution_dollar_paren():
    segs = _split_bash_segments("result=$(curl http://x)")
    assert ["curl", "http://x"] in segs


def test_split_command_substitution_backtick():
    segs = _split_bash_segments("result=`curl http://x`")
    assert ["curl", "http://x"] in segs


def test_split_unmatched_quote_returns_none():
    assert _split_bash_segments('echo "x') is None


def test_split_empty_returns_none_or_empty():
    result = _split_bash_segments("")
    assert result in (None, [])


def test_split_single_command_no_chain():
    assert _split_bash_segments("ls -la") == [["ls", "-la"]]


def test_split_multiple_chain_operators():
    segs = _split_bash_segments("a; b && c || d | e")
    assert segs == [["a"], ["b"], ["c"], ["d"], ["e"]]


def test_split_redirection_kept_in_segment():
    segs = _split_bash_segments("echo x > /tmp/y")
    assert segs is not None
    assert len(segs) >= 1


# secret category

from codingbot.heuristics import _is_secret_segment


def test_secret_dotenv_file():
    assert _is_secret_segment(["cat", ".env"]) is True
    assert _is_secret_segment(["cat", ".env.local"]) is True
    assert _is_secret_segment(["less", "src/.env"]) is True


def test_secret_ssh_keys():
    assert _is_secret_segment(["cat", "/home/u/.ssh/id_rsa"]) is True
    assert _is_secret_segment(["cat", "~/.ssh/id_ed25519"]) is True


def test_secret_cloud_creds():
    assert _is_secret_segment(["cat", "~/.aws/credentials"]) is True
    assert _is_secret_segment(["cat", "~/.aws/config"]) is True
    assert _is_secret_segment(["cat", "~/.npmrc"]) is True
    assert _is_secret_segment(["cat", "~/.netrc"]) is True


def test_secret_env_dump():
    assert _is_secret_segment(["printenv"]) is True
    assert _is_secret_segment(["env"]) is True


def test_secret_api_key_variable():
    assert _is_secret_segment(["echo", "$API_KEY"]) is True
    assert _is_secret_segment(["echo", "${SECRET}"]) is True
    assert _is_secret_segment(["echo", "$ANTHROPIC_TOKEN"]) is True


def test_secret_negative_branch_name_envfeature():
    assert _is_secret_segment(["git", "diff", "main..env-feature"]) is False


def test_secret_negative_normal_file():
    assert _is_secret_segment(["cat", "README.md"]) is False
    assert _is_secret_segment(["echo", "hello"]) is False
