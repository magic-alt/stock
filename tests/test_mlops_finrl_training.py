from __future__ import annotations

from src.mlops.finrl_training import FinRLTrainingConfig


def test_finrl_training_config_defaults() -> None:
    config = FinRLTrainingConfig(symbols=["AAA"], start="2024-01-01", end="2024-12-31")
    assert config.provider == "akshare"
    assert config.model_name == "ppo"
