# -*- coding: utf-8 -*-
"""
套利策略集合

V3.0.0 优化:
- 增加 z_stop 极端 Z-Score 强制止损
- 防止趋势行情下价差持续发散
"""
import numpy as np
import pandas as pd
from .base import BaseStrategy


class AlphaHedgeStrategy(BaseStrategy):
    """
    alpha 对冲（股票+期货/指数）：对目标资产的超额收益做多，同时按 rolling beta 做对冲。
    df 需包含一列对冲标的收盘价：默认列名 '对冲收盘'（可通过参数 hedge_col 指定）。
    仅输出做多/空仓信号（对冲规模由执行引擎/外部下单层完成）。
    """
    def __init__(self, beta_window: int = 60, hedge_col: str = "对冲收盘"):
        super().__init__(name=f"alpha对冲(beta{beta_window})")
        self.w, self.hcol = beta_window, hedge_col

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.hcol not in df.columns:
            # 缺少对冲列，无法构建信号
            out = df.copy()
            out['Signal'] = 0
            out['Position'] = 0
            return out
        out = df.copy()
        r_s = out['收盘'].pct_change()
        r_h = out[self.hcol].pct_change()
        cov = r_s.rolling(self.w, min_periods=max(10, self.w//3)).cov(r_h)
        var = r_h.rolling(self.w, min_periods=max(10, self.w//3)).var().replace(0, np.nan)
        beta = (cov / var).fillna(0)
        alpha = r_s - beta * r_h
        # 做多正 alpha 的扩散均值
        ma = alpha.rolling(10, min_periods=5).mean()
        sig = (ma > 0).astype(int)
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class CrossCommodityArbStrategy(BaseStrategy):
    """
    跨品种套利（期货）：价差 ZScore 回归
    需要 '对冲收盘' 列（另一品种），基于 spread = target - hedge*beta
    
    V3.0.0 优化:
    - z_stop: 极端 Z-Score 止损阈值 (默认 4.0)
    - 当 |Z| > z_stop 时强制平仓，防止价差趋势性发散
    """
    def __init__(self, hedge_col: str = "对冲收盘", z_window: int = 60, 
                 z_entry: float = 1.5, z_exit: float = 0.5, z_stop: float = 4.0):
        super().__init__(name="跨品种套利")
        self.hcol, self.w, self.ze, self.zx, self.zs = hedge_col, z_window, z_entry, z_exit, z_stop

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.hcol not in df.columns:
            out = df.copy()
            out['Signal'] = 0
            out['Position'] = 0
            return out
        out = df.copy()
        r_s = out['收盘'].pct_change()
        r_h = out[self.hcol].pct_change()
        cov = r_s.rolling(self.w, min_periods=max(10, self.w//3)).cov(r_h)
        var = r_h.rolling(self.w, min_periods=max(10, self.w//3)).var().replace(0, np.nan)
        beta = (cov / var).fillna(0)
        spread = out['收盘'] - beta * out[self.hcol]
        z = (spread - spread.rolling(self.w, min_periods=max(10, self.w//3)).mean()) / spread.rolling(self.w, min_periods=max(10, self.w//3)).std().replace(0, np.nan)
        z = z.fillna(0)
        # z<-ze 做多价差（买目标卖对冲）；z>+ze 做空价差（卖目标买对冲）
        raw = np.where(z < -self.ze, 1, np.where(z > self.ze, -1, np.nan))
        # 平仓条件 |z|<zx
        exit_sig = (z.abs() < self.zx)
        # V3.0: z_stop 强制止损
        stop_sig = (z.abs() > self.zs)
        sig = pd.Series(raw, index=out.index).ffill()
        sig[exit_sig] = 0
        sig[stop_sig] = 0  # V3.0: 极端 Z-Score 强制平仓
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class CalendarSpreadArbStrategy(BaseStrategy):
    """
    跨期套利（期货）：近远月价差 ZScore 回归
    需要 '近月收盘'、'远月收盘' 列。
    
    V3.0.0 优化:
    - z_stop: 极端 Z-Score 止损阈值 (默认 4.0)
    """
    def __init__(self, near_col: str = "近月收盘", far_col: str = "远月收盘",
                 z_window: int = 60, z_entry: float = 1.5, z_exit: float = 0.5,
                 z_stop: float = 4.0):
        super().__init__(name="跨期套利")
        self.ncol, self.fcol, self.w, self.ze, self.zx, self.zs = near_col, far_col, z_window, z_entry, z_exit, z_stop

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.ncol not in df.columns or self.fcol not in df.columns:
            out = df.copy()
            out['Signal'] = 0
            out['Position'] = 0
            return out
        out = df.copy()
        spread = out[self.ncol] - out[self.fcol]
        ma = spread.rolling(self.w, min_periods=max(10, self.w//3)).mean()
        sd = spread.rolling(self.w, min_periods=max(10, self.w//3)).std().replace(0, np.nan)
        z = ((spread - ma) / sd).fillna(0)
        raw = np.where(z < -self.ze, 1, np.where(z > self.ze, -1, np.nan))
        exit_sig = (z.abs() < self.zx)
        # V3.0: z_stop 强制止损
        stop_sig = (z.abs() > self.zs)
        sig = pd.Series(raw, index=out.index).ffill()
        sig[exit_sig] = 0
        sig[stop_sig] = 0  # V3.0: 极端 Z-Score 强制平仓
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out