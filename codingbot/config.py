"""사용자 설정 로딩. YAML + 기본값."""
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List

import yaml

from codingbot import logger, paths


DEFAULT_SAFE_TOOLS = ["Read", "Glob", "Grep", "TodoWrite"]
DEFAULT_RISKY_PATTERNS = [
    "rm -rf",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "DROP TABLE",
    "DROP DATABASE",
    ":(){:|:&};:",
    "mkfs",
    "dd if=",
]


@dataclass
class Config:
    enabled: bool = True
    time_limit_minutes: int = 30
    max_cycles_per_run: int = 50
    judge_model: str = "claude-haiku-4-5-20251001"
    judge_timeout_secs: int = 15
    judge_enabled: bool = True
    api_key_env: str = "ANTHROPIC_API_KEY"
    safe_tools: List[str] = field(default_factory=lambda: list(DEFAULT_SAFE_TOOLS))
    risky_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_RISKY_PATTERNS))
    risky_categories: Dict[str, Any] = field(default_factory=lambda: {
        "secret": True, "install": True, "priv": True,
    })
    log_level: str = "info"


@lru_cache(maxsize=1)
def load() -> Config:
    """config.yaml 로딩. 누락/손상 시 기본값.

    Hook hot path에서 한 프로세스 안에 3-5번 호출되므로 캐시.
    프로세스 수명 동안만 유효 (hook subprocess는 짧으므로 신선도 OK).
    테스트는 conftest의 tmp_codingbot_home fixture에서 cache_clear() 호출.
    """
    cfg = Config()
    cfg_path = paths.config_file()
    if not cfg_path.exists():
        return cfg
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.warn("config_corrupt", error=str(e), fallback="defaults")
        return cfg

    for key in (
        "enabled",
        "time_limit_minutes",
        "max_cycles_per_run",
        "judge_model",
        "judge_timeout_secs",
        "judge_enabled",
        "api_key_env",
        "safe_tools",
        "risky_patterns",
        "risky_categories",
        "log_level",
    ):
        if key in data:
            setattr(cfg, key, data[key])
    return cfg
