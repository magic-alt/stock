"""
ML 增强策略 (特征工程优化版)

V3.0.0-beta.4

优化点：
1. 特征归一化：将价格相关特征转换为相对值
2. 波动率标准化：slope/diff 除以价格或 ATR
3. 置信度阈值：prob > 0.6 才交易，提高胜率

解决痛点：
- slope/diff 绝对值随股价高低剧烈变化
- 模型难以泛化
- prob > 0.5 胜率太低
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

# 依赖检查
try:
    from .base import BaseStrategy
except ImportError:
    class BaseStrategy:
        def __init__(self, name: str = "ML"):
            self.name = name
        def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

# 检查 sklearn
_HAS_SKLEARN = False
RandomForestClassifier = None
GradientBoostingClassifier = None
StandardScaler = None
Pipeline = None
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    _HAS_SKLEARN = True
except ImportError:
    pass

# 检查 xgboost
_HAS_XGB = False
try:
    import xgboost as xgb
    _HAS_XGB = True
except ImportError:
    pass


class _IdentityScaler:
    """Fallback scaler when sklearn is unavailable."""

    def fit_transform(self, X):
        return X

    def transform(self, X):
        return X


class MLEnhancedStrategy(BaseStrategy):
    """
    机器学习增强策略
    
    核心改进：
    1. 特征归一化：所有价格相关特征转为相对值
    2. 对数收益率：比普通收益率分布更正态
    3. 波动率比率：当前波动率相对历史的比例
    4. 置信度阈值：提高到 0.6，过滤低信心交易
    """
    
    def __init__(
        self,
        label_horizon: int = 1,
        min_train: int = 200,
        prob_threshold: float = 0.60,
        model_type: str = "rf",
        retrain_interval: int = 20,
    ):
        """
        参数:
            label_horizon: 标签预测周期
            min_train: 最小训练样本数
            prob_threshold: 置信度阈值 (默认 0.6)
            model_type: 模型类型 ('rf', 'gb', 'xgb')
            retrain_interval: 重训练间隔
        """
        super().__init__(name="ML-Enhanced")
        self.h = int(label_horizon)
        self.min_train = int(min_train)
        self.prob_threshold = float(prob_threshold)
        self.model_type = model_type
        self.retrain_interval = int(retrain_interval)
        
        self._model = None
        self._scaler = StandardScaler() if (_HAS_SKLEARN and StandardScaler is not None) else None
        self._last_train_idx = 0
        
    def _get_model(self):
        """获取模型实例"""
        if self.model_type == "xgb" and _HAS_XGB:
            return xgb.XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                use_label_encoder=False,
                eval_metric='logloss',
                verbosity=0,
            )
        elif self.model_type == "gb" and _HAS_SKLEARN and GradientBoostingClassifier is not None:
            return GradientBoostingClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
            )
        elif _HAS_SKLEARN and RandomForestClassifier is not None:
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=6,
                min_samples_split=10,
                random_state=42,
                n_jobs=-1,
            )
        else:
            return None
            
    @staticmethod
    def _ta(df: pd.DataFrame) -> pd.DataFrame:
        """
        优化后的特征工程：标准化处理
        
        所有特征都是无量纲的或相对值：
        1. 对数收益率 - 分布更正态
        2. 波动率比率 - 当前/历史
        3. 均线距离百分比 - (price - ma) / ma
        4. RSI - 本身就是 0-100 归一化
        5. 相对成交量 - vol / ma(vol)
        """
        # 获取价格列
        if "close" in df.columns:
            close = df['close'].astype(float)
            high = df.get('high', close).astype(float)
            low = df.get('low', close).astype(float)
            vol = df.get('volume', None)
        else:
            close = df['收盘'].astype(float)
            high = df.get('最高', close).astype(float)
            low = df.get('最低', close).astype(float)
            vol = df.get('成交量', None)
            
        out = pd.DataFrame(index=df.index)
        
        # 1. 对数收益率 (比普通收益率分布更正态)
        out['ret1'] = np.log(close / close.shift(1))
        out['ret5'] = np.log(close / close.shift(5))
        out['ret10'] = np.log(close / close.shift(10))
        out['ret20'] = np.log(close / close.shift(20))
        
        # 2. 波动率归一化
        std_5 = out['ret1'].rolling(5).std()
        std_20 = out['ret1'].rolling(20).std()
        std_60 = out['ret1'].rolling(60).mean()
        out['vol_ratio_5_20'] = std_5 / std_20.replace(0, np.nan)
        out['vol_ratio_20_60'] = std_20 / std_60.replace(0, np.nan)

        # 3. 均线距离 (百分比而非绝对值)
        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        
        out['dist_ma5'] = (close - ma5) / ma5
        out['dist_ma10'] = (close - ma10) / ma10
        out['dist_ma20'] = (close - ma20) / ma20
        out['dist_ma60'] = (close - ma60) / ma60
        
        # 均线斜率 (百分比变化)
        out['ma5_slope'] = ma5.pct_change(5)
        out['ma20_slope'] = ma20.pct_change(10)
        
        # 4. RSI (本身就是归一化的 0-100)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        out['rsi14'] = 100 - (100 / (1 + rs))
        
        # 短周期 RSI
        gain7 = (delta.where(delta > 0, 0)).rolling(7).mean()
        loss7 = (-delta.where(delta < 0, 0)).rolling(7).mean()
        rs7 = gain7 / loss7.replace(0, np.nan)
        out['rsi7'] = 100 - (100 / (1 + rs7))
        
        # 5. MACD 归一化
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        out['macd_pct'] = macd / close  # 百分比
        out['macd_hist_pct'] = (macd - signal) / close
        
        # 6. 布林带位置 (0-1 归一化)
        bb_mid = ma20
        bb_std = close.rolling(20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb_width = bb_upper - bb_lower
        out['bb_position'] = (close - bb_lower) / bb_width.replace(0, np.nan)
        out['bb_width_pct'] = bb_width / bb_mid

        # 7. 相对成交量
        if vol is not None:
            vol = vol.astype(float)
            vol_ma5 = vol.rolling(5).mean()
            vol_ma20 = vol.rolling(20).mean()
            out['vol_ratio_5'] = vol / vol_ma5.replace(0, np.nan)
            out['vol_ratio_20'] = vol / vol_ma20.replace(0, np.nan)
            
        # 8. K线形态 (归一化)
        body = close - df.get('open', close.shift(1)).astype(float)
        range_hl = high - low
        out['body_pct'] = body / range_hl.replace(0, np.nan)
        out['upper_shadow'] = (high - close.where(close > df.get('open', close.shift(1)), df.get('open', close.shift(1)))) / range_hl.replace(0, np.nan)
        out['lower_shadow'] = (close.where(close < df.get('open', close.shift(1)), df.get('open', close.shift(1))) - low) / range_hl.replace(0, np.nan)

        # 清理无穷值
        return out.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    def _create_labels(self, close: pd.Series) -> pd.Series:
        """创建标签：未来 h 天收益是否为正"""
        future_ret = close.shift(-self.h) / close - 1
        return (future_ret > 0).astype(int)
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        返回带有 Signal 列的 DataFrame:
        - Signal = 1: 买入
        - Signal = 0: 持有/空仓
        - Signal = -1: 卖出 (如果支持做空)
        """
        if not _HAS_SKLEARN:
            warnings.warn("sklearn not installed, returning zero signals")
            df_out = df.copy()
            df_out['Signal'] = 0
            df_out['Probability'] = 0.5
            return df_out
            
        # 特征工程
        X = self._ta(df)
        feature_cols = X.columns.tolist()
        
        # 获取收盘价
        if "close" in df.columns:
            close = df['close'].astype(float)
        else:
            close = df['收盘'].astype(float)
            
        # 创建标签
        y = self._create_labels(close)
        
        # 初始化输出
        df_out = df.copy()
        df_out['Signal'] = 0
        df_out['Probability'] = 0.5
        
        # 滚动训练预测
        for i in range(self.min_train, len(df)):
            # 检查是否需要重训练
            if self._model is None or (i - self._last_train_idx) >= self.retrain_interval:
                # 训练数据
                train_idx = max(0, i - self.min_train * 2)  # 使用最近的数据
                X_train = X.iloc[train_idx:i].values
                y_train = y.iloc[train_idx:i].values
                
                # 过滤 NaN 标签
                valid_mask = ~np.isnan(y_train)
                if valid_mask.sum() < self.min_train // 2:
                    continue
                    
                X_train = X_train[valid_mask]
                y_train = y_train[valid_mask].astype(int)
                
                # 标准化
                if self._scaler is None:
                    if StandardScaler is not None:
                        self._scaler = StandardScaler()
                    else:
                        self._scaler = _IdentityScaler()
                X_train_scaled = self._scaler.fit_transform(X_train)
                
                # 训练模型
                self._model = self._get_model()
                if self._model is None:
                    continue
                    
                try:
                    self._model.fit(X_train_scaled, y_train)
                    self._last_train_idx = i
                except Exception as e:
                    warnings.warn(f"Model training failed: {e}")
                    continue
            
            # 预测
            if self._model is not None and self._scaler is not None:
                try:
                    X_pred = X.iloc[i:i+1].values
                    X_pred_scaled = self._scaler.transform(X_pred)
                    prob = self._model.predict_proba(X_pred_scaled)[0, 1]
                    
                    df_out.iloc[i, df_out.columns.get_loc('Probability')] = prob
                    
                    # 信号生成：使用更高的阈值
                    if prob > self.prob_threshold:
                        df_out.iloc[i, df_out.columns.get_loc('Signal')] = 1
                    elif prob < (1 - self.prob_threshold):
                        df_out.iloc[i, df_out.columns.get_loc('Signal')] = -1
                        
                except Exception as e:
                    pass
                    
        return df_out
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """获取特征重要性"""
        if self._model is None:
            return None
            
        if hasattr(self._model, 'feature_importances_'):
            # 需要特征名称
            return dict(enumerate(self._model.feature_importances_))
        return None


