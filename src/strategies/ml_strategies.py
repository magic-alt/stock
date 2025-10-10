# -*- coding: utf-8 -*-
"""
机器学习策略（走步训练）

特性：
- 自动构造特征（收益、波动、斜率、RSI/MACD/BOLL 等）
- 走步/扩展窗口训练，避免数据泄漏
- 支持模型：逻辑回归 / 随机森林；model="auto" 时优先RF，缺失则退化到LR
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from .base import BaseStrategy

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    SK_OK = True
except Exception:
    SK_OK = False


class MLWalkForwardStrategy(BaseStrategy):
    def __init__(self,
                 label_horizon: int = 1,
                 min_train: int = 200,
                 prob_threshold: float = 0.55,
                 model: str = "auto",
                 use_regime_ma: int = 100):
        """
        Args:
            label_horizon: 预测未来h天收益符号，默认1天
            min_train: 最小训练样本数
            prob_threshold: 做多概率阈值
            model: 'auto'|'rf'|'lr'
            use_regime_ma: 趋势过滤的长期均线天数（<=0 关闭）
        """
        super().__init__(name=f"ML-走步(h={label_horizon})")
        self.h, self.min_train, self.pt, self.model = label_horizon, min_train, prob_threshold, model
        self.regime_ma = use_regime_ma

    # ---- 特征工程 ----
    @staticmethod
    def _ta(df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)
        close = df['收盘']
        high, low = df['最高'], df['最低']

        # 收益/波动/斜率
        out['ret1'] = close.pct_change(1)
        out['ret5'] = close.pct_change(5)
        out['vol10'] = out['ret1'].rolling(10, min_periods=5).std()
        out['slope5'] = close.rolling(5, min_periods=3).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0], raw=False)

        # MA/EMA
        for p in (5, 10, 20, 60):
            out[f'ma{p}'] = close.rolling(p, min_periods=max(2, p//2)).mean()
            out[f'ema{p}'] = close.ewm(span=p, adjust=False, min_periods=max(2, p//2)).mean()

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14, min_periods=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14, min_periods=7).mean()
        rs = gain / loss.replace(0, np.nan)
        out['rsi14'] = (100 - 100/(1+rs)).fillna(50.0)

        # MACD
        ema12 = close.ewm(span=12, adjust=False, min_periods=6).mean()
        ema26 = close.ewm(span=26, adjust=False, min_periods=10).mean()
        macd = ema12 - ema26
        macds = macd.ewm(span=9, adjust=False, min_periods=5).mean()
        out['macd'] = macd
        out['macd_hist'] = macd - macds

        # BOLL
        m = close.rolling(20, min_periods=10).mean()
        s = close.rolling(20, min_periods=10).std()
        out['boll_z'] = (close - m) / s.replace(0, np.nan)

        # 价量
        if '成交量' in df.columns:
            vol = df['成交量'].replace(0, np.nan)
            out['v_ma5'] = vol.rolling(5, min_periods=3).mean()
            out['v_ma20'] = vol.rolling(20, min_periods=10).mean()
            out['v_ratio'] = out['v_ma5'] / out['v_ma20']

        return out.replace([np.inf, -np.inf], np.nan).fillna(method='bfill').fillna(0)

    def _build_label(self, close: pd.Series) -> pd.Series:
        fwd = close.shift(-self.h) / close - 1.0
        y = (fwd > 0).astype(int)
        return y

    def _make_model(self):
        if self.model == 'rf' or (self.model == 'auto' and SK_OK):
            return RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42)
        if self.model == 'lr' or (self.model == 'auto' and not SK_OK):
            return LogisticRegression(max_iter=1000, n_jobs=None if not SK_OK else None)
        return None

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self._ta(df)
        y = self._build_label(df['收盘'])
        df_out = df.copy()

        if len(X) < self.min_train + 10:
            warnings.warn("样本不足，返回空信号")
            df_out['Signal'] = 0
            df_out['Position'] = 0
            return df_out

        probs = pd.Series(0.0, index=X.index, dtype=float)
        model = self._make_model()
        if model is None:
            warnings.warn("未找到可用模型，默认空信号")
            df_out['Signal'] = 0
            df_out['Position'] = 0
            return df_out

        # 走步/扩展窗口训练
        for i in range(self.min_train, len(X)-self.h):
            X_train = X.iloc[:i, :].values
            y_train = y.iloc[:i].values
            X_pred = X.iloc[i:i+1, :].values
            try:
                model.fit(X_train, y_train)
                if hasattr(model, "predict_proba"):
                    prob = float(model.predict_proba(X_pred)[0, 1])
                else:
                    # LR 决策函数转概率（粗略Sigmoid）
                    if hasattr(model, "decision_function"):
                        z = float(model.decision_function(X_pred)[0])
                        prob = 1 / (1 + np.exp(-z))
                    else:
                        prob = float(model.predict(X_pred)[0])
            except Exception:
                prob = 0.0
            probs.iloc[i] = prob

        # 趋势过滤
        if self.regime_ma and self.regime_ma > 0:
            regime = df['收盘'].rolling(self.regime_ma, min_periods=max(5, self.regime_ma//5)).mean()
            uptrend = (df['收盘'] > regime).fillna(False)
        else:
            uptrend = pd.Series(True, index=df.index)

        sig = ((probs >= self.pt) & uptrend).astype(int)  # 仅做多版本
        df_out['Signal'] = sig.shift(1).fillna(0)  # T日训练，T+1日执行
        df_out['Position'] = df_out['Signal'].diff().fillna(0)
        df_out['ML_Prob'] = probs
        return df_out