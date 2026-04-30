"""사용자 설정 로딩. YAML + 기본값."""
from dataclasses import dataclass, field
from typing import List

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
    api_key_env: str = "ANTHROPIC_API_KEY"
    safe_tools: List[str] = field(default_factory=lambda: list(DEFAULT_SAFE_TOOLS))
    risky_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_RISKY_PATTERNS))
    log_level: str = "info"


def load() -> Config:
    """config.yaml 로딩. 누락/손상 시 기본값."""
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
        "api_key_env",
        "safe_tools",
        "risky_patterns",
        "log_level",
    ):
        if key in data:
            setattr(cfg, key, data[key])
    return cfg
