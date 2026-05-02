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


def test_judge_timeout_default(tmp_codingbot_home):
    cfg = config.load()
    assert cfg.judge_timeout_secs == 15


def test_judge_timeout_override(tmp_codingbot_home):
    paths.config_file().write_text("judge_timeout_secs: 30\n", encoding="utf-8")
    config.load.cache_clear()
    cfg = config.load()
    assert cfg.judge_timeout_secs == 30


def test_risky_categories_default(tmp_codingbot_home):
    cfg = config.load()
    assert cfg.risky_categories == {
        "secret": True, "install": True, "priv": True,
    }


def test_risky_categories_partial_override(tmp_codingbot_home):
    paths.config_file().write_text(
        "risky_categories:\n  secret: false\n",
        encoding="utf-8",
    )
    config.load.cache_clear()
    cfg = config.load()
    assert cfg.risky_categories.get("secret") is False
    assert cfg.risky_categories.get("install", True) is True


def test_judge_enabled_default_true(tmp_codingbot_home):
    """0.9.0 P 사이클 — judge_enabled 미지정 시 default True (0.8.0 동작 보존)."""
    cfg = config.load()
    assert cfg.judge_enabled is True


def test_judge_enabled_yaml_override(tmp_codingbot_home):
    paths.config_file().write_text("judge_enabled: false\n", encoding="utf-8")
    config.load.cache_clear()
    cfg = config.load()
    assert cfg.judge_enabled is False
