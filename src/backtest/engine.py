"""
Backtest Engine Module

Core engine for running backtests with multiple strategies and data sources.
Handles data loading, strategy execution, metrics calculation, and result output.
"""
from __future__ import annotations

import itertools
import json
import math
import os
import pickle
import time
import warnings
import concurrent.futures
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc

from src.data_sources.providers import get_provider, DataProviderError, CACHE_DEFAULT
from src.strategies.backtrader_registry import BACKTRADER_STRATEGY_REGISTRY

# Import strategy modules (will be defined in separate files)
from .strategy_modules import (
    StrategyModule, 
    TURNING_POINT_MODULE, 
    RISK_PARITY_MODULE, 
    STRATEGY_REGISTRY,
    IntentLogger, 
    GenericPandasData
)

# Import event-driven architecture components (V2.6.0)
from src.core.events import EventEngine, Event, EventType
from src.core.gateway import BacktestGateway, HistoryGateway


# --- globals for process workers (avoid re-sending big data blobs) --------
_G_DATA_MAP: Optional[Dict[str, pd.DataFrame]] = None
_G_BENCH_NAV: Optional[pd.Series] = None


def _grid_worker_init(data_path: str, bench_path: Optional[str]) -> None:
    """Process initializer to load shared data into globals once per worker."""
    import pickle as _pkl
    global _G_DATA_MAP, _G_BENCH_NAV
    with open(data_path, "rb") as f:
        _G_DATA_MAP = _pkl.load(f)
    if bench_path and os.path.exists(bench_path):
        with open(bench_path, "rb") as f:
            _G_BENCH_NAV = _pkl.load(f)
    else:
        _G_BENCH_NAV = None


