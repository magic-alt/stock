"""
Strategy Modules

Defines the StrategyModule dataclass and legacy strategies
(TurningPoint, RiskParity) that are specific to this framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence, Tuple, Type

import numpy as np
import pandas as pd

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc

from src.strategies.backtrader_registry import BACKTRADER_STRATEGY_REGISTRY


# ---------------------------------------------------------------------------
# Generic Backtrader Data Feed
# ---------------------------------------------------------------------------

class GenericPandasData(bt.feeds.PandasData):
    """Backtrader data feed that expects the normalised pandas structure."""
    params = (
        ("datetime", None),
        ("open", -1),
        ("high", -1),
        ("low", -1),
        ("close", -1),
        ("volume", -1),
        ("openinterest", -1)
    )


# ---------------------------------------------------------------------------
# Turning Point Helper Utilities
# ---------------------------------------------------------------------------

def rolling_vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Compute a rolling VWAP to help with mean-reversion style filters."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["volume"]
    denom = df["volume"].rolling(window, min_periods=1).sum().replace(0, np.nan)
    vwap = pv.rolling(window, min_periods=1).sum() / denom
    return vwap.bfill().ffill()


def compute_signal_frame(
    df: pd.DataFrame,
    gap_th: float = 0.015,
    intraday_rev_th: float = 0.003,
    vol_surge: float = 1.3,
    vwap_window: int = 20,
) -> pd.DataFrame:
    """Derive the turning-point scoring frame used by the multi-symbol strategy."""
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        series = out[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        out[col] = pd.to_numeric(series, errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out["volume"] = out["volume"].fillna(0.0)
    out["prev_close"] = out["close"].shift(1)
    out["gap_up"] = (out["open"] >= out["prev_close"] * (1 + gap_th)).astype(int)
    out["gap_down"] = (out["open"] <= out["prev_close"] * (1 - gap_th)).astype(int)
    out["bearish_reversal"] = (
        (out["gap_up"] == 1)
        & ((out["close"] < out["open"] * (1 - intraday_rev_th)) | (out["close"] < out["prev_close"]))
    ).astype(int)
    out["bullish_reversal"] = (
        (out["gap_down"] == 1)
        & ((out["close"] > out["open"] * (1 + intraday_rev_th)) | (out["close"] > out["prev_close"]))
    ).astype(int)
    vol_mean = out["volume"].rolling(20, min_periods=1).mean()
    out["vol_surge_flag"] = (out["volume"] >= vol_mean * vol_surge).astype(int)
    out["vwap"] = rolling_vwap(out, vwap_window)
    out["long_ok"] = (
        (out["bullish_reversal"] == 1)
        & (out["close"] > out["vwap"])
        & (out["vol_surge_flag"] == 1)
    ).astype(int)
    out["short_ok"] = (
        (out["bearish_reversal"] == 1)
        & (out["close"] < out["vwap"])
        & (out["vol_surge_flag"] == 1)
    ).astype(int)
    body_strength = (out["close"] - out["open"]).abs() / out["prev_close"].replace(0, np.nan)
    vol_score = (out["volume"] / vol_mean.replace(0, np.nan)).clip(upper=3)
    vwap_bonus = 0.5 * ((out["long_ok"] == 1) | (out["short_ok"] == 1))
    out["score"] = body_strength.fillna(0) + vol_score.fillna(0) + vwap_bonus.astype(float)
    return out


@dataclass
class OrderIntent:
    """Simple container publishing the target side for each symbol."""
    symbol: str
    side: str


def decide_orders(
    df_map: Dict[str, pd.DataFrame],
    topn: int = 2,
    allow_short: bool = False,
    gap: float = 0.015,
    reversal: float = 0.003,
    vol_surge: float = 1.3,
    vwap_window: int = 20,
) -> List[OrderIntent]:
    """Convert recent price action into position intents for each symbol."""
    scored: List[Tuple[str, float, int, int]] = []
    for sym, df in df_map.items():
        sig = compute_signal_frame(df, gap_th=gap, intraday_rev_th=reversal, vol_surge=vol_surge, vwap_window=vwap_window)
        today = sig.iloc[-1]
        score = float(today["score"]) if (today["long_ok"] or today["short_ok"]) else 0.0
        scored.append((sym, score, int(today["long_ok"]), int(today["short_ok"])))
    selected = [x for x in scored if x[1] > 0]
    selected.sort(key=lambda x: x[1], reverse=True)
    keep = {sym for sym, *_ in selected[:topn]}
    intents: List[OrderIntent] = []
    for sym, score, long_ok, short_ok in scored:
        if sym in keep:
            if long_ok:
                intents.append(OrderIntent(symbol=sym, side="long"))
            elif allow_short and short_ok:
                intents.append(OrderIntent(symbol=sym, side="short"))
            else:
                intents.append(OrderIntent(symbol=sym, side="flat"))
        else:
            intents.append(OrderIntent(symbol=sym, side="flat"))
    return intents


def decide_orders_from_signals(
    sig_map_today: Dict[str, Tuple[float, int, int]],
    topn: int = 2,
    allow_short: bool = False,
) -> List[OrderIntent]:
    """
    根据已经预计算的当日信号（score/long_ok/short_ok）做多空/空仓决策。
    sig_map_today[sym] = (score, long_ok, short_ok)
    """
    selected = [(sym, s, l, sh) for sym, (s, l, sh) in sig_map_today.items() if s > 0]
    selected.sort(key=lambda x: x[1], reverse=True)
    keep = {sym for sym, *_ in selected[:max(1, int(topn))]}
    intents: List[OrderIntent] = []
    for sym, (score, long_ok, short_ok) in ((k, sig_map_today[k]) for k in sig_map_today.keys()):
        if sym in keep:
            if long_ok:
                intents.append(OrderIntent(symbol=sym, side="long"))
            elif allow_short and short_ok:
                intents.append(OrderIntent(symbol=sym, side="short"))
            else:
                intents.append(OrderIntent(symbol=sym, side="flat"))
        else:
            intents.append(OrderIntent(symbol=sym, side="flat"))
    return intents


# ---------------------------------------------------------------------------
# Strategy Module Dataclass
# ---------------------------------------------------------------------------

@dataclass
class StrategyModule:
    """Metadata wrapper describing how a strategy integrates with the engine."""
    name: str
    description: str
    strategy_cls: Type[bt.Strategy]
    param_names: Sequence[str]
    defaults: Dict[str, Any]
    multi_symbol: bool = False
    grid_defaults: Dict[str, Sequence[Any]] = field(default_factory=dict)
    coercer: Callable[[Dict[str, Any]], Dict[str, Any]] = staticmethod(lambda p: p)

    def coerce(self, params: Dict[str, Any]) -> Dict[str, Any]:
        merged = {**self.defaults, **params}
        return self.coercer(dict(merged))

    def add_data(self, cerebro: bt.Cerebro, data_map: Dict[str, pd.DataFrame]) -> None:
        if not data_map:
            raise ValueError(f"No data available for strategy '{self.name}'. data_map is empty.")
        
        if self.multi_symbol:
            for sym in sorted(data_map.keys()):
                feed = GenericPandasData(dataname=data_map[sym])
                cerebro.adddata(feed, name=sym)
        else:
            sym = next(iter(sorted(data_map.keys())))
            feed = GenericPandasData(dataname=data_map[sym])
            cerebro.adddata(feed, name=sym)

    def add_strategy(self, cerebro: bt.Cerebro, params: Dict[str, Any]) -> None:
        cerebro.addstrategy(self.strategy_cls, **params)


# ---------------------------------------------------------------------------
# Intent Logger (for Turning Point Strategy)
# ---------------------------------------------------------------------------

class IntentLogger(bt.Analyzer):
    """Analyzer that keeps a day-by-day record of portfolio intents."""

    def start(self) -> None:
        self.logs: List[Tuple[pd.Timestamp, Dict[str, str]]] = []

    def next(self) -> None:
        strat = self.strategy
        record: Dict[str, str] = {}
        for data in strat.datas:
            pos = strat.getposition(data)
            record[data._name] = "pos>0" if pos.size > 0 else "flat"
        dt = bt.num2date(self.strategy.datas[0].datetime[0])
        self.logs.append((pd.Timestamp(dt), record))

    def get_analysis(self) -> Dict[str, Any]:
        return {"logs": self.logs}


# ---------------------------------------------------------------------------
# Turning Point Strategy
# ---------------------------------------------------------------------------

class TurningPointBT(bt.Strategy):
    """Backtrader implementation of the signal-engine driven turning point play."""
    params = dict(
        topn=2,
        gap=0.015,
        reversal=0.003,
        vol_surge=1.3,
        vwap_window=20,
        allow_short=False,
        risk_per_trade=0.1,
        atr_period=14,
        atr_sl=2.0,
        atr_tp=None,
        use_atr_position_sizing=True,
        max_pos_value_frac=0.3,
        bull_filter=False,
        bull_filter_benchmark=False,
        benchmark_data_name="__benchmark__",
        regime_period=200,
        regime_use_slope=False,
        regime_slope_period=20,
        min_holding_bars=0,
        cooldown_bars=0,
    )

    def __init__(self) -> None:
        self._names = {data._name or f"sym{idx}": data for idx, data in enumerate(self.datas)}
        self._sig_map: Dict[str, pd.DataFrame] = {}
        for name, data in self._names.items():
            try:
                base_df = getattr(data, "_dataname", None)
                if isinstance(base_df, pd.DataFrame):
                    df_full = base_df[["open", "high", "low", "close", "volume"]].copy()
                    sig_full = compute_signal_frame(
                        df_full,
                        gap_th=self.p.gap,
                        intraday_rev_th=self.p.reversal,
                        vol_surge=self.p.vol_surge,
                        vwap_window=self.p.vwap_window,
                    )
                    self._sig_map[name] = sig_full[["long_ok", "short_ok", "score"]].copy()
                else:
                    self._sig_map[name] = None  # type: ignore
            except Exception:
                self._sig_map[name] = None  # type: ignore

    def next(self) -> None:
        cur_dt = bt.num2date(self.datas[0].datetime[0])
        cur_ts = pd.Timestamp(cur_dt)

        if any(self._sig_map.get(n) is not None for n in self._names):
            sig_map_today: Dict[str, Tuple[float, int, int]] = {}
            for name, data in self._names.items():
                sig = self._sig_map.get(name)
                if sig is None or sig.empty:
                    continue
                try:
                    loc = sig.index.get_loc(cur_ts, method="pad")
                    row = sig.iloc[loc]
                except Exception:
                    continue
                score = float(row.get("score", 0.0))
                long_ok = int(row.get("long_ok", 0))
                short_ok = int(row.get("short_ok", 0))
                sig_map_today[name] = (score, long_ok, short_ok)
            if not sig_map_today:
                return
            intents = decide_orders_from_signals(
                sig_map_today,
                topn=self.p.topn,
                allow_short=self.p.allow_short,
            )
        else:
            df_map: Dict[str, pd.DataFrame] = {}
            for name, data in self._names.items():
                if len(data) < 30:
                    continue
                df_map[name] = pd.DataFrame(
                    {
                        "open": data.open.get(size=30),
                        "high": data.high.get(size=30),
                        "low": data.low.get(size=30),
                        "close": data.close.get(size=30),
                        "volume": data.volume.get(size=30),
                    }
                )
            if not df_map:
                return
            intents = decide_orders(
                df_map,
                topn=self.p.topn,
                allow_short=self.p.allow_short,
                gap=self.p.gap,
                reversal=self.p.reversal,
                vol_surge=self.p.vol_surge,
                vwap_window=self.p.vwap_window,
            )
            
        atr_ind = bt.indicators.ATR(self.datas[0], period=self.p.atr_period)
        ema200 = bt.indicators.EMA(self.datas[0].close, period=self.p.regime_period)
        bench = next((d for d in self.datas if getattr(d, "_name", "") == self.p.benchmark_data_name), None)
        bench_ema200 = bt.indicators.EMA(bench.close, period=self.p.regime_period) if bench is not None else None
        
        for intent in intents:
            data = self._names.get(intent.symbol)
            if data is None:
                continue
            pos = self.getposition(data)
            price = data.close[0]
            atr = float(atr_ind[0]) if atr_ind[0] else 0.0
            
            if not self.p.bull_filter:
                bullish = True
            else:
                if self.p.bull_filter_benchmark and bench_ema200 is not None and bench is not None:
                    bench_close = float(bench.close[0])
                    ema_now = float(bench_ema200[0])
                    if self.p.regime_use_slope and len(bench_ema200) > self.p.regime_slope_period:
                        ema_past = float(bench_ema200[-self.p.regime_slope_period])
                        bullish = (bench_close > ema_now) and (ema_now > ema_past)
                    else:
                        bullish = bench_close > ema_now
                else:
                    ema_now = float(ema200[0])
                    if self.p.regime_use_slope and len(ema200) > self.p.regime_slope_period:
                        ema_past = float(ema200[-self.p.regime_slope_period])
                        bullish = (float(price) > ema_now) and (ema_now > ema_past)
                    else:
                        bullish = float(price) > ema_now
                        
            if self.p.use_atr_position_sizing and atr > 0:
                risk_amt = float(self.broker.getvalue()) * float(self.p.risk_per_trade)
                risk_per_share = float((self.p.atr_sl or 1.0) * atr)
                size = int(max(0, risk_amt / max(risk_per_share, 1e-8)))
            else:
                size = int(self.broker.getvalue() * self.p.risk_per_trade / max(price, 1e-8))
                
            if self.p.max_pos_value_frac and float(price) > 0:
                cap_shares = int(self.broker.getvalue() * float(self.p.max_pos_value_frac) / float(price))
                size = max(0, min(size, cap_shares))
                
            if intent.side == "long" and pos.size <= 0 and bullish:
                if pos.size < 0:
                    self.close(data=data)
                if size > 0:
                    self.buy(data=data, size=size)
            elif intent.side == "short" and self.p.allow_short and pos.size >= 0:
                if pos.size > 0:
                    self.close(data=data)
                if size > 0:
                    self.sell(data=data, size=size)
            elif intent.side == "flat" and pos.size != 0:
                if getattr(self, "_tp_hold", 0) >= int(self.p.min_holding_bars):
                    self.close(data=data)
                    
            if pos.size != 0 and atr > 0:
                entry = float(pos.price)
                if self.p.atr_sl and float(price) <= entry - float(self.p.atr_sl) * atr and getattr(self, "_tp_hold", 0) >= int(self.p.min_holding_bars):
                    self.close(data=data)
                if self.p.atr_tp and float(price) >= entry + float(self.p.atr_tp) * atr and getattr(self, "_tp_hold", 0) >= int(self.p.min_holding_bars):
                    self.close(data=data)
                self._tp_hold = getattr(self, "_tp_hold", 0) + 1


def _coerce_turning(params: Dict[str, Any]) -> Dict[str, Any]:
    """Force user-supplied turning-point params into safe numeric ranges."""
    params["topn"] = max(1, int(round(params.get("topn", 2))))
    params["vwap_window"] = max(1, int(round(params.get("vwap_window", 20))))
    params["gap"] = float(params.get("gap", 0.015))
    params["reversal"] = float(params.get("reversal", 0.003))
    params["vol_surge"] = float(params.get("vol_surge", 1.3))
    params["risk_per_trade"] = min(1.0, max(0.001, float(params.get("risk_per_trade", 0.1))))
    params["allow_short"] = bool(params.get("allow_short", False))
    return params


TURNING_POINT_MODULE = StrategyModule(
    name="turning_point",
    description="Multi-symbol turning point selector with gap/volume filters",
    strategy_cls=TurningPointBT,
    param_names=["topn", "gap", "reversal", "vol_surge", "vwap_window", "allow_short", "risk_per_trade"],
    defaults=dict(topn=2, gap=0.015, reversal=0.003, vol_surge=1.3, vwap_window=20, allow_short=False, risk_per_trade=0.1),
    multi_symbol=True,
    grid_defaults={
        "topn": [1, 2, 3],
        "gap": [0.01, 0.015, 0.02],
        "reversal": [0.002, 0.003, 0.004],
        "vol_surge": [1.2, 1.3, 1.5],
        "vwap_window": [10, 20, 30],
    },
    coercer=_coerce_turning,
)


# ---------------------------------------------------------------------------
# Risk Parity Strategy
# ---------------------------------------------------------------------------

class RiskParityBT(bt.Strategy):
    """
    Multi-asset risk parity: inverse-volatility weighting with periodic rebalancing.
    Includes momentum and regime filters, plus benchmark gate for risk-off scenarios.
    """
    params = dict(
        vol_window=20,
        rebalance_days=21,
        max_weight=0.4,
        use_momentum=True,
        mom_lookback=60,
        mom_threshold=0.0,
        use_regime=True,
        regime_period=200,
        allow_cash=True,
        # Benchmark gate parameters
        use_benchmark_gate=True,
        benchmark_data_name="__benchmark__",
        bench_gate_period=200,
        bench_risk_off_weight=0.0
    )
    
    def __init__(self) -> None:
        self._last_reb = -999
        self._names = [d._name or f"sym{i}" for i, d in enumerate(self.datas) 
                      if getattr(d, "_name", "") != self.p.benchmark_data_name]
        self._rets = {n: bt.indicators.PctChange(d.close) 
                     for n, d in zip(self._names, self.datas) 
                     if getattr(d, "_name", "") != self.p.benchmark_data_name}
        self._vol = {n: bt.indicators.StdDev(self._rets[n], period=self.p.vol_window) 
                    for n in self._names}
        self._ema200 = {n: bt.indicators.EMA(d.close, period=self.p.regime_period) 
                       for n, d in zip(self._names, self.datas) 
                       if getattr(d, "_name", "") != self.p.benchmark_data_name}
        self._mom = {n: (d.close - bt.indicators.SMA(d.close, period=self.p.mom_lookback)) 
                    for n, d in zip(self._names, self.datas) 
                    if getattr(d, "_name", "") != self.p.benchmark_data_name}
        # Benchmark EMA
        self._bench = next((d for d in self.datas if getattr(d, "_name", "") == self.p.benchmark_data_name), None)
        self._bench_ema = bt.indicators.EMA(self._bench.close, period=self.p.bench_gate_period) if self._bench is not None else None

    def _eligible(self, name: str, data) -> bool:
        """Check if asset passes momentum and regime filters."""
        ok = True
        if self.p.use_momentum:
            ok &= (float(self._mom[name][0]) > float(self.p.mom_threshold))
        if self.p.use_regime:
            ok &= (float(data.close[0]) > float(self._ema200[name][0]))
        return bool(ok)

    def next(self) -> None:
        bar = len(self.datas[0])
        if bar - self._last_reb < int(self.p.rebalance_days):
            return
        self._last_reb = bar

        # Benchmark gate: risk-on/risk-off switch
        gate_on = True
        if self.p.use_benchmark_gate and (self._bench is not None) and (self._bench_ema is not None):
            gate_on = float(self._bench.close[0]) >= float(self._bench_ema[0])

        vols, elig = {}, {}
        for d in self.datas:
            n = d._name
            if n == self.p.benchmark_data_name:
                continue
            v = float(self._vol[n][0])
            vols[n] = v if v == v and v > 1e-9 else float("inf")
            elig[n] = self._eligible(n, d) and gate_on

        inv = {n: (1.0/vols[n]) if (elig[n] and vols[n] < float("inf")) else 0.0 for n in self._names}
        # Scale by gate
        gate_scale = 1.0 if gate_on else float(self.p.bench_risk_off_weight)

        if sum(inv.values()) <= 0.0 or gate_scale <= 0.0:
            if self.p.allow_cash:
                for d in self.datas:
                    if d._name == self.p.benchmark_data_name:
                        continue
                    if self.getposition(d).size != 0:
                        self.close(data=d)
                return

        weights = {n: gate_scale * (inv[n] / sum(inv.values())) for n in self._names}
        for d in self.datas:
            n = d._name
            if n == self.p.benchmark_data_name:
                continue
            tgt_w = min(float(self.p.max_weight), float(weights.get(n, 0.0)))
            port_val = float(self.broker.getvalue())
            price = float(d.close[0])
            tgt_shares = int((port_val * tgt_w) / max(price, 1e-8))
            cur_pos = self.getposition(d).size
            delta = tgt_shares - cur_pos
            if delta > 0:
                self.buy(data=d, size=delta)
            elif delta < 0:
                self.sell(data=d, size=abs(delta))


def _coerce_rp(p: Dict[str, Any]) -> Dict[str, Any]:
    """Force user-supplied risk-parity params into safe numeric ranges."""
    p["vol_window"] = max(10, int(round(float(p.get("vol_window", 20)))))
    p["rebalance_days"] = max(5, int(round(float(p.get("rebalance_days", 21)))))
    p["max_weight"] = float(min(0.9, max(0.05, float(p.get("max_weight", 0.4)))))
    p["use_momentum"] = bool(p.get("use_momentum", True))
    p["mom_lookback"] = max(20, int(round(float(p.get("mom_lookback", 60)))))
    p["mom_threshold"] = float(p.get("mom_threshold", 0.0))
    p["use_regime"] = bool(p.get("use_regime", True))
    p["allow_cash"] = bool(p.get("allow_cash", True))
    return p


RISK_PARITY_MODULE = StrategyModule(
    name="risk_parity",
    description="Multi-asset risk parity (inverse-vol) portfolio, periodic rebalance",
    strategy_cls=RiskParityBT,
    param_names=["vol_window", "rebalance_days", "max_weight", "use_momentum", "mom_lookback", "mom_threshold", "use_regime", "allow_cash"],
    defaults={"vol_window": 20, "rebalance_days": 21, "max_weight": 0.4, "use_momentum": True, "mom_lookback": 60, "mom_threshold": 0.0, "use_regime": True, "allow_cash": True},
    grid_defaults={"vol_window": [20, 30], "rebalance_days": [21], "max_weight": [0.3, 0.4, 0.5]},
    coercer=_coerce_rp,
    multi_symbol=True,
)


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

def _convert_backtrader_registry_to_legacy() -> Dict[str, StrategyModule]:
    """Convert new backtrader registry to legacy StrategyModule format."""
    legacy_registry = {}
    
    for name, module in BACKTRADER_STRATEGY_REGISTRY.items():
        legacy_module = StrategyModule(
            name=module.name,
            description=module.description,
            strategy_cls=module.strategy_cls,
            param_names=module.param_names,
            defaults=module.defaults,
            multi_symbol=module.multi_symbol,
            grid_defaults=module.grid_defaults,
            coercer=module.coercer
        )
        legacy_registry[name] = legacy_module
    
    return legacy_registry


# Initialize the complete strategy registry
STRATEGY_REGISTRY: Dict[str, StrategyModule] = {}
STRATEGY_REGISTRY.update(_convert_backtrader_registry_to_legacy())
STRATEGY_REGISTRY["turning_point"] = TURNING_POINT_MODULE
STRATEGY_REGISTRY["risk_parity"] = RISK_PARITY_MODULE  # Now added!
