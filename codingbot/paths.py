"""모든 파일 경로를 단일 출처로 관리."""
import os
from pathlib import Path


def codingbot_home() -> Path:
    """런타임 디렉터리. CODINGBOT_HOME 환경변수 우선, 없으면 ~/.codingbot."""
    env = os.environ.get("CODINGBOT_HOME")
    if env:
        return Path(env)
    return Path.home() / ".codingbot"


def ensure_home() -> Path:
    home = codingbot_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def config_file() -> Path:
    return codingbot_home() / "config.yaml"


def state_file() -> Path:
    return codingbot_home() / "state.json"


def handoff_file() -> Path:
    return codingbot_home() / "handoff.md"


def log_file() -> Path:
    return codingbot_home() / "log.jsonl"


def stop_signal_file() -> Path:
    return codingbot_home() / ".codingbot-stop"


def lock_file() -> Path:
    return codingbot_home() / ".runner.lock"
