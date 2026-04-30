"""Claude Code transcript .jsonl 파서. 손상된 줄은 건너뜀."""
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from codingbot import logger


def iter_messages(path: Path) -> Iterator[Dict[str, Any]]:
    """전체 transcript를 한 메시지씩 yield. 손상 줄은 스킵."""
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.warn("transcript_bad_line", path=str(path), line=lineno)
    except OSError as e:
        logger.warn("transcript_read_error", path=str(path), error=str(e))


def read_recent(path: Path, n: int = 5) -> List[Dict[str, Any]]:
    msgs = list(iter_messages(path))
    return msgs[-n:]


def last_assistant_text(path: Path) -> Optional[str]:
    for msg in reversed(list(iter_messages(path))):
        if msg.get("role") == "assistant":
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return None