class MLEnsembleStrategy(BaseStrategy):
    """
    集成学习策略
    
    组合多个模型的预测结果，提高稳定性
    """
    
    def __init__(
        self,
        prob_threshold: float = 0.60,
        min_train: int = 200,
    ):
        super().__init__(name="ML-Ensemble")
        self.prob_threshold = prob_threshold
        self.min_train = min_train
        
        self._models = {}
        if _HAS_SKLEARN:
            self._models['rf'] = MLEnhancedStrategy(
                prob_threshold=prob_threshold,
                min_train=min_train,
                model_type='rf'
            )
            self._models['gb'] = MLEnhancedStrategy(
                prob_threshold=prob_threshold,
                min_train=min_train,
                model_type='gb'
            )
        if _HAS_XGB:
            self._models['xgb'] = MLEnhancedStrategy(
                prob_threshold=prob_threshold,
                min_train=min_train,
                model_type='xgb'
            )
            
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        集成预测
        
        只有当多数模型同意时才发出信号
        """
        if not self._models:
            df_out = df.copy()
            df_out['Signal'] = 0
            df_out['Probability'] = 0.5
            return df_out
            
        # 收集各模型预测
        predictions = []
        for name, model in self._models.items():
            result = model.generate_signals(df)
            predictions.append(result['Probability'])
            
        # 平均概率
        avg_prob = pd.concat(predictions, axis=1).mean(axis=1)
        
        df_out = df.copy()
        df_out['Probability'] = avg_prob
        df_out['Signal'] = 0
        df_out.loc[avg_prob > self.prob_threshold, 'Signal'] = 1
        df_out.loc[avg_prob < (1 - self.prob_threshold), 'Signal'] = -1
        
        return df_out


# 策略配置
def _coerce_ml_enhanced(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    if "label_horizon" in out: out["label_horizon"] = int(out["label_horizon"])
    if "min_train" in out: out["min_train"] = int(out["min_train"])
    if "prob_threshold" in out: out["prob_threshold"] = float(out["prob_threshold"])
    if "retrain_interval" in out: out["retrain_interval"] = int(out["retrain_interval"])
    return out


ML_ENHANCED_CONFIG = {
    'name': 'ml_enhanced',
    'description': 'Machine Learning Strategy with Normalized Features',
    'strategy_class': MLEnhancedStrategy,
    'param_names': ['label_horizon', 'min_train', 'prob_threshold', 'model_type'],
    'defaults': {
        'label_horizon': 1,
        'min_train': 200,
        'prob_threshold': 0.60,
        'model_type': 'rf',
    },
    'grid_defaults': {
        'label_horizon': [1, 3, 5],
        'prob_threshold': [0.55, 0.60, 0.65],
    },
    'coercer': _coerce_ml_enhanced,
    'multi_symbol': False,
}

ML_ENSEMBLE_CONFIG = {
    'name': 'ml_ensemble',
    'description': 'Ensemble ML Strategy combining RF, GB, XGB',
    'strategy_class': MLEnsembleStrategy,
    'param_names': ['prob_threshold', 'min_train'],
    'defaults': {
        'prob_threshold': 0.60,
        'min_train': 200,
    },
    'coercer': _coerce_ml_enhanced,
    'multi_symbol': False,
}


__all__ = [
    'MLEnhancedStrategy',
    'MLEnsembleStrategy',
    '_coerce_ml_enhanced',
    'ML_ENHANCED_CONFIG',
    'ML_ENSEMBLE_CONFIG',
]
