"""
快速浏览 ML 策略示例：
- 走步训练 MLWalkForwardStrategy
- 序列建模 DeepSequenceStrategy
- RegimeAdaptiveMLStrategy

运行：
    python examples/ml_strategy_gallery.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.strategies.ml_strategies import (
    DeepSequenceStrategy,
    MLWalkForwardStrategy,
    RegimeAdaptiveMLStrategy,
)


def _dummy_ohlcv(rows: int = 240) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=rows, freq="D")
    base = np.linspace(100, 115, rows) + np.random.normal(0, 1, rows)
    return pd.DataFrame(
        {
            "开盘": base + np.random.normal(0, 0.5, rows),
            "最高": base + np.random.uniform(0.5, 1.5, rows),
            "最低": base - np.random.uniform(0.5, 1.5, rows),
            "收盘": base + np.random.normal(0, 0.5, rows),
            "成交量": np.random.randint(1_000_000, 2_000_000, rows),
        },
        index=idx,
    )


def main() -> None:
    df = _dummy_ohlcv()

    wf = MLWalkForwardStrategy(label_horizon=1, min_train=120, prob_long=0.55)
    wf_res = wf.generate_signals(df.tail(150))

    deep = DeepSequenceStrategy(arch="lstm", lookback=30)
    deep_res = deep.generate_signals(df.tail(80))

    regime = RegimeAdaptiveMLStrategy(regime_window=25)
    regime_res = regime.generate_signals(df.tail(120))

    print("[MLWalkForward] 信号示例:")
    print(wf_res[["Signal", "ML_Prob"]].tail())
    print("\n[DeepSequence] 概率示例:")
    print(deep_res[["signal", "prob"]].tail())
    print("\n[RegimeAdaptive] 信号示例:")
    print(regime_res[["signal", "prob", "regime_vol"]].tail())


if __name__ == "__main__":
    main()
