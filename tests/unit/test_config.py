import pytest
from codingbot import config, paths


def test_defaults_when_no_file(tmp_codingbot_home):
    cfg = config.load()
    assert cfg.enabled is True
    assert cfg.time_limit_minutes == 30
    assert cfg.max_cycles_per_run == 50
    assert cfg.judge_model == "claude-haiku-4-5-20251001"
    assert "Read" in cfg.safe_tools
    assert "rm -rf" in cfg.risky_patterns
    assert cfg.api_key_env == "ANTHROPIC_API_KEY"
    assert cfg.log_level == "info"


def test_user_yaml_overrides_defaults(tmp_codingbot_home):
    paths.config_file().write_text(
        "time_limit_minutes: 60\nmax_cycles_per_run: 100\nlog_level: warn\n",
        encoding="utf-8",
    )
    cfg = config.load()
    assert cfg.time_limit_minutes == 60
    assert cfg.max_cycles_per_run == 100
    assert cfg.log_level == "warn"
    assert cfg.enabled is True   # 미지정은 기본값


def test_corrupt_yaml_falls_back_to_defaults(tmp_codingbot_home):
    paths.config_file().write_text("invalid: yaml: : :", encoding="utf-8")
    cfg = config.load()
    assert cfg.time_limit_minutes == 30  # 기본값


def test_partial_overrides_keep_defaults_for_lists(tmp_codingbot_home):
    paths.config_file().write_text(
        "safe_tools: [Read, MyCustomTool]\n", encoding="utf-8"
    )
    cfg = config.load()
    assert cfg.safe_tools == ["Read", "MyCustomTool"]
    assert "rm -rf" in cfg.risky_patterns  # 기본값 유지
