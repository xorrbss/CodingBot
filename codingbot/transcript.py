"""Claude Code transcript .jsonl 파서.

Claude Code session JSONL의 각 line은 entry로, top-level `type` 필드와
선택적 `message: {role, content}`를 가진다. content는 두 형태:
  - str: 사용자가 직접 입력한 프롬프트
  - list[block]: assistant block list (`text` / `thinking` / `tool_use`)
                또는 user 응답 (tool_result 등)

이 모듈은 `user`/`assistant` 두 type만 골라 텍스트만 추출해
`{"role", "content": str}` 형태로 normalize한다. 추출 텍스트가 없는 entry
(thinking/tool_use/tool_result만 있는 라인)는 yield 안 한다 — 다운스트림
LLM judge / heuristics는 텍스트만 본다.

손상된 line은 건너뛰고 logger.warn으로 기록.
"""
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from codingbot import logger


def _extract_text(content: Any) -> Optional[str]:
    """message.content를 텍스트 한 덩어리로 변환.

    str 그대로, list면 type=='text' block만 골라 join. 텍스트가 하나도
    없으면 None — 호출 측이 그 entry를 skip하도록 한다.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: List[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    texts.append(t)
        return "\n\n".join(texts) if texts else None
    return None


def _normalize_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """raw jsonl entry를 {"role", "content": str}로. 대상 외/텍스트 없음 → None."""
    t = entry.get("type")
    if t not in ("user", "assistant"):
        return None
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return None
    text = _extract_text(msg.get("content"))
    if text is None:
        return None
    return {"role": t, "content": text}


def iter_messages(path: Path) -> Iterator[Dict[str, Any]]:
    """jsonl을 한 줄씩 읽어 normalized user/assistant 메시지를 yield."""
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    logger.warn("transcript_bad_line", path=str(path), line=lineno)
                    continue
                if not isinstance(entry, dict):
                    continue
                msg = _normalize_entry(entry)
                if msg is not None:
                    yield msg
    except OSError as e:
        logger.warn("transcript_read_error", path=str(path), error=str(e))


def read_recent(path: Path, n: int = 5) -> List[Dict[str, Any]]:
    msgs = list(iter_messages(path))
    return msgs[-n:]


def last_assistant_text(path: Path) -> Optional[str]:
    """마지막 assistant 텍스트. 현재 구현은 메모리 로딩 — I-4에서 tail로 전환 예정."""
    for msg in reversed(list(iter_messages(path))):
        if msg.get("role") == "assistant":
            content = msg.get("content")
            if isinstance(content, str) and content:
                return content
    return None
