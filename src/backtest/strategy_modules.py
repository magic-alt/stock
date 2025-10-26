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


# ---------------------------------------------------------------------------
# ML Walk-Forward Strategy (Backtrader)
# ---------------------------------------------------------------------------
try:
    from src.strategies.ml_strategies import MLWalkForwardStrategy
    _ML_AVAILABLE = True
except Exception:
    _ML_AVAILABLE = False

if _ML_AVAILABLE:
    class MLWalkForwardBT(bt.Strategy):
        """
        Backtrader 版 ML 走步策略：
        - 每根 bar 用"到前一日"的样本扩展训练
        - 依据今日概率与阈值生成意图（多/空/空仓），下单由本框架成交模型处理
        """
        params = dict(
            label_h=1,
            min_train=200,
            prob_long=0.60,          # 调高默认入场阈值（更稳健）
            prob_short=0.60,
            prob_exit_long=0.54,     # 新增：出场阈值（滞回带）
            prob_exit_short=0.46,    # 新增：做空出场阈值
            model_type="auto",   # 'auto'|'xgb'|'rf'|'lr'|'sgd'|'mlp'
            regime_ma=200,       # 更严趋势过滤
            allow_short=False,
            use_partial_fit=False,
            risk_per_trade=0.05, # 默认更小的单笔风险
            atr_period=14,
            atr_sl=2.0,
            atr_tp=None,
            max_pos_value_frac=0.3,
            min_holding_bars=2,  # 新增更稳健默认
            cooldown_bars=3,     # 新增：冷却期，避免来回打
        )

        def __init__(self) -> None:
            # 仅单标的数据（StrategyModule.add_data 会只加第一个）
            self.data0 = self.datas[0]
            # 从 feed 提取原始 DataFrame（GenericPandasData.dataname）
            self._raw_df = getattr(self.data0, "_dataname", None)
            if not isinstance(self._raw_df, pd.DataFrame):
                raise ValueError("MLWalkForwardBT requires PandasData with underlying DataFrame")
            # 规范列名
            df = self._raw_df.copy()
            # 尝试多种列名规范化方案
            if 'close' in df.columns:
                df = df.rename(columns={
                    "open":"开盘","high":"最高","low":"最低","close":"收盘","volume":"成交量"
                })
            elif '收盘' not in df.columns and 'close' not in df.columns:
                # 如果没有这些列，尝试使用索引
                raise ValueError("DataFrame must contain OHLCV data")
            
            # 预先计算特征矩阵与标签
            self._ml = MLWalkForwardStrategy(
                label_horizon=int(self.p.label_h),
                min_train=int(self.p.min_train),
                prob_long=float(self.p.prob_long),
                prob_short=float(self.p.prob_short),
                model=str(self.p.model_type),
                use_regime_ma=int(self.p.regime_ma),
                allow_short=bool(self.p.allow_short),
                use_partial_fit=bool(self.p.use_partial_fit),
            )
            self._feat = self._ml._ta(df)
            self._label = self._ml._build_label(df["收盘"])
            self._probs = pd.Series(0.0, index=df.index)
            self._trained_upto = None  # 扩展窗口截止索引

            # 交易风控指标
            self._atr = bt.indicators.ATR(self.data0, period=int(self.p.atr_period))
            self._hold = 0
            self._since_trade = 99999   # 冷却计数器
            self._state = 0             # -1/0/1 当前意图，用于滞回

        def log(self, txt, dt=None):
            """日志输出辅助函数"""
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt}, {txt}")

        def notify_order(self, order):
            """订单状态通知"""
            if order.status in [order.Submitted, order.Accepted]:
                return

            if order.status in [order.Completed]:
                # 计算总费用（佣金+印花税）
                value = abs(order.executed.value)
                if order.isbuy():
                    # 买入：仅佣金 (0.01%)
                    total_cost = value * 0.0001
                else:
                    # 卖出：佣金 (0.01%) + 印花税 (0.05%)
                    total_cost = value * 0.0006
                
                if order.isbuy():
                    self.log(
                        f"BUY EXECUTED, Size {order.executed.size:.0f}, "
                        f"Price: {order.executed.price:.2f}, "
                        f"Cost: {order.executed.value:.2f}, Commission {total_cost:.2f}"
                    )
                else:
                    self.log(
                        f"SELL EXECUTED, Size {order.executed.size:.0f}, "
                        f"Price: {order.executed.price:.2f}, "
                        f"Value: {order.executed.value:.2f}, Commission {total_cost:.2f}"
                    )
            elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                self.log("Order Canceled/Margin/Rejected")

        def next(self) -> None:
            # 当前时间戳
            cur_dt = bt.num2date(self.data0.datetime[0])
            cur_ts = pd.Timestamp(cur_dt)
            if cur_ts not in self._feat.index:
                return

            # 走步训练：用严格早于"当前 bar"的样本，预测当前 bar 概率（执行在下一根由回测器处理）
            i = self._feat.index.get_loc(cur_ts)
            if i < max(int(self.p.min_train), self.p.label_h):
                return

            X_train = self._feat.iloc[:i, :].values
            y_train = self._label.iloc[:i].values
            X_pred = self._feat.iloc[i:i+1, :].values

            model = self._ml._make_model()
            prob = 0.0
            try:
                if isinstance(model, tuple) and model[0] == "torch_mlp":
                    net = self._ml._torch_fit(model[1], X_train, y_train)
                    prob = self._ml._torch_predict(net, X_pred) if net is not None else 0.0
                else:
                    if self.p.use_partial_fit and hasattr(model, "partial_fit"):
                        model.partial_fit(X_train, y_train, classes=np.array([0,1]))
                    else:
                        model.fit(X_train, y_train)
                    if hasattr(model, "predict_proba"):
                        prob = float(model.predict_proba(X_pred)[0, 1])
                    elif hasattr(model, "decision_function"):
                        z = float(model.decision_function(X_pred)[0])
                        prob = 1.0 / (1.0 + np.exp(-z))
                    else:
                        prob = float(model.predict(X_pred)[0])
            except Exception:
                prob = 0.0

            self._probs.iloc[i] = prob

            # --- 概率滞回：入场与出场不同阈值，减少抖动 ---
            enter_long = float(self.p.prob_long)
            exit_long  = float(self.p.prob_exit_long) if self.p.prob_exit_long is not None else max(0.5, enter_long - 0.05)
            enter_short = float(self.p.prob_short)
            exit_short  = float(self.p.prob_exit_short) if self.p.prob_exit_short is not None else max(0.5, enter_short - 0.05)

            intent = self._state
            if self._state == 0:
                if prob >= enter_long:
                    intent = 1
                elif bool(self.p.allow_short) and (prob <= (1.0 - enter_short)):
                    intent = -1
            elif self._state == 1:
                if prob <= exit_long:
                    intent = 0
            elif self._state == -1:
                if prob >= (1.0 - exit_short):
                    intent = 0

            price = float(self.data0.close[0])
            atr = float(self._atr[0]) if self._atr[0] else 0.0
            pos = self.getposition(self.data0)

            # 头寸规模：ATR 风控 / 价值上限
            if atr > 0:
                risk_amt = float(self.broker.getvalue()) * float(self.p.risk_per_trade)
                risk_per_share = float((self.p.atr_sl or 1.0) * atr)
                size = int(max(0, risk_amt / max(risk_per_share, 1e-8)))
            else:
                size = int(self.broker.getvalue() * float(self.p.risk_per_trade) / max(price, 1e-8))
            if self.p.max_pos_value_frac and price > 0:
                cap_shares = int(self.broker.getvalue() * float(self.p.max_pos_value_frac) / price)
                size = max(0, min(size, cap_shares))
            
            # 强制100股整数倍（A股规则）
            lots = max(1, size // 100)
            size = lots * 100

            # 冷却：若刚交易完，必须等待 cooldown_bars
            if self._since_trade < int(self.p.cooldown_bars):
                intent = self._state  # 忽略新意图

            # 执行（最小持有周期/止盈止损基于 ATR）
            if intent > 0 and pos.size <= 0:
                if pos.size < 0:
                    self.close(data=self.data0)
                if size > 0:
                    self.buy(data=self.data0, size=size)
                    self._hold = 0
                    self._since_trade = 0
            elif intent < 0 and pos.size >= 0 and bool(self.p.allow_short):
                if pos.size > 0:
                    self.close(data=self.data0)
                if size > 0:
                    self.sell(data=self.data0, size=size)
                    self._hold = 0
                    self._since_trade = 0
            elif intent == 0 and pos.size != 0:
                if self._hold >= int(self.p.min_holding_bars):
                    self.close(data=self.data0)
                    self._since_trade = 0

            # 出场：ATR-based
            if pos.size != 0 and atr > 0:
                entry = float(pos.price)
                if (self.p.atr_sl and price <= entry - float(self.p.atr_sl) * atr and self._hold >= int(self.p.min_holding_bars)):
                    self.close(data=self.data0)
                    self._since_trade = 0
                if (self.p.atr_tp and price >= entry + float(self.p.atr_tp) * atr and self._hold >= int(self.p.min_holding_bars)):
                    self.close(data=self.data0)
                    self._since_trade = 0
                self._hold += 1

            # 递增冷却计数器、保存状态
            self._since_trade += 1
            self._state = intent

    def _coerce_ml(p: Dict[str, Any]) -> Dict[str, Any]:
        """Force user-supplied ML walk-forward params into safe numeric ranges."""
        p["label_h"] = max(1, int(round(float(p.get("label_h", 1)))))
        p["min_train"] = max(50, int(round(float(p.get("min_train", 200)))))
        p["prob_long"] = float(p.get("prob_long", 0.60))
        p["prob_short"] = float(p.get("prob_short", 0.60))
        p["prob_exit_long"] = float(p.get("prob_exit_long", 0.54)) if p.get("prob_exit_long", None) is not None else None
        p["prob_exit_short"] = float(p.get("prob_exit_short", 0.46)) if p.get("prob_exit_short", None) is not None else None
        p["model_type"] = str(p.get("model_type", "auto")).lower()
        p["regime_ma"] = max(0, int(round(float(p.get("regime_ma", 200)))))
        p["allow_short"] = bool(p.get("allow_short", False))
        p["use_partial_fit"] = bool(p.get("use_partial_fit", False))
        p["risk_per_trade"] = min(1.0, max(0.001, float(p.get("risk_per_trade", 0.05))))
        p["atr_period"] = max(5, int(round(float(p.get("atr_period", 14)))))
        p["atr_sl"] = float(p.get("atr_sl", 2.0)) if p.get("atr_sl", None) is not None else None
        p["atr_tp"] = float(p.get("atr_tp", None)) if p.get("atr_tp", None) is not None else None
        p["max_pos_value_frac"] = float(min(0.9, max(0.05, float(p.get("max_pos_value_frac", 0.3)))))
        p["min_holding_bars"] = max(0, int(round(float(p.get("min_holding_bars", 2)))))
        p["cooldown_bars"] = max(0, int(round(float(p.get("cooldown_bars", 3)))))
        return p

    ML_WALK_MODULE = StrategyModule(
        name="ml_walk",
        description="Walk-forward ML classifier with auto features & probability thresholds",
        strategy_cls=MLWalkForwardBT,
        param_names=[
            "label_h","min_train","prob_long","prob_short","prob_exit_long","prob_exit_short","model_type",
            "regime_ma","allow_short","use_partial_fit",
            "risk_per_trade","atr_period","atr_sl","atr_tp","max_pos_value_frac","min_holding_bars","cooldown_bars"
        ],
        defaults=dict(
            label_h=1, min_train=200, prob_long=0.60, prob_short=0.60, prob_exit_long=0.54, prob_exit_short=0.46, model_type="auto",
            regime_ma=200, allow_short=False, use_partial_fit=False,
            risk_per_trade=0.05, atr_period=14, atr_sl=2.0, atr_tp=None, max_pos_value_frac=0.3, min_holding_bars=2, cooldown_bars=3
        ),
        grid_defaults={
            "label_h": [1, 3, 5],
            "min_train": [150, 200, 300],
            "model_type": ["auto", "rf", "xgb", "lr"],
            "prob_long": [0.58, 0.60, 0.65],
            "prob_short": [0.52, 0.55],
            "prob_exit_long": [0.52, 0.54, 0.56],
            "allow_short": [False, True],
            "cooldown_bars": [2, 3, 5],
            "min_holding_bars": [2, 3, 5],
        },
        coercer=_coerce_ml,
        multi_symbol=False,
    )
    STRATEGY_REGISTRY["ml_walk"] = ML_WALK_MODULE

    # -----------------------------------------------------------------------
    # 新策略 1：ml_meta —— 基础技术面候选 + ML 概率过滤（明显降频）
    # -----------------------------------------------------------------------
    class MLMetaFilterBT(bt.Strategy):
        """元标注策略：先用SMA金叉产生候选信号，再用ML概率过滤"""
        params = dict(
            fast=10, slow=60,             # 基础信号：SMA 金叉/死叉
            min_train=200, label_h=1,
            prob_filter=0.58,             # 仅当 ML 概率 >= 该阈值才允许进场
            prob_exit=0.52,               # 滞回退出
            model_type="auto", regime_ma=200,
            risk_per_trade=0.05, atr_period=14, atr_sl=2.0, atr_tp=None,
            max_pos_value_frac=0.3, min_holding_bars=2, cooldown_bars=3,
            allow_short=False
        )
        
        def __init__(self):
            self.data0 = self.datas[0]
            base_df = getattr(self.data0, "_dataname", None)
            if not isinstance(base_df, pd.DataFrame):
                raise ValueError("MLMetaFilterBT requires PandasData with underlying DataFrame")
            df = base_df.copy()
            if 'close' in df.columns:
                df = df.rename(columns={"open":"开盘","high":"最高","low":"最低","close":"收盘","volume":"成交量"})
            
            self._ml = MLWalkForwardStrategy(
                label_horizon=int(self.p.label_h),
                min_train=int(self.p.min_train),
                prob_long=float(self.p.prob_filter),
                model=str(self.p.model_type),
                use_regime_ma=int(self.p.regime_ma),
                allow_short=False
            )
            self._feat = self._ml._ta(df)
            self._label = self._ml._build_label(df["收盘"])
            self._atr = bt.indicators.ATR(self.data0, period=int(self.p.atr_period))
            self._fast = bt.indicators.SMA(self.data0.close, period=int(self.p.fast))
            self._slow = bt.indicators.SMA(self.data0.close, period=int(self.p.slow))
            self._hold = 0
            self._since_trade = 99999
            self._ml_model = None
            self._last_side = 0

        def log(self, txt, dt=None):
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt}, {txt}")

        def notify_order(self, order):
            if order.status in [order.Submitted, order.Accepted]:
                return
            if order.status in [order.Completed]:
                # 计算总费用（佣金+印花税）
                value = abs(order.executed.value)
                if order.isbuy():
                    total_cost = value * 0.0001  # 买入：仅佣金
                else:
                    total_cost = value * 0.0006  # 卖出：佣金+印花税
                
                if order.isbuy():
                    self.log(f"BUY EXECUTED, Size {order.executed.size:.0f}, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Commission {total_cost:.2f}")
                else:
                    self.log(f"SELL EXECUTED, Size {order.executed.size:.0f}, Price: {order.executed.price:.2f}, Value: {order.executed.value:.2f}, Commission {total_cost:.2f}")
            elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                self.log("Order Canceled/Margin/Rejected")

        def next(self):
            cur_dt = bt.num2date(self.data0.datetime[0])
            cur_ts = pd.Timestamp(cur_dt)
            if cur_ts not in self._feat.index:
                return
            i = self._feat.index.get_loc(cur_ts)
            if i < max(int(self.p.min_train), int(self.p.label_h)):
                return

            # 基础金叉/死叉产生"候选"
            long_candidate = float(self._fast[0]) > float(self._slow[0]) and float(self._fast[-1]) <= float(self._slow[-1])
            flat_candidate = float(self._fast[0]) < float(self._slow[0]) and float(self._fast[-1]) >= float(self._slow[-1])

            # ML 概率（扩展窗口）
            X_train, y_train = self._feat.iloc[:i, :].values, self._label.iloc[:i].values
            X_pred = self._feat.iloc[i:i+1, :].values
            if self._ml_model is None:
                self._ml_model = self._ml._make_model()
            prob = 0.0
            try:
                m = self._ml_model
                if hasattr(m, "partial_fit"):
                    m.partial_fit(X_train, y_train, classes=np.array([0,1]))
                else:
                    m.fit(X_train, y_train)
                prob = float(m.predict_proba(X_pred)[0,1]) if hasattr(m,"predict_proba") else float(m.predict(X_pred)[0])
            except Exception:
                prob = 0.0

            pos = self.getposition(self.data0)
            price = float(self.data0.close[0])
            atr = float(self._atr[0]) if self._atr[0] else 0.0
            if atr > 0:
                risk_amt = float(self.broker.getvalue()) * float(self.p.risk_per_trade)
                size = int(max(0, risk_amt / max(float(self.p.atr_sl) * atr, 1e-8)))
            else:
                size = int(self.broker.getvalue() * float(self.p.risk_per_trade) / max(price, 1e-8))
            if self.p.max_pos_value_frac and price > 0:
                cap_shares = int(self.broker.getvalue() * float(self.p.max_pos_value_frac) / price)
                size = max(0, min(size, cap_shares))
            size = max(1, size//100)*100

            # 冷却
            if self._since_trade < int(self.p.cooldown_bars):
                long_candidate = False
                flat_candidate = False

            # 仅当基础信号触发 + ML 概率通过阈值，才入场；退出用滞回
            if long_candidate and prob >= float(self.p.prob_filter) and pos.size <= 0:
                if pos.size < 0:
                    self.close(data=self.data0)
                if size > 0:
                    self.buy(data=self.data0, size=size)
                    self._since_trade = 0
                    self._hold = 0
                    self._last_side = 1
            elif flat_candidate and pos.size > 0 and (prob <= float(self.p.prob_exit) or self._hold >= int(self.p.min_holding_bars)):
                self.close(data=self.data0)
                self._since_trade = 0
                self._last_side = 0

            if pos.size != 0 and atr > 0:
                entry = float(pos.price)
                if self.p.atr_sl and price <= entry - float(self.p.atr_sl)*atr and self._hold >= int(self.p.min_holding_bars):
                    self.close(data=self.data0); self._since_trade = 0; self._last_side = 0
                if self.p.atr_tp and price >= entry + float(self.p.atr_tp)*atr and self._hold >= int(self.p.min_holding_bars):
                    self.close(data=self.data0); self._since_trade = 0; self._last_side = 0
                self._hold += 1
            self._since_trade += 1

    def _coerce_meta(p):
        p["fast"] = max(3, int(round(float(p.get("fast", 10)))))
        p["slow"] = max(p["fast"]+1, int(round(float(p.get("slow", 60)))))
        p["prob_filter"] = float(p.get("prob_filter", 0.58))
        p["prob_exit"] = float(p.get("prob_exit", 0.52))
        p["min_train"] = max(100, int(round(float(p.get("min_train", 200)))))
        p["label_h"] = max(1, int(round(float(p.get("label_h", 1)))))
        p["risk_per_trade"] = min(1.0, max(0.001, float(p.get("risk_per_trade", 0.05))))
        p["min_holding_bars"] = max(0, int(round(float(p.get("min_holding_bars", 2)))))
        p["cooldown_bars"] = max(0, int(round(float(p.get("cooldown_bars", 3)))))
        p["regime_ma"] = max(0, int(round(float(p.get("regime_ma", 200)))))
        p["allow_short"] = bool(p.get("allow_short", False))
        p["model_type"] = str(p.get("model_type", "auto")).lower()
        return p

    ML_META_MODULE = StrategyModule(
        name="ml_meta",
        description="Meta-labeling: base SMA cross candidates filtered by ML probability (low turnover).",
        strategy_cls=MLMetaFilterBT,
        param_names=["fast","slow","min_train","label_h","prob_filter","prob_exit","model_type","regime_ma",
                     "risk_per_trade","atr_period","atr_sl","atr_tp","max_pos_value_frac","min_holding_bars","cooldown_bars","allow_short"],
        defaults=dict(fast=10, slow=60, min_train=200, label_h=1, prob_filter=0.58, prob_exit=0.52, model_type="auto",
                      regime_ma=200, risk_per_trade=0.05, atr_period=14, atr_sl=2.0, atr_tp=None,
                      max_pos_value_frac=0.3, min_holding_bars=2, cooldown_bars=3, allow_short=False),
        grid_defaults={"fast":[5,10],"slow":[50,60,90],"prob_filter":[0.58,0.62],"prob_exit":[0.50,0.52,0.54]},
        coercer=_coerce_meta,
        multi_symbol=False,
    )
    STRATEGY_REGISTRY["ml_meta"] = ML_META_MODULE

    # -----------------------------------------------------------------------
    # 新策略 2：ml_prob_band —— 概率分段 + 滞回（天然低换手；可选做空）
    # -----------------------------------------------------------------------
    class MLProbBandBT(bt.Strategy):
        """概率分段策略：将ML概率映射为长/空/空仓三段，带滞回带，天然低换手"""
        params = dict(
            min_train=200, label_h=1, model_type="auto", regime_ma=200,
            hi=0.62, lo=0.38,          # 三段阈值；lo=1-hi 对称时仅做多/空
            band_gap=0.04,             # 滞回带（入/出不同）
            allow_short=False,
            risk_per_trade=0.05, atr_period=14, atr_sl=2.0, atr_tp=None,
            max_pos_value_frac=0.3, min_holding_bars=2, cooldown_bars=3
        )
        
        def __init__(self):
            self.data0 = self.datas[0]
            df = getattr(self.data0, "_dataname", None)
            if not isinstance(df, pd.DataFrame):
                raise ValueError("MLProbBandBT requires PandasData with underlying DataFrame")
            if 'close' in df.columns:
                df = df.rename(columns={"open":"开盘","high":"最高","low":"最低","close":"收盘","volume":"成交量"})
            
            self._ml = MLWalkForwardStrategy(
                label_horizon=int(self.p.label_h), min_train=int(self.p.min_train),
                model=str(self.p.model_type), use_regime_ma=int(self.p.regime_ma), allow_short=bool(self.p.allow_short)
            )
            self._feat = self._ml._ta(df)
            self._label = self._ml._build_label(df["收盘"])
            self._atr = bt.indicators.ATR(self.data0, period=int(self.p.atr_period))
            self._state = 0
            self._since_trade = 99999

        def log(self, txt, dt=None):
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt}, {txt}")

        def notify_order(self, order):
            if order.status in [order.Submitted, order.Accepted]:
                return
            if order.status in [order.Completed]:
                # 计算总费用（佣金+印花税）
                value = abs(order.executed.value)
                if order.isbuy():
                    total_cost = value * 0.0001  # 买入：仅佣金
                else:
                    total_cost = value * 0.0006  # 卖出：佣金+印花税
                
                if order.isbuy():
                    self.log(f"BUY EXECUTED, Size {order.executed.size:.0f}, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Commission {total_cost:.2f}")
                else:
                    self.log(f"SELL EXECUTED, Size {order.executed.size:.0f}, Price: {order.executed.price:.2f}, Value: {order.executed.value:.2f}, Commission {total_cost:.2f}")
            elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                self.log("Order Canceled/Margin/Rejected")

        def next(self):
            cur_dt = bt.num2date(self.data0.datetime[0]); cur_ts = pd.Timestamp(cur_dt)
            if cur_ts not in self._feat.index: return
            i = self._feat.index.get_loc(cur_ts)
            if i < max(int(self.p.min_train), int(self.p.label_h)): return
            
            X_train, y_train = self._feat.iloc[:i,:].values, self._label.iloc[:i].values
            X_pred = self._feat.iloc[i:i+1,:].values
            m = self._ml._make_model(); prob = 0.0
            try:
                if hasattr(m,"partial_fit"): m.partial_fit(X_train,y_train,classes=np.array([0,1]))
                else: m.fit(X_train,y_train)
                prob = float(m.predict_proba(X_pred)[0,1]) if hasattr(m,"predict_proba") else float(m.predict(X_pred)[0])
            except Exception: prob = 0.0

            hi, lo, gap = float(self.p.hi), float(self.p.lo), float(self.p.band_gap)
            enter_long, exit_long = hi, max(0.5, hi-gap)
            enter_short, exit_short = (1.0-lo), min(0.5, lo+gap)

            intent = self._state
            if self._state == 0:
                if prob >= enter_long: intent = 1
                elif bool(self.p.allow_short) and prob <= lo: intent = -1
            elif self._state == 1 and prob <= exit_long:
                intent = 0
            elif self._state == -1 and prob >= exit_short:
                intent = 0

            pos = self.getposition(self.data0); price = float(self.data0.close[0])
            atr = float(self._atr[0]) if self._atr[0] else 0.0
            if atr>0:
                risk_amt = float(self.broker.getvalue()) * float(self.p.risk_per_trade)
                size = int(max(0, risk_amt / max(float(self.p.atr_sl)*atr,1e-8)))
            else:
                size = int(self.broker.getvalue()*float(self.p.risk_per_trade)/max(price,1e-8))
            if self.p.max_pos_value_frac and price>0:
                cap_shares = int(self.broker.getvalue()*float(self.p.max_pos_value_frac)/price)
                size = max(0, min(size, cap_shares))
            size = max(1, size//100)*100

            # 冷却
            if self._since_trade < int(self.p.cooldown_bars):
                intent = self._state

            if intent>0 and pos.size<=0:
                if pos.size<0: self.close(data=self.data0)
                if size>0: self.buy(data=self.data0,size=size); self._since_trade=0
            elif intent<0 and pos.size>=0 and bool(self.p.allow_short):
                if pos.size>0: self.close(data=self.data0)
                if size>0: self.sell(data=self.data0,size=size); self._since_trade=0
            elif intent==0 and pos.size!=0 and self._since_trade>=int(self.p.min_holding_bars):
                self.close(data=self.data0); self._since_trade=0

            if pos.size!=0 and atr>0:
                entry=float(pos.price)
                if self.p.atr_sl and price<=entry-float(self.p.atr_sl)*atr and self._since_trade>=int(self.p.min_holding_bars):
                    self.close(data=self.data0); self._since_trade=0
                if self.p.atr_tp and price>=entry+float(self.p.atr_tp)*atr and self._since_trade>=int(self.p.min_holding_bars):
                    self.close(data=self.data0); self._since_trade=0
            self._since_trade += 1; self._state = intent

    def _coerce_band(p):
        p["min_train"] = max(100, int(round(float(p.get("min_train", 200)))))
        p["label_h"] = max(1, int(round(float(p.get("label_h", 1)))))
        p["hi"] = float(p.get("hi", 0.62))
        p["lo"] = float(p.get("lo", 0.38))
        p["band_gap"] = float(p.get("band_gap", 0.04))
        p["risk_per_trade"] = min(1.0, max(0.001, float(p.get("risk_per_trade", 0.05))))
        p["min_holding_bars"] = max(0, int(round(float(p.get("min_holding_bars", 2)))))
        p["cooldown_bars"] = max(0, int(round(float(p.get("cooldown_bars", 3)))))
        p["regime_ma"] = max(0, int(round(float(p.get("regime_ma", 200)))))
        p["allow_short"] = bool(p.get("allow_short", False))
        p["model_type"] = str(p.get("model_type", "auto")).lower()
        return p

    ML_PROB_BAND_MODULE = StrategyModule(
        name="ml_prob_band",
        description="Probability banding with hysteresis; optional short; low turnover.",
        strategy_cls=MLProbBandBT,
        param_names=["min_train","label_h","model_type","regime_ma","hi","lo","band_gap",
                     "allow_short","risk_per_trade","atr_period","atr_sl","atr_tp",
                     "max_pos_value_frac","min_holding_bars","cooldown_bars"],
        defaults=dict(min_train=200,label_h=1,model_type="auto",regime_ma=200,hi=0.62,lo=0.38,band_gap=0.04,
                      allow_short=False,risk_per_trade=0.05,atr_period=14,atr_sl=2.0,atr_tp=None,
                      max_pos_value_frac=0.3,min_holding_bars=2,cooldown_bars=3),
        grid_defaults={"hi":[0.60,0.62,0.65],"band_gap":[0.03,0.04,0.05],"min_holding_bars":[2,3,5],"cooldown_bars":[2,3,5]},
        coercer=_coerce_band,
        multi_symbol=False,
    )
    STRATEGY_REGISTRY["ml_prob_band"] = ML_PROB_BAND_MODULE
