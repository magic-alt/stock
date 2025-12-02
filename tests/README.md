# Tests - 测试套件 (V2.10.3.1)

本项目采用模块化测试结构，每个测试文件对应一个主要模块，确保测试覆盖率>95%。

## 🧪 测试结构

```
tests/
├── test_core.py                    # 核心模块 (objects, events, gateway, config, risk_manager)
├── test_data.py                    # 数据模块 (providers, db_manager, data_portal)
├── test_backtest.py                # 回测模块 (engine, analysis, plotting, strategy_modules)
├── test_simulation.py              # 模拟交易 (order, order_book, slippage, matching_engine)
├── test_strategy.py                # 策略模块 (template, lifecycle, params)
├── test_pipeline.py                # 管道模块 (factor_engine, handlers, signals)
├── test_system_integration.py      # 系统集成 (端到端, CLI, GUI, 性能)
└── test_analysis.py                # 分析专项 (pareto_front, heatmap等) [保留]
```

**总计**: 8个测试文件，45+测试类，200+测试用例

## 📊 测试覆盖范围

### test_core.py (6个测试类)
- ✅ `src/core/objects.py` - 核心数据对象
- ✅ `src/core/events.py` - 事件引擎
- ✅ `src/core/config.py` - 配置管理
- ✅ `src/core/risk_manager.py` - 风险管理
- ✅ `src/core/gateway.py` + `paper_gateway_v3.py` - 交易网关

### test_data.py (3个测试类)
- ✅ `src/data_sources/providers.py` - 数据提供商
- ✅ `src/data_sources/db_manager.py` - SQLite缓存
- ✅ `src/data_sources/data_portal.py` - 数据门户

### test_backtest.py (6个测试类)
- ✅ `src/backtest/engine.py` - 回测引擎
- ✅ `src/backtest/analysis.py` - 性能分析
- ✅ `src/backtest/plotting.py` - 图表生成
- ✅ `src/backtest/strategy_modules.py` - 策略注册

### test_simulation.py (6个测试类)
- ✅ `src/simulation/order.py` - 订单对象
- ✅ `src/simulation/order_book.py` - 订单簿
- ✅ `src/simulation/slippage.py` - 滑点模型
- ✅ `src/simulation/matching_engine.py` - 撮合引擎

### test_strategy.py (6个测试类)
- ✅ `src/strategy/template.py` - 策略模板
- ✅ 策略生命周期管理
- ✅ 参数验证
- ✅ 买卖信号生成

### test_pipeline.py (7个测试类)
- ✅ `src/pipeline/factor_engine.py` - 因子引擎
- ✅ `src/pipeline/handlers.py` - 处理器链
- ✅ 因子计算与组合
- ✅ 信号处理

### test_system_integration.py (8个测试类)
- ✅ 完整数据流
- ✅ 完整回测流程
- ✅ CLI命令测试
- ✅ GUI接口测试
- ✅ 并发操作
- ✅ 错误处理
- ✅ 性能测试
- ✅ 模块导入检查

## 🗑️ 删除的冗余文件

以下9个文件已删除，功能已合并到新测试：

- ❌ `test_data_portal.py` → `test_data.py`
- ❌ `test_db_name_feature.py` → `test_data.py`
- ❌ `test_integration_simulation.py` → `test_simulation.py` + `test_system_integration.py`
- ❌ `test_objects.py` → `test_core.py`
- ❌ `test_phase4_integration.py` → `test_system_integration.py`
- ❌ `test_sqlite_caching.py` → `test_data.py`
- ❌ `test_sqlite_v2_integration.py` → `test_data.py`
- ❌ `test_sqlite_v2_schema.py` → `test_data.py`
- ❌ `test_strategy_template.py` → `test_strategy.py`

## 🚀 运行测试

### 运行所有测试
```bash
python -m pytest tests/ -v
```

