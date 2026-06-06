"""
测试管道模块 (src/pipeline/*)
覆盖: factor_engine, handlers
"""

from __future__ import annotations

import pytest

from src.pipeline.factor_engine import (
    Factor, Pipeline, create_pipeline,
    Returns, Momentum, RSI, SMA, EMA, MACD,
    Volume, VolumeRatio, Volatility, BollingerBands, ATR,
)
from src.pipeline.handlers import (
    PipelineEventCollector, make_pipeline_handlers,
    ProgressTrackingCollector, make_progress_handlers
)


def _make_ohlcv(n: int = 60, seed: int = 42) -> pd.DataFrame:
    """Create a realistic OHLCV DataFrame for testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "open": close - rng.uniform(0.5, 1.5, n),
        "high": close + rng.uniform(0.5, 2.0, n),
        "low": close - rng.uniform(0.5, 2.0, n),
        "close": close,
        "volume": rng.integers(100_000, 1_000_000, n).astype(float),
    }, index=dates)


class TestFactorClasses:
    """测试因子类 - 实例化和计算验证"""

    def test_returns_factor_computation(self):
        """测试Returns因子计算"""
        factor = Returns(period=1)
        assert factor.name == "Returns"
        assert factor.params["period"] == 1
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        # First value is NaN (no prior close)
        assert np.isnan(result.iloc[0])

    def test_momentum_factor_computation(self):
        """测试Momentum因子计算"""
        factor = Momentum(period=10)
        assert factor.name == "Momentum"
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        # First 10 values should be NaN
        assert result.iloc[:10].isna().all()
        # Later values should be finite
        assert result.iloc[-1:].notna().all()

    def test_rsi_factor_computation(self):
        """测试RSI因子计算"""
        factor = RSI(period=14)
        assert factor.name == "RSI"
        data = _make_ohlcv(60)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        # RSI should be between 0 and 100 where not NaN
        valid = result.dropna()
        assert len(valid) > 0
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_sma_factor_computation(self):
        """测试SMA因子计算"""
        factor = SMA(period=10)
        assert factor.name == "SMA"
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        assert result.iloc[:9].isna().all()
        assert result.iloc[-1:].notna().all()

    def test_ema_factor_computation(self):
        """测试EMA因子计算"""
        factor = EMA(period=10)
        assert factor.name == "EMA"
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        # EMA starts from the first value (no NaN at beginning for ewm)
        assert result.notna().sum() > 20

    def test_macd_factor_computation(self):
        """测试MACD因子计算"""
        factor = MACD(fast=5, slow=10, signal=3)
        assert factor.name == "MACD"
        assert factor.params["fast"] == 5
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)

    def test_volume_factor(self):
        """测试Volume因子"""
        factor = Volume()
        data = _make_ohlcv(20)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        assert (result == data["volume"]).all()

    def test_volume_ratio_factor(self):
        """测试VolumeRatio因子"""
        factor = VolumeRatio(period=10)
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert len(valid) > 0
        # Volume ratio should be positive
        assert (valid > 0).all()

    def test_volatility_factor(self):
        """测试Volatility因子"""
        factor = Volatility(period=10)
        data = _make_ohlcv(30)
        result = factor.compute(data)
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert len(valid) > 0
        assert (valid >= 0).all()

    def test_factor_repr(self):
        """测试Factor repr"""
        factor = Momentum(period=20)
        repr_str = repr(factor)
        assert "Momentum" in repr_str
        assert "20" in repr_str

class TestPipelineClass:
    """测试Pipeline类 - 添加因子和运行"""

    def test_pipeline_creation(self):
        """测试Pipeline创建"""
        pipeline = Pipeline()
        assert pipeline is not None
        assert len(pipeline.factors) == 0

    def test_pipeline_add_factor(self):
        """测试Pipeline添加因子"""
        pipeline = Pipeline()
        result = pipeline.add("mom", Momentum(20))
        assert result is pipeline  # method chaining
        assert "mom" in pipeline.factors
        assert isinstance(pipeline.factors["mom"], Momentum)

    def test_pipeline_run_single_factor(self):
        """测试Pipeline运行单因子"""
        data = _make_ohlcv(30)
        pipeline = Pipeline()
        pipeline.add("returns", Returns(1))
        result = pipeline.run({"SYM1": data})
        assert isinstance(result, pd.DataFrame)
        assert "returns" in result.columns

    def test_pipeline_run_multiple_factors(self):
        """测试Pipeline运行多因子"""
        data = _make_ohlcv(60)
        pipeline = Pipeline()
        pipeline.add("mom", Momentum(10))
        pipeline.add("rsi", RSI(14))
        pipeline.add("sma", SMA(10))
        result = pipeline.run({"SYM1": data})
        assert isinstance(result, pd.DataFrame)
        assert "mom" in result.columns
        assert "rsi" in result.columns
        assert "sma" in result.columns

    def test_pipeline_empty_factors(self):
        """测试空Pipeline"""
        pipeline = Pipeline()
        result = pipeline.run({"SYM1": _make_ohlcv(10)})
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_create_pipeline_function(self):
        """测试create_pipeline工厂函数"""
        pipeline = create_pipeline(
            ("mom", Momentum(20)),
            ("rsi", RSI(14)),
        )
        assert isinstance(pipeline, Pipeline)
        assert "mom" in pipeline.factors
        assert "rsi" in pipeline.factors

    def test_pipeline_get_latest(self):
        """测试Pipeline获取最新值"""
        data = _make_ohlcv(30)
        pipeline = Pipeline()
        pipeline.add("returns", Returns(1))
        latest = pipeline.get_latest({"SYM1": data})
        # get_latest returns a DataFrame
        assert isinstance(latest, pd.DataFrame)

class TestHandlers:
    """测试处理器"""

    def test_pipeline_event_collector_creation(self):
        """测试PipelineEventCollector创建"""
        collector = PipelineEventCollector()
        assert collector is not None

    def test_make_pipeline_handlers_returns_list(self):
        """测试make_pipeline_handlers返回列表"""
        handlers = make_pipeline_handlers(out_dir="./test_output")
        assert isinstance(handlers, list)

    def test_progress_tracking_collector_creation(self):
        """测试ProgressTrackingCollector创建"""
        collector = ProgressTrackingCollector()
        assert collector is not None

    def test_make_progress_handlers_returns_list(self):
        """测试make_progress_handlers返回列表"""
        handlers = make_progress_handlers(out_dir="./test_output")
        assert isinstance(handlers, list)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
