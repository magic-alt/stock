# Examples - 示例代码

本目录包含量化回测系统的各种使用示例。建议第一次从无需外部数据源和券商 SDK 的一键 demo 开始。

## 📋 示例列表

### 1. one_click_demo.py - 开源预览一键 demo
**适合首次体验** | 无需网络数据、token 或券商 SDK

生成纸面交易演示报告、Markdown 摘要和 ECharts 可用 JSON：
```bash
python examples/one_click_demo.py --out-dir report/open_source_demo
```

输出内容：
- `platform_console_demo.json`
- `demo_report.md`
- `web_console_echarts.json`

---

### 2. quick_start.py - 快速开始
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

### 3. batch_backtest.py - 批量回测
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

### 4. ml_strategy_gallery.py - ML策略合集
**适合进阶** | ML 策略速览

快速浏览多个 ML 策略的信号输出：
```bash
python examples/ml_strategy_gallery.py
```

学习内容：
- MLWalkForward / DeepSequence / RegimeAdaptive
- MLEnhanced / MLEnsemble

---

### 5. ml_enhanced_examples.py - ML增强与集成
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

**注意**: `one_click_demo.py` 使用 `sample_data/` 中的内置样例数据；其他回测示例首次运行可能会下载数据，可能需要几分钟时间。