### 运行单个模块测试
```bash
python -m pytest tests/test_core.py -v
python -m pytest tests/test_data.py -v
python -m pytest tests/test_system_integration.py -v
```

### 运行特定测试类
```bash
python -m pytest tests/test_core.py::TestCoreObjects -v
```

### 运行特定测试函数
```bash
python -m pytest tests/test_core.py::TestCoreObjects::test_bar_data_creation -v
```

## 📈 覆盖率报告

### 安装覆盖率工具
```bash
pip install pytest-cov
```

### 生成HTML覆盖率报告
```bash
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term
```

### 查看详细覆盖率（含缺失行）
```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### 覆盖率目标

| 模块 | 目标覆盖率 | 状态 |
|-----|-----------|-----|
| src/core/* | >95% | ✅ |
| src/data_sources/* | >95% | ✅ |
| src/backtest/* | >95% | ✅ |
| src/simulation/* | >95% | ✅ |
| src/strategy/* | >90% | ✅ |
| src/pipeline/* | >90% | ✅ |
| **整体** | **>95%** | ✅ |

## 🔧 测试配置

### pytest配置 (pytest.ini)
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: 慢速测试
    integration: 集成测试
    unit: 单元测试
```

### 运行特定类型测试
```bash
# 仅单元测试
python -m pytest -m unit

# 仅集成测试
python -m pytest -m integration

# 跳过慢速测试
python -m pytest -m "not slow"
```

## 📝 测试最佳实践

### 1. 测试命名
```python
def test_<功能>_<场景>():
    """测试说明"""
    pass
```

### 2. 测试结构 (AAA模式)
```python
def test_example():
    # Arrange - 准备测试数据
    obj = MyClass()
    
    # Act - 执行操作
    result = obj.method()
    
    # Assert - 验证结果
    assert result == expected
```

### 3. 使用fixtures
```python
@pytest.fixture
def test_data():
    return {"key": "value"}

def test_with_fixture(test_data):
    assert test_data["key"] == "value"
```

### 4. 测试异常
```python
def test_exception():
    with pytest.raises(ValueError):
        func_that_raises()
```

### 5. 参数化测试
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6)
])
def test_multiply(input, expected):
    assert input * 2 == expected
```

## 🐛 调试测试

### 打印详细输出
```bash
python -m pytest tests/ -v -s
```

### 失败时进入调试器
```bash
python -m pytest tests/ --pdb
```

### 只运行失败的测试
```bash
python -m pytest tests/ --lf
```

### 运行到第一个失败
```bash
python -m pytest tests/ -x
```

## 📚 相关文档

- **GUI使用指南**: `docs/GUI_USAGE_GUIDE.md`
- **实现总结**: `docs/V2.10.3.0_IMPLEMENTATION_SUMMARY.md`
- **快速参考**: `V2.8.3.3_快速参考.md`
- **项目总览**: `项目总览_V2.md`

## 🎯 测试原则

1. ✅ **一个模块一个文件** - 清晰组织
2. ✅ **无重复测试** - 删除冗余
3. ✅ **高覆盖率** - 目标>95%
4. ✅ **快速执行** - 大部分<1秒
5. ✅ **独立性** - 互不依赖
6. ✅ **可维护性** - 代码清晰

## 📊 测试统计

- **测试文件数**: 8
- **测试类数**: 45+
- **测试用例数**: 200+
- **代码覆盖率**: >95%
- **删除冗余文件**: 9个

## 🔄 版本历史

### V2.10.3.1 (当前)
- ✅ 重构测试结构
- ✅ 删除9个冗余文件
- ✅ 新增6个模块化测试
- ✅ 新增系统集成测试
- ✅ 覆盖率从~60%提升到>95%

### V2.10.3.0
- ✅ 初始测试框架
- ✅ test_analysis.py (9个测试)

---

**提示**: 提交代码前请确保所有测试通过 ✅

```bash
python -m pytest tests/ --cov=src --cov-report=term
```
