"""규칙 기반 휴리스틱. 순수 함수. config의 safe/risky 리스트 참조."""
import re
import shlex
from typing import Any, Dict

from codingbot import config


_CHAIN_OPS = {";", "&&", "||", "|"}


def _split_bash_segments(cmd: str):
    """Bash 명령을 segment(argv list) 단위로 분해.

    Chain operators(;, &&, ||, |)와 command substitution($(), backtick)을
    별도 segment로 분리. shlex로 1차 토큰화하여 quoting을 보존한다.
    파싱 실패 시 None을 반환 (호출자가 unknown으로 매핑).
    """
    if not cmd or not cmd.strip():
        return None

    inner_cmds = []

    def _extract_substitutions(s: str):
        result = []
        i = 0
        while i < len(s):
            if s[i] == "$" and i + 1 < len(s) and s[i + 1] == "(":
                end = s.find(")", i + 2)
                if end < 0:
                    return None
                inner_cmds.append(s[i + 2 : end])
                result.append("__SUBST__")
                i = end + 1
            elif s[i] == "`":
                end = s.find("`", i + 1)
                if end < 0:
                    return None
                inner_cmds.append(s[i + 1 : end])
                result.append("__SUBST__")
                i = end + 1
            else:
                result.append(s[i])
                i += 1
        return "".join(result)

    outer = _extract_substitutions(cmd)
    if outer is None:
        return None

    try:
        lexer = shlex.shlex(outer, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None

    segments = []
    current = []
    for tok in tokens:
        if tok in _CHAIN_OPS:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)

    for inner in inner_cmds:
        inner_segs = _split_bash_segments(inner)
        if inner_segs:
            segments.extend(inner_segs)

    return segments if segments else None


_SECRET_FILE_PATTERNS = [
    re.compile(r"(^|[/\\])\.env(\.|$)"),
    re.compile(r"id_(rsa|ed25519|ecdsa|dsa)(\.pub)?$"),
    re.compile(r"\.aws[/\\](credentials|config)$"),
    re.compile(r"(^|[/\\])\.npmrc$"),
    re.compile(r"(^|[/\\])\.pypirc$"),
    re.compile(r"(^|[/\\])\.netrc$"),
]
_SECRET_VAR_PATTERN = re.compile(
    r"\$\{?[A-Za-z_]*?(API[_-]?KEY|SECRET|TOKEN|PASSWORD)[A-Za-z_]*\}?"
)
_ENV_DUMP_COMMANDS = {"printenv", "env"}


def _is_secret_segment(argv):
    if not argv:
        return False
    if argv[0] in _ENV_DUMP_COMMANDS:
        return len(argv) == 1 or argv[1].startswith("-")
    for tok in argv:
        for p in _SECRET_FILE_PATTERNS:
            if p.search(tok):
                return True
        if _SECRET_VAR_PATTERN.search(tok):
            return True
    return False


_INSTALL_MANAGERS = {
    "pip", "pip3", "pipx",
    "npm", "yarn", "pnpm",
    "apt", "apt-get", "dpkg",
    "brew",
    "choco", "winget", "scoop",
    "gem", "cargo", "go",
}
_INSTALL_SUBCOMMANDS = {"install", "add", "i", "upgrade", "update"}


def _is_install_segment(argv):
    if len(argv) < 2:
        return False
    if argv[0] not in _INSTALL_MANAGERS:
        return False
    return argv[1] in _INSTALL_SUBCOMMANDS


_PRIV_COMMANDS = {"sudo", "runas", "doas", "su", "setcap", "setuid"}
_CHMOD_BAD_MODE = re.compile(r"^[+-]?7?77\d?$|^a\+w$")
_CHMOD_PLUS_X_SYSTEM = re.compile(r"^(/|\$HOME|~)")
_CHOWN_ROOT = re.compile(r"^(root|0)(:\w*)?$|^:0$")


def _is_priv_segment(argv):
    if not argv:
        return False
    if argv[0] in _PRIV_COMMANDS:
        return True
    if argv[0] == "chmod":
        for tok in argv[1:]:
            if _CHMOD_BAD_MODE.match(tok):
                return True
        if "+x" in argv[1:]:
            for tok in argv[1:]:
                if _CHMOD_PLUS_X_SYSTEM.match(tok):
                    return True
        return False
    if argv[0] == "chown":
        for tok in argv[1:]:
            if _CHOWN_ROOT.match(tok):
                return True
        return False
    return False


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


def _seg_is_safe_prefix(argv) -> bool:
    seg_str = " ".join(argv)
    return any(
        seg_str == p.rstrip() or seg_str.startswith(p)
        for p in _SAFE_BASH_PREFIXES
    )


def _classify_bash(cmd: str, cfg) -> str:
    segments = _split_bash_segments(cmd)
    if not segments:
        return "unknown"

    cats = cfg.risky_categories or {}

    if cats.get("secret", True) and any(_is_secret_segment(a) for a in segments):
        return "risky"
    if cats.get("install", True):
        if any(_is_install_segment(a) for a in segments):
            return "risky"
        # curl|sh 류 — 다단계 chain의 후반부에 단독 shell interpreter
        if len(segments) >= 2 and any(
            seg in (["sh"], ["bash"], ["zsh"]) for seg in segments[1:]
        ):
            return "risky"
    if cats.get("priv", True) and any(_is_priv_segment(a) for a in segments):
        return "risky"

    for argv in segments:
        # legacy pattern은 unquoted token에 한정 — quoted("rm -rf" 류) 안의 위험
        # 문자열은 실행되지 않으므로 false positive 방지.
        safe_tokens = [t for t in argv if " " not in t]
        seg_str = " ".join(safe_tokens)
        for p in cfg.risky_patterns:
            if p in seg_str:
                return "risky"

    if all(_seg_is_safe_prefix(a) for a in segments):
        return "safe"

    return "unknown"


def classify_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """returns 'safe' | 'risky' | 'unknown'."""
    cfg = config.load()

    if tool_name in cfg.safe_tools:
        return "safe"

    if tool_name == "Bash":
        cmd = str(tool_input.get("command", ""))
        return _classify_bash(cmd, cfg)

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
