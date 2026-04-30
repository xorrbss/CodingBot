"""핸드오프 파일 read/write/clear/exists."""
from typing import Optional

from codingbot import paths


def exists() -> bool:
    return paths.handoff_file().exists()


def read() -> Optional[str]:
    """파일이 없거나 빈 문자열이면 None."""
    f = paths.handoff_file()
    if not f.exists():
        return None
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return None
    return text if text.strip() else None


def write(content: str) -> None:
    paths.ensure_home()
    paths.handoff_file().write_text(content, encoding="utf-8")


def clear() -> None:
    f = paths.handoff_file()
    try:
        f.unlink()
    except FileNotFoundError:
        pass


def was_just_written() -> bool:
    """runner가 매 사이클 시작 시 clear()하므로, 파일 존재 = 이번 사이클 안에서 작성됨."""
    return exists()