class BacktestEngine:
    """Facade responsible for orchestrating data loading and optimisation."""

    def __init__(
        self,
        *,
        source: str = "akshare",
        benchmark_source: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
        # V2.6.0: Optional dependency injection for event-driven architecture
        event_engine: Optional[EventEngine] = None,
        history_gateway: Optional[HistoryGateway] = None,
    ) -> None:
        """
        Initialize backtest engine.
        
        Args:
            source: Data provider name (for backward compatibility)
            benchmark_source: Benchmark data provider (defaults to source)
            cache_dir: Cache directory for downloaded data
            event_engine: Optional EventEngine for event-driven features (V2.6.0+)
            history_gateway: Optional HistoryGateway implementation (V2.6.0+)
            
        Note:
            For backward compatibility, if event_engine or history_gateway are not
            provided, the engine will create default instances internally.
        """
        self.source = source
        self.benchmark_source = benchmark_source or source
        self.cache_dir = cache_dir
        
        # V2.6.0: Initialize event-driven components (with backward compatibility)
        self.events = event_engine or EventEngine()
        self.gw = history_gateway or BacktestGateway(source, cache_dir)
        
        # Track if we created the event engine (for cleanup)
        self._owns_events = event_engine is None

    def _load_data(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data using the configured gateway (V2.6.0: event-aware)."""
        # V2.6.0: Use gateway protocol instead of direct provider access
        data = self.gw.load_bars(symbols, start, end, adj=adj)
        
        # V2.6.0: Publish data loaded event
        self.events.put(Event(EventType.DATA_LOADED, {
            "symbols": list(data.keys()),
            "start": start,
            "end": end,
            "count": sum(len(df) for df in data.values())
        }))
        
        return data

    def _load_benchmark(self, index_code: str, start: str, end: str) -> pd.Series:
        """Fetch the benchmark NAV series from the gateway (V2.6.0: simplified)."""
        try:
            # V2.6.0: Use gateway's load_index_nav which handles fallback internally
            nav = self.gw.load_index_nav(index_code, start, end)
            
            # V2.6.0: Publish benchmark loaded event
            self.events.put(Event("benchmark.loaded", {
                "index": index_code,
                "points": len(nav),
                "start_value": float(nav.iloc[0]) if len(nav) > 0 else 1.0,
                "end_value": float(nav.iloc[-1]) if len(nav) > 0 else 1.0
            }))
            
            return nav
        except Exception as e:
            # Fallback to flat NAV if gateway fails
            warnings.warn(f"Benchmark loading failed: {e}. Using flat NAV.")
            date_index = pd.bdate_range(start=start, end=end)
            if date_index.empty:
                date_index = pd.Index([pd.to_datetime(start)])
            return pd.Series(1.0, index=date_index, name=index_code)

    @staticmethod
    def _run_module(
        module: StrategyModule,
        data_map: Dict[str, pd.DataFrame],
        params: Dict[str, Any],
        *,
        cash: float,
        commission: float,
        slippage: float,
        benchmark_nav: Optional[pd.Series],
        return_cerebro: bool = False,
    ) -> Tuple[pd.Series, Dict[str, Any], Optional[bt.Cerebro]]:
        """Internal helper that executes a single backtest run.
        
        Args:
            return_cerebro: If True, return the cerebro instance for plotting
            
        Returns:
            (nav, metrics, cerebro) if return_cerebro=True, else (nav, metrics, None)
        """
        cerebro = bt.Cerebro(stdstats=False)
        cerebro.broker.setcash(cash)
        
        # 设置中国A股交易成本：佣金 + 印花税
        # 佣金：万分之一，买卖双向收取
        # 免五：按实际佣金率收取，无最低限制（默认启用）
        # 不免五：佣金不足5元时按5元收取
        # 印花税：万分之五，仅卖出时收取
        # 最小交易单位：1手 = 100股
        class CNStockCommission(bt.CommInfoBase):
            """中国A股佣金和印花税计算"""
            params = (
                ('commission', 0.0001),      # 佣金率：万分之一
                ('stocklike', True),         # 股票模式
                ('commtype', bt.CommInfoBase.COMM_PERC),  # 百分比佣金
                ('percabs', False),          # 相对百分比
                ('stamp_duty', 0.0005),      # 印花税：万分之五（仅卖出）
                ('min_commission', 0.0),     # 最低佣金：0元（免五）
                ('mult', 1.0),               # 乘数
                ('margin', None),            # 保证金
            )
            
            def getsize(self, price, cash):
                """计算可购买的股票数量（必须是100的整数倍）"""
                # 预估总成本（包括佣金和可能的印花税）
                # 保守估计：假设佣金 + 印花税 = 0.0006 (万分之6)
                effective_price = price * (1 + 0.0006)
                
                # 计算最多能买多少股
                max_shares = int(cash / effective_price)
                
                # 向下取整到100的倍数（1手 = 100股）
                lots = max_shares // 100
                return lots * 100
            
            def getvaluesize(self, size, price):
                """返回持仓价值，size必须是100的倍数"""
                # 确保size是100的倍数
                return abs(size) * price
            
            def getoperationcost(self, size, price):
                """返回开仓/平仓的总成本"""
                return self.getcommission(size, price)
            
            def _getcommission(self, size, price, pseudoexec):
                """计算佣金（买卖双向）
                
                免五模式：按实际佣金率收取
                不免五模式：需将 min_commission 参数设为 5.0
                """
                value = abs(size) * price
                comm = value * self.p.commission
                
                # 如果设置了最低佣金（不免五）
                if self.p.min_commission > 0 and comm < self.p.min_commission:
                    comm = self.p.min_commission
                    
                return comm
            
            def getcommission(self, size, price):
                """获取总交易成本（佣金 + 印花税）"""
                # 佣金（买卖都收）
                comm = self._getcommission(size, price, False)
                
                # 印花税（仅卖出收取）
                stamp = 0.0
                if size < 0:  # 卖出时 size 为负
                    stamp = abs(size) * price * self.p.stamp_duty
                
                return comm + stamp
        
        cerebro.broker.addcommissioninfo(CNStockCommission())
        
        # 添加股票整手Sizer：确保所有交易都是100股的整数倍
        class StockLotSizer(bt.Sizer):
            """
            中国A股交易规则：最小1手（100股），只能是100股的整数倍
            """
            params = (
                ('lot_size', 100),  # 1手 = 100股
            )
            
            def _getsizing(self, comminfo, cash, data, isbuy):
                """计算下单数量，确保是100的整数倍"""
                position = self.broker.getposition(data)
                
                if isbuy:
                    # 买入：使用可用资金计算能买多少手
                    price = data.close[0]
                    if price <= 0:
                        return 0
                    
                    # 考虑佣金和印花税后的有效价格
                    effective_price = price * 1.0006
                    max_shares = int(cash / effective_price)
                    lots = max_shares // self.p.lot_size
                    return lots * self.p.lot_size
                else:
                    # 卖出：返回当前持仓数量（已经是100的倍数）
                    # Backtrader的sell()默认会卖出全部持仓
                    return abs(position.size)
        
        # 设置Sizer：强制所有交易都是100股整数倍
        cerebro.addsizer(StockLotSizer)
        
        if slippage:
            cerebro.broker.set_slippage_perc(slippage)
        module.add_data(cerebro, data_map)
        
        # Add benchmark data if available
        if benchmark_nav is not None and not benchmark_nav.empty:
            bench_df = pd.DataFrame(
                {
                    "open": benchmark_nav.values,
                    "high": benchmark_nav.values,
                    "low": benchmark_nav.values,
                    "close": benchmark_nav.values,
                    "volume": 0.0,
                },
                index=pd.to_datetime(benchmark_nav.index),
            )
            bench_df.index.name = "datetime"
            bench_feed = GenericPandasData(dataname=bench_df)
            cerebro.adddata(bench_feed, name="__benchmark__")
            
        module.add_strategy(cerebro, params)
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timeret")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        
        if module is TURNING_POINT_MODULE:
            cerebro.addanalyzer(IntentLogger, _name="intent_log")
            
        # Run backtest
        results = cerebro.run(runonce=True, preload=True)
        strat = results[0]
        
        # Calculate metrics
        timeret = pd.Series(strat.analyzers.timeret.get_analysis())
        nav = (1 + timeret.fillna(0)).cumprod()
        nav.index = pd.to_datetime(nav.index)
        nav.name = "strategy"
        
        metrics: Dict[str, Any] = {
            "cum_return": float(nav.iloc[-1] - 1) if len(nav) else float("nan"),
            "final_value": float(cerebro.broker.getvalue()),
        }
        
        # Sharpe ratio
        try:
            sharpe_val = strat.analyzers.sharpe.get_analysis().get("sharperatio")
        except Exception:
            sharpe_val = None
            
        ann_factor = 252.0
        avg = float(timeret.mean()) if len(timeret) else float("nan")
        std = float(timeret.std(ddof=1)) if len(timeret) > 1 else float("nan")
        sharpe_calc = (avg / std * math.sqrt(ann_factor)) if (std and std == std and std > 0) else float("nan")
        metrics["sharpe"] = float(sharpe_val) if sharpe_val is not None else sharpe_calc
        
        # Annualized metrics
        metrics["ann_return"] = float((1 + timeret).prod() ** (ann_factor / max(len(timeret), 1)) - 1) if len(timeret) else float("nan")
        metrics["ann_vol"] = float(std * math.sqrt(ann_factor)) if std == std else float("nan")
        metrics["mdd"] = float(-((nav / nav.cummax()) - 1).min()) if len(nav) else float("nan")
        
        # Trade statistics
        try:
            ta = strat.analyzers.trades.get_analysis()
            def _dig(d, *keys, default=float("nan")):
                cur = d
                for k in keys:
                    if not isinstance(cur, dict) or k not in cur:
                        return default
                    cur = cur[k]
                return cur
                
            total_closed = float(_dig(ta, "total", "closed", default=0.0))
            won_total = float(_dig(ta, "won", "total", default=0.0))
            lost_total = float(_dig(ta, "lost", "total", default=0.0))
            gross_won = float(_dig(ta, "pnl", "gross", "won", default=0.0))
            gross_lost = float(_dig(ta, "pnl", "gross", "lost", default=0.0))
            avg_win = float(_dig(ta, "won", "pnl", "average", default=float("nan")))
            avg_loss = float(_dig(ta, "lost", "pnl", "average", default=float("nan")))
            avg_len_tot = float(_dig(ta, "len", "avg", "total", default=float("nan")))
            
            win_rate = (won_total / total_closed) if total_closed > 0 else float("nan")
            profit_factor = (gross_won / abs(gross_lost)) if gross_lost != 0 else (float("inf") if gross_won > 0 else float("nan"))
            payoff_ratio = (avg_win / abs(avg_loss)) if (avg_win == avg_win and avg_loss and avg_loss < 0) else float("nan")
            expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss) if (win_rate == win_rate and avg_win == avg_win and avg_loss == avg_loss) else float("nan")
            exposure_ratio = float((np.abs(timeret.values) > 0).sum() / max(1, len(timeret))) if len(timeret) else float("nan")
            trade_freq = float(total_closed / max(1, len(timeret))) if len(timeret) else float("nan")
            
            metrics.update({
                "trades": int(total_closed),
                "win_rate": float(win_rate) if win_rate == win_rate else float("nan"),
                "profit_factor": float(profit_factor),
                "avg_hold_bars": float(avg_len_tot),
                "avg_win": float(avg_win) if avg_win == avg_win else float("nan"),
                "avg_loss": float(avg_loss) if avg_loss == avg_loss else float("nan"),
                "payoff_ratio": float(payoff_ratio),
                "expectancy": float(expectancy),
                "exposure_ratio": float(exposure_ratio),
                "trade_freq": float(trade_freq),
            })
        except Exception:
            metrics.update({
                "trades": int(0),
                "win_rate": float("nan"),
                "profit_factor": float("nan"),
                "avg_hold_bars": float("nan"),
                "avg_win": float("nan"),
                "avg_loss": float("nan"),
                "payoff_ratio": float("nan"),
                "expectancy": float("nan"),
                "exposure_ratio": float("nan"),
                "trade_freq": float("nan"),
            })
            
        # Calmar ratio
        metrics["calmar"] = float(metrics["ann_return"] / metrics["mdd"]) if (metrics.get("mdd") and metrics["mdd"] > 0) else float("nan")
        
        # Benchmark comparison
        if benchmark_nav is not None:
            # Ensure both series have timezone-naive indices
            nav_clean = nav.copy()
            bench_clean = benchmark_nav.copy()
            if hasattr(nav_clean.index, 'tz') and nav_clean.index.tz is not None:
                nav_clean.index = nav_clean.index.tz_localize(None)
            if hasattr(bench_clean.index, 'tz') and bench_clean.index.tz is not None:
                bench_clean.index = bench_clean.index.tz_localize(None)
            
            combined = pd.concat(
                [nav_clean.to_frame("strategy"), bench_clean.to_frame("benchmark")],
                axis=1,
            ).dropna()
            if not combined.empty:
                metrics["bench_return"] = float(combined["benchmark"].iloc[-1] - 1)
                metrics["bench_mdd"] = float(-((combined["benchmark"] / combined["benchmark"].cummax()) - 1).min())
                metrics["excess_return"] = float(combined["strategy"].iloc[-1] - combined["benchmark"].iloc[-1])
            else:
                metrics["bench_return"] = float("nan")
                metrics["bench_mdd"] = float("nan")
                metrics["excess_return"] = float("nan")
        
        return nav, metrics, (cerebro if return_cerebro else None)

    def _execute_strategy(
        self,
        module: StrategyModule,
        data_map: Dict[str, pd.DataFrame],
        params: Dict[str, Any],
        *,
        cash: float,
        commission: float,
        slippage: float,
        benchmark_nav: Optional[pd.Series],
        out_dir: Optional[str] = None,
        label: Optional[str] = None,
        enable_plot: bool = False,
    ) -> Tuple[pd.Series, Dict[str, Any], Optional[bt.Cerebro]]:
        """Run a backtest for the supplied strategy module and capture metrics."""
        nav, metrics, cerebro = self._run_module(
            module,
            data_map,
            params,
            cash=cash,
            commission=commission,
            slippage=slippage,
            benchmark_nav=benchmark_nav,
            return_cerebro=enable_plot,
        )
        
        if benchmark_nav is not None and out_dir:
            os.makedirs(out_dir, exist_ok=True)
            combined = pd.concat(
                [nav.to_frame("strategy"), benchmark_nav.to_frame("benchmark")],
                axis=1,
            ).dropna()
            combined_path = os.path.join(out_dir, f"{label or module.name}_nav_vs_benchmark.csv")
            combined.to_csv(combined_path)
            
            if not combined.empty:
                import matplotlib.pyplot as plt
                plt.figure()
                combined.plot()
                plt.title(f"{module.name} vs benchmark")
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f"{label or module.name}_nav_vs_benchmark.png"))
                plt.close()
        elif out_dir:
            os.makedirs(out_dir, exist_ok=True)
            nav.to_frame("strategy").to_csv(os.path.join(out_dir, f"{label or module.name}_nav.csv"))
            
        return nav, metrics, cerebro

    def run_strategy(
        self,
        strategy: str,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        cash: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.001,
        benchmark: Optional[str] = None,
        adj: Optional[str] = None,
        out_dir: Optional[str] = None,
        enable_plot: bool = False,
    ) -> Dict[str, Any]:
        """Convenience wrapper returning both metrics and NAV for a single run."""
        from .strategy_modules import STRATEGY_REGISTRY
        
        if strategy not in STRATEGY_REGISTRY:
            raise KeyError(f"Unknown strategy: {strategy}")
            
        module = STRATEGY_REGISTRY[strategy]
        if not symbols:
            raise ValueError("At least one symbol is required")
            
        data_map = self._load_data(symbols, start, end, adj=adj)
        bench_nav = self._load_benchmark(benchmark, start, end) if benchmark else None
        param_dict = module.coerce(params or {})
        
        nav, metrics, cerebro = self._execute_strategy(
            module,
            data_map,
            param_dict,
            cash=cash,
            commission=commission,
            slippage=slippage,
            benchmark_nav=bench_nav,
            out_dir=out_dir,
            label="run",
            enable_plot=enable_plot,
        )
        
        metrics.update({"strategy": strategy, **param_dict})
        metrics["nav"] = nav
        if cerebro:
            metrics["_cerebro"] = cerebro
            
        return metrics

    def grid_search(
        self,
        strategy: str,
        grid: Dict[str, Sequence[Any]],
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        cash: float = 200000,
        commission: float = 0.0001,
        slippage: float = 0.001,
        benchmark: Optional[str] = None,
        adj: Optional[str] = None,
        data_map: Optional[Dict[str, pd.DataFrame]] = None,
        bench_nav: Optional[pd.Series] = None,
        max_workers: int = 1,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Evaluate the Cartesian product of parameters and return the score grid."""
        from .strategy_modules import STRATEGY_REGISTRY
        
        if strategy not in STRATEGY_REGISTRY:
            raise KeyError(f"Unknown strategy: {strategy}")
        module = STRATEGY_REGISTRY[strategy]
        local_data_map = data_map if data_map is not None else self._load_data(symbols, start, end, adj=adj)
        local_bench_nav = bench_nav if bench_nav is not None else (self._load_benchmark(benchmark, start, end) if benchmark else None)
        keys = list(grid.keys())
        combos = list(itertools.product(*grid.values()))
        rows: List[Dict[str, Any]] = []
        broker_conf = dict(cash=cash, commission=commission, slippage=slippage)
        max_workers = max(1, max_workers)

        if max_workers > 1 and len(combos) > 1:
            # Serialize large objects once and load them in worker processes
            os.makedirs(self.cache_dir, exist_ok=True)
            data_path = os.path.join(self.cache_dir, f"_grid_data_{int(time.time()*1000)}.pkl")
            bench_path = os.path.join(self.cache_dir, f"_grid_bench_{int(time.time()*1000)}.pkl") if local_bench_nav is not None else None
            with open(data_path, "wb") as f:
                pickle.dump(local_data_map, f, protocol=pickle.HIGHEST_PROTOCOL)
            if bench_path:
                with open(bench_path, "wb") as f:
                    pickle.dump(local_bench_nav, f, protocol=pickle.HIGHEST_PROTOCOL)
            tasks = []
            param_dicts = []
            for combo in combos:
                raw_params = dict(zip(keys, combo))
                param_dict = module.coerce(raw_params)
                if extra_params:
                    param_dict.update(extra_params)
                param_dicts.append(param_dict)
                tasks.append((module.name, param_dict, broker_conf))
            metrics_list: List[Dict[str, Any]] = []
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers,
                initializer=_grid_worker_init,
                initargs=(data_path, bench_path),
            ) as pool:
                for metrics in pool.map(_grid_worker_task, tasks):
                    metrics_list.append(metrics)
            # Cleanup
            try:
                os.remove(data_path)
                if bench_path:
                    os.remove(bench_path)
            except Exception:
                pass
            for param_dict, metrics in zip(param_dicts, metrics_list):
                rows.append({"strategy": strategy, **param_dict, **metrics})
        else:
            for combo in combos:
                raw_params = dict(zip(keys, combo))
                param_dict = module.coerce(raw_params)
                if extra_params:
                    param_dict.update(extra_params)
                try:
                    _, metrics, _ = self._run_module(
                        module,
                        local_data_map,
                        param_dict,
                        cash=cash,
                        commission=commission,
                        slippage=slippage,
                        benchmark_nav=local_bench_nav,
                    )
                except Exception as err:
                    metrics = {
                        "cum_return": float("nan"),
                        "final_value": float("nan"),
                        "sharpe": float("nan"),
                        "mdd": float("nan"),
                        "bench_return": float("nan"),
                        "bench_mdd": float("nan"),
                        "excess_return": float("nan"),
                        "error": str(err),
                    }
                rows.append({"strategy": strategy, **param_dict, **metrics})
        return pd.DataFrame(rows)

    def auto_pipeline(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        strategies: Optional[List[str]] = None,
        benchmark: str = "000300.SH",
        top_n: int = 5,
        min_trades: int = 1,
        cash: float = 200000,
        commission: float = 0.0001,
        slippage: float = 0.001,
        adj: Optional[str] = None,
        out_dir: str = "./reports_auto",
        workers: int = 1,
        hot_only: bool = False,
        use_benchmark_regime: bool = False,
        regime_scope: str = "trend",
    ) -> None:
        """Run optimization for each strategy, combine results, and replay top picks."""
        from .strategy_modules import STRATEGY_REGISTRY
        from .analysis import pareto_front, save_heatmap
        
        strategies = strategies or ["ema","macd","bollinger","rsi","turning_point","keltner","zscore","donchian","triple_ma","adx_trend"]
        os.makedirs(out_dir, exist_ok=True)
        start_ts = time.perf_counter()
        data_map = self._load_data(symbols, start, end, adj=adj)
        print(f"📊 Loaded data for {len(data_map)} symbols: {list(data_map.keys())}")
        if not data_map:
            print("❌ Error: No data loaded. Cannot proceed with auto pipeline.")
            return
        bench_nav = self._load_benchmark(benchmark, start, end)
        all_rows: List[pd.DataFrame] = []
        
        for name in strategies:
            module = STRATEGY_REGISTRY.get(name)
            if not module:
                print(f"⚠️  Unknown strategy in auto pipeline: {name}, skipping")
                continue
            
            # Use hot grid or default
            grid = self._hot_grid(module) if hot_only else module.grid_defaults
            
            # Inject regime filter parameters if enabled
            extras: Optional[Dict[str, Any]] = None
            if use_benchmark_regime and name == "turning_point":
                if regime_scope == "all":
                    extras = {"bull_filter": True, "bull_filter_benchmark": True}
                elif regime_scope != "none":
                    extras = {"bull_filter": True, "bull_filter_benchmark": True}
            
            df = self.grid_search(
                name,
                grid,
                symbols,
                start,
                end,
                cash=cash,
                commission=commission,
                slippage=slippage,
                benchmark=benchmark,
                adj=adj,
                data_map=data_map,
                bench_nav=bench_nav,
                max_workers=workers,
                extra_params=extras,
            )
            csv_path = os.path.join(out_dir, f"opt_{name}.csv")
            df.to_csv(csv_path, index=False)
            save_heatmap(module, df, out_dir)
            all_rows.append(df)
        
        big = pd.concat(all_rows, ignore_index=True)
        big.to_csv(os.path.join(out_dir, "opt_all.csv"), index=False)
        pareto = pareto_front(big)
        pareto.to_csv(os.path.join(out_dir, "pareto_front.csv"), index=False)
        
        self._rerun_top_n(
            pareto,
            symbols,
            start,
            end,
            bench_nav,
            data_map,
            top_n,
            min_trades,
            cash,
            commission,
            slippage,
            out_dir,
            workers=workers,
        )

        elapsed = time.perf_counter() - start_ts
        ordered = big.sort_values(["sharpe", "cum_return", "mdd"], ascending=[False, False, True]).reset_index(drop=True)
        
        # Statistics
        if "trades" in ordered.columns:
            zero_trade_ratio = float((ordered["trades"].fillna(0) <= 0).mean())
            print(f"Zero-trade ratio in grid: {zero_trade_ratio:.1%}")
        top_overall = ordered.head(min(top_n, len(ordered)))

        # Print summary
        print(f"\nSymbols: {', '.join(symbols)} | Benchmark: {benchmark}")
        print(f"Date range: {start} -> {end} | Strategies evaluated: {len(strategies)}")
        print(f"Parameter evaluations: {len(ordered)} | Elapsed: {elapsed:.1f}s")
        print(f"Workers used: {workers}")
        if hot_only:
            print("Grid mode: HOT-ONLY (narrow ranges around empirically good zones)")
        if use_benchmark_regime:
            print(f"Regime filter: BENCHMARK EMA200 (scope={regime_scope})")
        
        self._print_metrics_legend()
        self._print_top_configs(top_overall)
        self._print_best_per_strategy(ordered)
        print(f"Reports written to {out_dir}\n")

    @staticmethod
    def _hot_grid(module) -> Dict[str, Sequence[Any]]:
        """Return a narrowed parameter grid for known strategies (hot zones)."""
        if module.name == "bollinger":
            return {"period": [10, 12, 14, 16], "devfactor": [2.2, 2.5],
                    "entry_mode": ["pierce", "close_below"], "exit_mode": ["mid"]}
        if module.name == "macd":
            # Fixed: ensure fast < slow to avoid invalid parameter combinations
            return {"fast": [10, 11, 12], "slow": [14, 15, 16, 17], "signal": [9]}
        if module.name == "rsi":
            # Optimized: relaxed thresholds to increase trade frequency
            return {"period": [14, 18, 20, 22], "upper": [65, 70, 75], "lower": [25, 30, 35]}
        if module.name == "keltner":
            return {"ema_period": [12, 16, 20], "atr_period": [14], "kc_mult": [1.8, 2.0, 2.2],
                    "entry_mode": ["pierce", "close_below"], "exit_mode": ["mid"]}
        if module.name == "zscore":
            return {"period": [14, 18, 22], "z_entry": [-1.8, -2.0, -2.2], "z_exit": [-0.7, -0.4]}
        if module.name == "donchian":
            return {"upper": [18,20,22], "lower": [8,10,12]}
        if module.name == "triple_ma":
            return {"fast":[5,8], "mid":[18,20,22], "slow":[55,60,65]}
        if module.name == "adx_trend":
            return {"adx_period":[12,14,16], "adx_th":[20,25,30]}
        if module.name == "risk_parity":
            return {"vol_window":[20,30], "rebalance_days":[21], "max_weight":[0.3,0.4,0.5]}
        return dict(module.grid_defaults)

    @staticmethod
    def _print_metrics_legend():
        """Print metrics interpretation guide."""
        print("\nMetrics legend (rule of thumb):")
        print("  - Sharpe: <0 差; 0~0.5 弱; 0.5~1 尚可; 1~1.5 良好; >1.5 很好")
        print("  - MDD: <0.10 低; 0.10~0.20 中; >0.20 高  （数值为比例，如 0.23=23%）")
        print("  - ProfitFactor: <1 亏损; 1~1.3 边缘; >1.5 稳健; >2 强")
        print("  - WinRate 需结合盈亏比一起看，单看胜率没有意义")
        print("  - PayoffRatio(平均盈亏比): >1 佳; >1.5 很好")
        print("  - Expectancy(单笔期望): >0 代表长期正期望")
        print("  - Calmar: 年化收益/MDD，>0.5 尚可; >1 佳")
        print("  - ExposureRatio: 持仓/暴露时间比例（0~1），越高越主动")
        print("  - TradeFreq: 交易频率 = trades/样本天数（越高越频繁）")

    @staticmethod
    def _print_top_configs(top_overall: pd.DataFrame):
        """Print top configurations."""
        if top_overall.empty:
            return
        print("\nTop configurations (ordered by Sharpe, return, drawdown):")
        for idx, row in top_overall.iterrows():
            info = [f"strategy={row['strategy']}"]
            for key in ["topn", "gap", "reversal", "vol_surge", "vwap_window", "period", "fast", "slow", "signal", "devfactor", "upper", "lower"]:
                if key in row and pd.notna(row[key]):
                    val = row[key]
                    if isinstance(val, bool):
                        info.append(f"{key}={val}")
                    elif isinstance(val, (int, float)):
                        info.append(f"{key}={float(val):.3f}")
                    else:
                        info.append(f"{key}={val}")
            sharpe_val = row["sharpe"]
            sharpe_str = f"{sharpe_val:.3f}" if pd.notna(sharpe_val) else "nan"
            extras = []
            for k in ["ann_return","ann_vol","win_rate","profit_factor","trades","payoff_ratio","expectancy","calmar","exposure_ratio","trade_freq"]:
                if k in row and pd.notna(row[k]):
                    try:
                        extras.append(f"{k}={float(row[k]):.3f}")
                    except Exception:
                        extras.append(f"{k}={row[k]}")
            metrics = f"sharpe={sharpe_str}, cum_return={row['cum_return']:.3f}, mdd={row['mdd']:.3f}" + (", " + ", ".join(extras) if extras else "")
            print(f"  - {'; '.join(info)} | {metrics}")

    @staticmethod
    def _print_best_per_strategy(ordered: pd.DataFrame):
        """Print best configuration per strategy."""
        best_by_strategy = ordered.groupby('strategy', sort=False).head(1)
        if best_by_strategy.empty:
            return
        print("\nBest per strategy:")
        for _, row in best_by_strategy.iterrows():
            sharpe_val = row['sharpe']
            sharpe_str = f"{sharpe_val:.3f}" if pd.notna(sharpe_val) else "nan"
            msg = f"  * {row['strategy']}: sharpe={sharpe_str}, cum_return={row['cum_return']:.3f}, mdd={row['mdd']:.3f}"
            for k in ["win_rate","profit_factor","trades","payoff_ratio","expectancy","calmar"]:
                if k in row and pd.notna(row[k]):
                    try:
                        msg += f", {k}={float(row[k]):.3f}"
                    except Exception:
                        msg += f", {k}={row[k]}"
            error_msg = row.get("error")
            if isinstance(error_msg, str) and error_msg:
                short_err = error_msg if len(error_msg) <= 80 else error_msg[:77] + "..."
                msg += f", error={short_err}"
            print(msg)

    def _rerun_top_n(
        self,
        pareto_df: pd.DataFrame,
        symbols: Sequence[str],
        start: str,
        end: str,
        bench_nav: pd.Series,
        data_map: Dict[str, pd.DataFrame],
        top_n: int,
        min_trades: int,
        cash: float,
        commission: float,
        slippage: float,
        out_dir: str,
        workers: int,
    ) -> None:
        """Replay the best candidates from the Pareto frontier to produce NAV curves."""
        from .strategy_modules import STRATEGY_REGISTRY
        import matplotlib.pyplot as plt
        
        if pareto_df.empty:
            return
        
        # Diagnostic: check if data_map is empty
        if not data_map:
            print(f"⚠️ Warning: data_map is empty in _rerun_top_n, cannot replay top configurations")
            return
        
        df = pareto_df.copy()
        # Filter out zero-trade/zero-exposure solutions
        if "trades" in df.columns:
            df1 = df[(df["trades"].fillna(0) >= float(min_trades)) & (df.get("exposure_ratio", 0).astype(float) > 0)]
        else:
            df1 = df
        
        # Relax filter if too few results
        if len(df1) < top_n and "trades" in df.columns:
            df2 = df[(df["trades"].fillna(0) > 0)]
            df1 = pd.concat([df1, df2]).drop_duplicates().head(max(top_n, len(df1)))
        
        filtered_out = len(df) - len(df1)
        if filtered_out > 0:
            print(f"Filtered {filtered_out} zero-trade/zero-exposure configs before Top-N replay.")
        
        head = df1.sort_values(["sharpe", "cum_return"], ascending=[False, False]).head(top_n)
        tasks = []
        for idx, row in head.iterrows():
            name = str(row["strategy"])
            module = STRATEGY_REGISTRY.get(name)
            if not module:
                continue
            params = {key: row[key] for key in module.param_names if key in row and not pd.isna(row[key])}
            params = module.coerce(params)
            tasks.append((f"{name}_{idx}", module, params))
        
        if not tasks:
            return

        def _run_single(label: str, module, params: Dict[str, Any]) -> Tuple[str, pd.Series]:
            local_map = {sym: df.copy(deep=False) for sym, df in data_map.items()}
            if not local_map:
                print(f"⚠️ Warning: Empty data_map for {label}, returning flat NAV")
                # Return a flat NAV series to avoid crash
                flat_nav = pd.Series(1.0, index=pd.date_range(start, end, freq='B'), name=label)
                return label, flat_nav
            nav, _, _ = self._run_module(
                module,
                local_map,
                params,
                cash=cash,
                commission=commission,
                slippage=slippage,
                benchmark_nav=bench_nav,
            )
            return label, nav

        nav_dict: Dict[str, pd.Series] = {}
        if workers > 1 and len(tasks) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_run_single, label, module, params): label for label, module, params in tasks}
                for future in concurrent.futures.as_completed(future_map):
                    label, nav = future.result()
                    nav_dict[label] = nav
        else:
            for label, module, params in tasks:
                label, nav = _run_single(label, module, params)
                nav_dict[label] = nav

        if nav_dict:
            combined = pd.concat([series.rename(label) for label, series in nav_dict.items()], axis=1).dropna()
            combined.to_csv(os.path.join(out_dir, "topN_navs.csv"))
            
            plt.figure()
            combined.plot()
            plt.title("Top-N strategies NAV")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "topN_navs.png"))
            plt.close()


# ---------------------------------------------------------------------------
# Grid search worker functions
# ---------------------------------------------------------------------------

def _grid_worker_task(args: Tuple[str, Dict[str, Any], Dict[str, Any]]) -> Dict[str, Any]:
    """Worker function for parallel grid search."""
    from .strategy_modules import STRATEGY_REGISTRY
    
    strategy_name, params, broker_conf = args
    module = STRATEGY_REGISTRY[strategy_name]
    
    try:
        engine = BacktestEngine()
        _, metrics, _ = engine._run_module(
            module,
            _G_DATA_MAP,
            params,
            cash=broker_conf["cash"],
            commission=broker_conf["commission"],
            slippage=broker_conf["slippage"],
            benchmark_nav=_G_BENCH_NAV,
        )
        return metrics
    except Exception as err:
        return {
            "cum_return": float("nan"),
            "final_value": float("nan"),
            "sharpe": float("nan"),
            "mdd": float("nan"),
            "bench_return": float("nan"),
            "bench_mdd": float("nan"),
            "excess_return": float("nan"),
            "error": str(err),
        }

