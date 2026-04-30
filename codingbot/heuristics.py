"""규칙 기반 휴리스틱. 순수 함수. config의 safe/risky 리스트 참조."""
import re
from typing import Any, Dict

from codingbot import config


_SAFE_BASH_PREFIXES = (
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git show",
    "ls",
    "pwd",
    "cat ",
    "echo ",
    "which ",
    "whoami",
    "date",
    "head ",
    "tail ",
    "wc ",
)

_QUESTION_PATTERNS = [
    r"\?",
    r"맞을까요",
    r"알려주세요",
    r"확인해주세요",
    r"어떻게 (할|하면|진행)",
]

_DONE_PATTERNS = [
    r"완료(했|되었|됐|입니다)",
    r"마쳤(습니다|어요|네요)",
    r"끝(났|냈)(습니다|어요|네요)",
    r"✓\s*완료",
    r"\bAll done\b",
    r"\bFinished\b",
    r"\bComplete[d]?\b",
]

_CONTINUING_PATTERNS = [
    r"이제\s*[가-힣A-Za-z]+",
    r"다음(으로|에)\s*[가-힣A-Za-z]+",
    r"계속해서",
    r"이어서",
    r"\bNext,?\s+",
    r"\bNow,?\s+(I|let|let's)",
    r"\bLet me\s+(continue|move|proceed|start|implement|add|update|refactor|fix|create|write)",
    r"\bI(['']ll|'ll| will)\s+(continue|move|proceed|start|implement|add|update|refactor|fix|create|write)",
]


def classify_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """returns 'safe' | 'risky' | 'unknown'."""
    cfg = config.load()

    if tool_name in cfg.safe_tools:
        return "safe"

    if tool_name == "Bash":
        cmd = str(tool_input.get("command", ""))

        for pattern in cfg.risky_patterns:
            if pattern in cmd:
                return "risky"

        if any(cmd == p.rstrip() or cmd.startswith(p) for p in _SAFE_BASH_PREFIXES):
            return "safe"

        return "unknown"

    flat_input = " ".join(str(v) for v in tool_input.values())
    for pattern in cfg.risky_patterns:
        if pattern in flat_input:
            return "risky"

    return "unknown"


def is_clearly_done(text: str) -> bool:
    if not text:
        return False
    if _has_question(text):
        return False
    if any(re.search(p, text) for p in _CONTINUING_PATTERNS):
        return False
    return any(re.search(p, text) for p in _DONE_PATTERNS)


def is_clearly_continuing(text: str) -> bool:
    if not text:
        return False
    if _has_question(text):
        return False
    return any(re.search(p, text) for p in _CONTINUING_PATTERNS)


def _has_question(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _QUESTION_PATTERNS)
