"""
ML Enhanced strategy examples:
- MLEnhancedStrategy
- MLEnsembleStrategy

Run:
    python examples/ml_enhanced_examples.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.strategies.ml_enhanced_strategy import MLEnhancedStrategy, MLEnsembleStrategy


def _dummy_ohlcv(rows: int = 240) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=rows, freq="D")
    base = np.linspace(100, 118, rows) + np.random.normal(0, 0.8, rows)
    return pd.DataFrame(
        {
            "open": base + np.random.normal(0, 0.5, rows),
            "high": base + np.random.uniform(0.5, 1.5, rows),
            "low": base - np.random.uniform(0.5, 1.5, rows),
            "close": base + np.random.normal(0, 0.5, rows),
            "volume": np.random.randint(800_000, 1_800_000, rows),
        },
        index=idx,
    )


def main() -> None:
    df = _dummy_ohlcv()

    enhanced = MLEnhancedStrategy(min_train=120, prob_threshold=0.60)
    enhanced_res = enhanced.generate_signals(df.tail(160))

    ensemble = MLEnsembleStrategy(min_train=120, prob_threshold=0.60)
    ensemble_res = ensemble.generate_signals(df.tail(160))

    print("[MLEnhanced] 置信度示例:")
    print(enhanced_res[["Signal", "Probability"]].tail())
    print("\n[MLEnsemble] 置信度示例:")
    print(ensemble_res[["Signal", "Probability"]].tail())


if __name__ == "__main__":
    main()
