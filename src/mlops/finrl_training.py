"""
FinRL training integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.data_sources.data_portal import DataPortal
from src.mlops.finrl_adapter import build_finrl_frame
from src.mlops.training import TrainingArtifact, FinRLTrainerAdapter, register_trained_model, build_artifact_path
from src.mlops.model_registry import ModelRegistry


@dataclass
class FinRLTrainingConfig:
    symbols: List[str]
    start: str
    end: str
    provider: str = "akshare"
    cache_dir: str = "./cache"
    adj: Optional[str] = None
    model_name: str = "ppo"
    timesteps: int = 10_000
    tech_indicator_list: Optional[List[str]] = None
    env_kwargs: Dict[str, float] = field(default_factory=dict)
    artifact_dir: Optional[str] = None


def build_finrl_training_frame(config: FinRLTrainingConfig) -> pd.DataFrame:
    portal = DataPortal(provider=config.provider, cache_dir=config.cache_dir, adj=config.adj)
    data_map = portal.get_data(config.symbols, config.start, config.end)
    return build_finrl_frame(data_map)


def train_finrl_model(config: FinRLTrainingConfig) -> TrainingArtifact:
    try:
        from finrl.meta.preprocessor.preprocessors import FeatureEngineer, data_split
        from finrl.meta.env_stock_trading.env_stocktrading import StockTradingEnv
        from finrl.agents.stablebaselines3.models import DRLAgent
        from finrl import config as finrl_config
    except Exception as exc:
        raise ImportError(
            "FinRL dependencies not available. Install finrl and its extras first."
        ) from exc

    df = build_finrl_training_frame(config)
    if df.empty:
        raise ValueError("Training data is empty. Check symbols/date range.")

    indicators = config.tech_indicator_list or getattr(finrl_config, "INDICATORS", [])
    fe = FeatureEngineer(
        use_technical_indicator=True,
        tech_indicator_list=indicators,
        use_turbulence=False,
        user_defined_feature=False,
    )
    processed = fe.preprocess_data(df).fillna(0)

    date_col = "date"
    tic_col = "tic"
    processed[date_col] = pd.to_datetime(processed[date_col]).dt.strftime("%Y-%m-%d")
    list_ticker = processed[tic_col].unique().tolist()
    list_date = list(pd.date_range(processed[date_col].min(), processed[date_col].max()).astype(str))
    combo = pd.DataFrame([(d, t) for d in list_date for t in list_ticker], columns=[date_col, tic_col])
    expanded = combo.merge(processed, on=[date_col, tic_col], how="left")
    expanded = expanded[expanded[date_col].isin(processed[date_col])].sort_values([date_col, tic_col])
    expanded = expanded.fillna(0)

    train_df = data_split(expanded, config.start, config.end)
    stock_dim = len(train_df[tic_col].unique())
    state_space = 1 + 2 * stock_dim + len(indicators) * stock_dim
    env_kwargs = {
        "hmax": 100,
        "initial_amount": 100000,
        "num_stock_shares": [0] * stock_dim,
        "buy_cost_pct": [0.001] * stock_dim,
        "sell_cost_pct": [0.001] * stock_dim,
        "state_space": state_space,
        "stock_dim": stock_dim,
        "tech_indicator_list": indicators,
        "action_space": stock_dim,
        "reward_scaling": 1e-4,
    }
    env_kwargs.update(config.env_kwargs)
    env_train = StockTradingEnv(df=train_df, **env_kwargs)
    env_train_sb, _ = env_train.get_sb_env()

    agent = DRLAgent(env=env_train_sb)
    model = agent.get_model(config.model_name)
    trained = agent.train_model(
        model=model,
        tb_log_name=config.model_name,
        total_timesteps=config.timesteps,
    )

    artifact_dir = config.artifact_dir
    artifact_path = build_artifact_path(artifact_dir or "./cache/mlops/artifacts", config.model_name, "zip")
    trained.save(artifact_path)
    signature = {"features": ["open", "high", "low", "close", "volume"] + indicators}
    return TrainingArtifact(
        artifact_path=artifact_path,
        metrics={"timesteps": config.timesteps, "model_name": config.model_name},
        signature=signature,
        training_config={"symbols": config.symbols, "start": config.start, "end": config.end},
        data_fingerprint=f"{config.start}:{config.end}:{','.join(config.symbols)}",
    )


def train_and_register_finrl(config: FinRLTrainingConfig, registry: Optional[ModelRegistry] = None):
    trainer = FinRLTrainerAdapter(
        name=f"finrl-{config.model_name}",
        train_fn=lambda: train_finrl_model(config),
        training_config={"symbols": config.symbols, "start": config.start, "end": config.end},
        data_fingerprint=f"{config.start}:{config.end}:{','.join(config.symbols)}",
    )
    return register_trained_model(trainer, registry=registry)
