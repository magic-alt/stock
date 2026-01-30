# Examples - 示例代码

本目录包含量化回测系统的各种使用示例。

## 📋 示例列表

### 1. quick_start.py - 快速开始
**适合新手** | 5分钟上手

演示最基本的单策略回测流程：
```bash
python examples/quick_start.py
```

学习内容：
- 创建回测引擎
- 运行单次回测
- 查看性能指标

---

### 2. batch_backtest.py - 批量回测
**适合进阶** | 多股票多策略

演示自动化批量测试流程：
```bash
python examples/batch_backtest.py
```

学习内容：
- 多股票 × 多策略组合
- 自动化流程
- Pareto前沿分析

---

### 3. ml_strategy_gallery.py - ML策略合集
**适合进阶** | ML 策略速览

快速浏览多个 ML 策略的信号输出：
```bash
python examples/ml_strategy_gallery.py
```

学习内容：
- MLWalkForward / DeepSequence / RegimeAdaptive
- MLEnhanced / MLEnsemble

---

### 4. ml_enhanced_examples.py - ML增强与集成
**适合进阶** | 特征工程 + 集成策略

演示 MLEnhancedStrategy 与 MLEnsembleStrategy 的基本用法：
```bash
python examples/ml_enhanced_examples.py
```

学习内容：
- 归一化特征 + 置信度阈值
- 多模型概率融合

---

## 🚀 运行所有示例

```bash
# Windows
Get-ChildItem examples\*.py | ForEach-Object { python $_.FullName }

# Linux/Mac
for script in examples/*.py; do python "$script"; done
```

## 📚 更多资源

- **完整文档**: `docs/`
- **GUI界面**: `python scripts/backtest_gui.py`
- **CLI工具**: `python unified_backtest_framework.py --help`
- **测试代码**: `tests/`

## 💡 自定义示例

复制任一示例文件，修改参数即可：
```python
# 修改股票代码
symbols = ["your_symbol_here"]

# 修改策略
strategy_name = "your_strategy"

# 修改时间范围
start = "2020-01-01"
end = "2024-12-31"
```

---

**注意**: 首次运行会下载数据，可能需要几分钟时间。
