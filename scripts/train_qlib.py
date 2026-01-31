"""
Train a Qlib model and register the model.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.mlops.qlib_training import QlibTrainingConfig, train_and_register_qlib
from src.mlops.model_registry import ModelRegistry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Qlib model and register it.")
    parser.add_argument("--provider-uri", required=True, help="Qlib data provider URI")
    parser.add_argument("--region", default="cn", help="Qlib region")
    parser.add_argument("--market", default="csi300", help="Market/instruments")
    parser.add_argument("--artifact-dir", default=None, help="Artifact output directory")
    parser.add_argument("--experiment", default="qlib_lgbm", help="Qlib experiment name")
    parser.add_argument("--train-start", default="2008-01-01")
    parser.add_argument("--train-end", default="2014-12-31")
    parser.add_argument("--valid-start", default="2015-01-01")
    parser.add_argument("--valid-end", default="2016-12-31")
    parser.add_argument("--test-start", default="2017-01-01")
    parser.add_argument("--test-end", default="2018-12-31")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = QlibTrainingConfig(
        provider_uri=args.provider_uri,
        region=args.region,
        market=args.market,
        experiment_name=args.experiment,
        artifact_dir=args.artifact_dir,
        train_start=args.train_start,
        train_end=args.train_end,
        valid_start=args.valid_start,
        valid_end=args.valid_end,
        test_start=args.test_start,
        test_end=args.test_end,
    )
    registry = ModelRegistry()
    model = train_and_register_qlib(config, registry=registry)
    print(f"Registered Qlib model: {model.model_id} ({model.name} {model.version})")


if __name__ == "__main__":
    main()
