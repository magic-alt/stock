"""
Backtrader strategy that trades using a registered Qlib model.
"""
from __future__ import annotations

from typing import Dict, Any

import backtrader as bt
import pandas as pd

from src.mlops.qlib_inference import (
    extract_instrument_scores,
    predict_qlib_scores,
    resolve_registry_model,
    to_qlib_symbol,
)


class QlibRegistrySignalStrategy(bt.Strategy):
    """
    Use registered Qlib model predictions to drive trades.

    Logic:
    - score > threshold => long
    - score < -threshold => (optional) short
    - otherwise flat
    """

    params = dict(
        model_id=None,
        model_name="qlib-csi300",
        provider_uri="./qlib_data",
        region="cn",
        threshold=0.0,
        allow_short=False,
        position_pct=0.95,
        lot_size=100,
        min_hold_bars=1,
        cooldown_bars=0,
    )

    def __init__(self) -> None:
        self.data0 = self.datas[0]
        base_df = getattr(self.data0, "_dataname", None)
        if not isinstance(base_df, pd.DataFrame):
            raise ValueError("QlibRegistrySignalStrategy requires PandasData with underlying DataFrame")

        symbol = getattr(self.data0, "_name", "")
        qlib_symbol = to_qlib_symbol(symbol)
        start = base_df.index.min()
        end = base_df.index.max()

        model_meta = resolve_registry_model(model_id=self.p.model_id, model_name=self.p.model_name)
        if model_meta.framework != "qlib":
            raise ValueError(f"QlibRegistrySignalStrategy expects a qlib model, got {model_meta.framework}")

        scores = predict_qlib_scores(
            model_meta=model_meta,
            instruments=[qlib_symbol],
            start=start,
            end=end,
            provider_uri=self.p.provider_uri,
            region=self.p.region,
        )
        self._scores = extract_instrument_scores(scores, qlib_symbol)
        self._hold_bars = 0
        self._bars_since_trade = 999

    def _calc_size(self, price: float) -> int:
        if price <= 0:
            return 0
        target_value = float(self.broker.getvalue()) * float(self.p.position_pct)
        size = int(target_value / price)
        lot = int(self.p.lot_size) if int(self.p.lot_size) > 0 else 1
        if lot > 1:
            size = (size // lot) * lot
        return max(size, 0)

    def next(self) -> None:
        cur_dt = bt.num2date(self.data0.datetime[0])
        cur_ts = pd.Timestamp(cur_dt).normalize()
        if cur_ts not in self._scores.index:
            self._bars_since_trade += 1
            return

        score = float(self._scores.loc[cur_ts])
        threshold = float(self.p.threshold)
        target = 0
        if score > threshold:
            target = 1
        elif score < -threshold:
            target = -1

        pos = self.getposition(self.data0)
        if pos.size != 0:
            self._hold_bars += 1
        else:
            self._hold_bars = 0

        if self._bars_since_trade < int(self.p.cooldown_bars):
            self._bars_since_trade += 1
            return

        price = float(self.data0.close[0])
        size = self._calc_size(price)
        min_hold = int(self.p.min_hold_bars)

        if target > 0 and pos.size <= 0:
            if pos.size < 0:
                self.close(data=self.data0)
            if size > 0:
                self.buy(data=self.data0, size=size)
                self._bars_since_trade = 0
                self._hold_bars = 0
        elif target < 0 and pos.size >= 0 and bool(self.p.allow_short):
            if pos.size > 0:
                self.close(data=self.data0)
            if size > 0:
                self.sell(data=self.data0, size=size)
                self._bars_since_trade = 0
                self._hold_bars = 0
        elif target == 0 and pos.size != 0 and self._hold_bars >= min_hold:
            self.close(data=self.data0)
            self._bars_since_trade = 0
            self._hold_bars = 0

        self._bars_since_trade += 1


def _coerce_qlib_registry(params: Dict[str, Any]) -> Dict[str, Any]:
    params["model_id"] = params.get("model_id") or None
    params["model_name"] = str(params.get("model_name", "qlib-csi300"))
    params["provider_uri"] = str(params.get("provider_uri", "./qlib_data"))
    params["region"] = str(params.get("region", "cn"))
    params["threshold"] = float(params.get("threshold", 0.0))
    params["allow_short"] = bool(params.get("allow_short", False))
    params["position_pct"] = min(1.0, max(0.01, float(params.get("position_pct", 0.95))))
    params["lot_size"] = max(1, int(params.get("lot_size", 100)))
    params["min_hold_bars"] = max(0, int(params.get("min_hold_bars", 1)))
    params["cooldown_bars"] = max(0, int(params.get("cooldown_bars", 0)))
    return params
