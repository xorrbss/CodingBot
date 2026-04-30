"""Claude Code transcript .jsonl 파서. 손상된 줄은 건너뜀.

# TODO: [BLOCKED]
#   violated: 4 (구조 무결성), 8 (편법 금지), 가정 금지
#   reason:
#     이 파서는 `{"role": "...", "content": str}` 형식을 가정하지만,
#     실제 Claude Code session JSONL은
#     `{"type": "assistant", "message": {...}, "content": [text/tool_use blocks]}`
#     형식임 (final review I-5). 단위 테스트 fixture가 가정한 형식에 맞춰져 있어
#     테스트는 통과하지만, 첫 E2E 실행에서 last_assistant_text()가 None을 반환할
#     가능성이 높음.
#   required_change:
#     실제 Claude Code session 파일 1건을 확보해 정확한 스키마를 확인한 뒤
#     iter_messages()의 yield 형태(또는 별도 normalize 단계)와 last_assistant_text()를
#     실제 스키마에 맞춰 재구성. fixture(tests/unit/test_transcript.py)도
#     실제 스키마로 갱신. 추정만으로 "양쪽 다 지원" 같은 분기 코드는 추가하지 말 것
#     (편법 금지). 0.1.1 마일스톤에서 해결.
"""
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
