# -*- coding: utf-8 -*-
"""
机器学习策略（走步训练 / 扩展窗口）

特性：
- 自动构造特征（收益、波动、斜率、RSI/MACD/BOLL/价量 等）
- 走步/扩展窗口训练，避免数据泄漏（T 训练、T+1 执行）
- 模型工厂：XGBoost/RandomForest/LogReg/SGDClassifier 以及可选 PyTorch MLP
- 内置 StandardScaler 管线；支持多空两侧概率阈值（做多/做空独立阈值）
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

try:
    # 兼容旧工程：若项目内有 BaseStrategy，可继续继承；否则降级为 object
    from .base import BaseStrategy  # type: ignore
except Exception:  # pragma: no cover
    class BaseStrategy:  # type: ignore
        def __init__(self, name: str = "ML-Strategy") -> None:
            self.name = name

# --- 依赖可用性探测 ---------------------------------------------------------
SK_OK = False
XGB_OK = False
TORCH_OK = False
try:
    from sklearn.linear_model import LogisticRegression, SGDClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    SK_OK = True
except Exception:
    pass
try:
    import xgboost as xgb  # type: ignore
    XGB_OK = True
except Exception:
    pass
try:
    import torch  # type: ignore
    import torch.nn as nn  # type: ignore
    TORCH_OK = True
except Exception:
    pass


class MLWalkForwardStrategy(BaseStrategy):
    def __init__(self,
                 label_horizon: int = 1,
                 min_train: int = 200,
                 prob_long: float = 0.55,
                 prob_short: float = 0.55,
                 model: str = "auto",
                 use_regime_ma: int = 100,
                 allow_short: bool = False,
                 use_partial_fit: bool = False):
        """
        Args:
            label_horizon: 预测未来h天收益符号，默认1天
            min_train: 最小训练样本数
            prob_long: 做多概率阈值
            prob_short: 做空概率阈值（需要 allow_short=True）
            model: 'auto'|'xgb'|'rf'|'lr'|'sgd'|'mlp'
            use_regime_ma: 趋势过滤的长期均线天数（<=0 关闭）
            allow_short: 是否允许做空（仅信号层面；实际成交取决于回测器）
            use_partial_fit: 若为 True 且模型支持，则使用增量训练
        """
        super().__init__(name=f"ML-走步(h={label_horizon})")
        self.h = int(label_horizon)
        self.min_train = int(min_train)
        self.pt_long = float(prob_long)
        self.pt_short = float(prob_short)
        self.model = str(model)
        self.regime_ma = int(use_regime_ma) if use_regime_ma is not None else 0
        self.allow_short = bool(allow_short)
        self.use_partial_fit = bool(use_partial_fit)

    # ---- 特征工程 ----
    @staticmethod
    def _ta(df: pd.DataFrame) -> pd.DataFrame:
        # 允许外部传入含英文列名的 DataFrame
        if "收盘" not in df.columns and "close" in df.columns:
            df = df.rename(columns={"open":"开盘","high":"最高","low":"最低","close":"收盘","volume":"成交量"})
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

        return out.replace([np.inf, -np.inf], np.nan).bfill().fillna(0)

    def _build_label(self, close: pd.Series) -> pd.Series:
        fwd = close.shift(-self.h) / close - 1.0
        y = (fwd > 0).astype(int)
        return y

    def _make_model(self):
        m = (self.model or "auto").lower()
        # 优先 xgboost
        if (m == "xgb" or m == "auto") and XGB_OK:
            return xgb.XGBClassifier(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.9, colsample_bytree=0.8, random_state=42,
                reg_lambda=1.0, n_jobs=-1
            )
        if (m == "rf" or (m == "auto" and SK_OK)):
            return RandomForestClassifier(n_estimators=300, max_depth=6, random_state=42, n_jobs=-1)
        if (m == "sgd") and SK_OK:
            return make_pipeline(StandardScaler(), SGDClassifier(loss="log_loss", max_iter=2000, random_state=42))
        if (m == "lr" or (m == "auto" and SK_OK)):
            return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, n_jobs=-1 if SK_OK else None))
        if (m == "mlp") and TORCH_OK:
            # 简单 MLP（在 _torch_predict/_torch_fit 内部处理）
            class _Tiny(nn.Module):  # type: ignore
                def __init__(self, d):
                    super().__init__()
                    self.net = nn.Sequential(
                        nn.Linear(d, 64), nn.ReLU(),
                        nn.Linear(64, 32), nn.ReLU(),
                        nn.Linear(32, 1)
                    )
                def forward(self, x):
                    return self.net(x)
            return ("torch_mlp", _Tiny)  # 返回构造器占位，实际维度训练时再实例化
        # 最后兜底：纯概率常数模型（永不交易）
        return None

    # --- Torch 支持（仅当 TORCH_OK=True 且选择 mlp 时启用） --------------------
    def _torch_fit(self, model_ctor, X_train, y_train):
        if not TORCH_OK:
            return None
        X = torch.tensor(X_train, dtype=torch.float32)  # type: ignore
        y = torch.tensor(y_train.reshape(-1, 1), dtype=torch.float32)  # type: ignore
        net = model_ctor(X.shape[1])
        opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)  # type: ignore
        loss_fn = nn.BCEWithLogitsLoss()  # type: ignore
        net.train()
        for _ in range(80):  # 轻量训练
            opt.zero_grad()
            pred = net(X)
            loss = loss_fn(pred, y)
            loss.backward()
            opt.step()
        net.eval()
        return net

    def _torch_predict(self, net, X_pred):
        X = torch.tensor(X_pred, dtype=torch.float32)  # type: ignore
        with torch.no_grad():
            z = net(X).numpy()
        # Sigmoid
        import numpy as _np
        prob = 1.0 / (1.0 + _np.exp(-z))
        return float(prob.squeeze())

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

        # 走步/扩展窗口训练：T 训练、T+1 执行
        for i in range(self.min_train, len(X)-self.h):
            X_train = X.iloc[:i, :].values
            y_train = y.iloc[:i].values
            X_pred = X.iloc[i:i+1, :].values
            try:
                if isinstance(model, tuple) and model[0] == "torch_mlp":
                    net = self._torch_fit(model[1], X_train, y_train)
                    prob = self._torch_predict(net, X_pred) if net is not None else 0.0
                else:
                    # sklearn/xgb
                    if self.use_partial_fit and hasattr(model, "partial_fit"):
                        # 首次需要 classes
                        if i == self.min_train:
                            model.partial_fit(X_train, y_train, classes=np.array([0,1]))
                        else:
                            model.partial_fit(X_train[-64:], y_train[-64:])  # 小批增量
                    else:
                        model.fit(X_train, y_train)
                    if hasattr(model, "predict_proba"):
                        prob = float(model.predict_proba(X_pred)[0, 1])
                    elif hasattr(model, "decision_function"):
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

        # 信号：多空独立阈值，可选允许做空；执行日 = 训练日 + 1
        long_sig = ((probs >= self.pt_long) & uptrend).astype(int)
        if self.allow_short:
            short_sig = ((probs <= (1 - self.pt_short)) & (~uptrend if self.regime_ma>0 else True)).astype(int)
            raw = long_sig - short_sig
        else:
            raw = long_sig
        df_out['Signal'] = raw.shift(1).fillna(0).astype(int)
        df_out['Position'] = df_out['Signal'].diff().fillna(0)
        df_out['ML_Prob'] = probs
        return df_out