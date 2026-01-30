"""
Train a FinRL agent and register the model.
"""
from __future__ import annotations

import argparse

from src.mlops.finrl_training import FinRLTrainingConfig, train_and_register_finrl
from src.mlops.model_registry import ModelRegistry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train FinRL model and register it.")
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols list, e.g. 000001.SZ 600519.SH")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--provider", default="akshare", help="Data provider")
    parser.add_argument("--cache-dir", default="./cache", help="Cache directory")
    parser.add_argument("--adj", default=None, help="Adjustment type (qfq/hfq)")
    parser.add_argument("--model", default="ppo", help="DRL model name (ppo/a2c/sac)")
    parser.add_argument("--timesteps", type=int, default=10000, help="Training timesteps")
    parser.add_argument("--artifact-dir", default=None, help="Artifact output directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = FinRLTrainingConfig(
        symbols=args.symbols,
        start=args.start,
        end=args.end,
        provider=args.provider,
        cache_dir=args.cache_dir,
        adj=args.adj,
        model_name=args.model,
        timesteps=args.timesteps,
        artifact_dir=args.artifact_dir,
    )
    registry = ModelRegistry()
    model = train_and_register_finrl(config, registry=registry)
    print(f"Registered FinRL model: {model.model_id} ({model.name} {model.version})")


if __name__ == "__main__":
    main()
