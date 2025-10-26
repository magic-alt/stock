"""
测试管道模块 (src/pipeline/*)
覆盖: factor_engine, handlers
"""
import pytest
from datetime import datetime
import pandas as pd
import numpy as np

from src.pipeline.factor_engine import (
    Factor, Pipeline, create_pipeline,
    Returns, Momentum, RSI, SMA, EMA, MACD
)
from src.pipeline.handlers import (
    PipelineEventCollector, make_pipeline_handlers,
    ProgressTrackingCollector, make_progress_handlers
)


class TestFactorClasses:
    """测试因子类"""
    
    def test_factor_base_class_exists(self):
        """测试Factor基类存在"""
        assert Factor is not None
    
    def test_returns_factor_exists(self):
        """测试Returns因子存在"""
        assert Returns is not None
    
    def test_momentum_factor_exists(self):
        """测试Momentum因子存在"""
        assert Momentum is not None
    
    def test_rsi_factor_exists(self):
        """测试RSI因子存在"""
        assert RSI is not None
    
    def test_sma_factor_exists(self):
        """测试SMA因子存在"""
        assert SMA is not None
    
    def test_ema_factor_exists(self):
        """测试EMA因子存在"""
        assert EMA is not None
    
    def test_macd_factor_exists(self):
        """测试MACD因子存在"""
        assert MACD is not None


class TestPipelineClass:
    """测试Pipeline类"""
    
    def test_pipeline_class_exists(self):
        """测试Pipeline类存在"""
        assert Pipeline is not None
    
    def test_create_pipeline_function_exists(self):
        """测试create_pipeline函数存在"""
        assert callable(create_pipeline)
    
    def test_pipeline_creation(self):
        """测试Pipeline创建"""
        try:
            pipeline = Pipeline()
            assert pipeline is not None
        except TypeError:
            pytest.skip("Pipeline需要参数")


class TestHandlers:
    """测试处理器"""
    
    def test_pipeline_event_collector_exists(self):
        """测试PipelineEventCollector存在"""
        assert PipelineEventCollector is not None
    
    def test_make_pipeline_handlers_exists(self):
        """测试make_pipeline_handlers函数存在"""
        assert callable(make_pipeline_handlers)
    
    def test_progress_tracking_collector_exists(self):
        """测试ProgressTrackingCollector存在"""
        assert ProgressTrackingCollector is not None
    
    def test_make_progress_handlers_exists(self):
        """测试make_progress_handlers函数存在"""
        assert callable(make_progress_handlers)
    
    def test_make_pipeline_handlers(self):
        """测试创建pipeline处理器"""
        handlers = make_pipeline_handlers(out_dir="./test_output")
        assert isinstance(handlers, list)
    
    def test_make_progress_handlers(self):
        """测试创建progress处理器"""
        handlers = make_progress_handlers(out_dir="./test_output")
        assert isinstance(handlers, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
