# 量化回测系统 | Quantitative Backtesting Platform

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI Status](https://github.com/magic-alt/stock/workflows/CI/badge.svg)](https://github.com/magic-alt/stock/actions)
[![Code Coverage](https://codecov.io/gh/magic-alt/stock/branch/main/graph/badge.svg)](https://codecov.io/gh/magic-alt/stock)

> 企业级量化回测与实盘系统，基于 Backtrader + 事件驱动架构，支持多数据源、策略库与 ML 策略、自动化流程与本地部署。

**版本**: V3.2.0 | **更新日期**: 2026-01-30 | **状态**: 🟢 本地部署就绪 | 商业级加固中

---

## ✨ 关键能力

- **多数据源**: AKShare / YFinance / TuShare
- **策略库**: 趋势、均值回归、动量、组合优化、ML 策略
- **ML 策略族**: `ml_walk`, `ml_meta`, `ml_prob_band`, `ml_enhanced`, `ml_ensemble` + DL/RL/特征选择/集成示例
- **自动化流程**: `run` / `grid` / `auto` / `combo`
- **统一架构**: BaseStrategy + EventEngine + 统一接口层
- **实盘网关**: XtQuant / XTP / Hundsun UFT（SDK 可用时启用）
- **风险与归因**: VaR/ES、CAPM α/β、跟踪误差、风格暴露
- **执行建模**: 市场冲击滑点 + 成交概率/延迟模拟
- **合规与运维**: 审计日志、RBAC 权限隔离、快照恢复（HA/DR）
- **报告输出**: PNG / Markdown / JSON + 运行快照/数据质量报告；默认写入 `report/`（或 `--out_dir` 指定）

---

## 🚀 快速开始

### 安装

```bash
pip install -r requirements.txt
# 可选 ML 依赖
pip install xgboost torch
```

### 运行（CLI / GUI / 示例）

```bash
# CLI: 单策略回测
python unified_backtest_framework.py run \
  --strategy macd \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --plot

# GUI: 图形界面
python scripts/backtest_gui.py

# 示例: 快速上手
python examples/quick_start.py
```

---

## 🧭 CLI 常用命令

```bash
# 策略列表
python unified_backtest_framework.py list

# 生成真实历史样本回归基线
python unified_backtest_framework.py baseline --strategy macd \
  --params '{"fast": 12, "slow": 26, "signal": 9}' \
  --register-strategy-baseline --baseline-alias prod \
  --regimes bull bear range high-vol

# 生成策略准入报告（自动解析单策略基线并做漂移检查）
python unified_backtest_framework.py admission --strategy macd \
  --profile institutional \
  --baseline-alias prod \
  --regimes bull bear range high-vol

# 网格搜索
python unified_backtest_framework.py grid --strategy macd --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --grid '{"fast": [10,12,15], "slow": [26,30]}'

# 自动化流程 (多策略 + Pareto)
python unified_backtest_framework.py auto --symbols 600519.SH 000858.SZ \
  --start 2023-01-01 --end 2024-12-31 --workers 4

# 组合优化 (NAV 权重)
python unified_backtest_framework.py combo --navs report/ema_nav.csv report/macd_nav.csv \
  --objective sharpe --step 0.2 --out combo_nav.csv
```

- `run` 默认启用交易日历对齐与停牌填充（可用 `--calendar off` 关闭）。
- A 股数据源（`akshare` / `tushare`）会自动使用上交所真实交易日历做对齐和质量检查，不再把春节、国庆等休市日误判为缺失交易日。
- 回测输出目录会生成 `run_snapshot.json` 与 `data_quality.json/.md` 便于复现与审计。
- `baseline` / `admission` 会基于真实历史样本输出 JSON + Markdown 评审产物，支持按 `bull` / `bear` / `range` / `high-vol` 分层回归，并按策略族套用不同准入门槛。
- `baseline --register-strategy-baseline` 会把基线注册到 `report/strategy_baselines/<strategy>/<alias>/`；后续 `admission` 在未传 `--baseline-file` 时会自动解析该单策略基线。

---

## 🧪 示例代码

```bash
python examples/quick_start.py
python examples/batch_backtest.py
python examples/ml_strategy_gallery.py
python examples/ml_enhanced_examples.py
```

---

## ✅ 测试与质量

```bash
pytest tests/ -v
```

- `pytest.ini` 已启用 ML 模块覆盖率门槛（`--cov-fail-under=90`）
- 覆盖范围包含 `src/optimizer` 与 ML 策略模块

---

## 🗂️ 目录结构（概览）

```
stock/
├── src/                  # 核心模块
├── tests/                # 测试
├── examples/             # 示例
├── scripts/              # GUI/运维脚本
├── docs/                 # 文档
└── unified_backtest_framework.py  # CLI 入口
```

---

## 📚 文档索引

- `docs/ROADMAP.md` - 路线图/进度
- `CHANGELOG.md` - 版本记录
- `docs/QUICK_START_DEPLOYMENT.md` - 部署速览
- `docs/API_REFERENCE.md` - API 参考
- `docs/LIVE_TRADING_API.md` - 实盘接口说明
- `docs/STRATEGY_ADMISSION_WORKFLOW.md` - 历史样本回归基线与策略准入流程

---

## 🔐 配置提示

- 示例配置：`config.yaml.example`（复制为 `config.yaml` 修改）
- TuShare Token 使用环境变量：`TUSHARE_TOKEN`
- 缓存目录默认 `cache/`

---

## 🤝 贡献与规范

- 代码风格：PEP 8 + type hints
- 提交规范：Conventional Commits
- 每次优化需同步更新相关文档并记录到 `CHANGELOG.md`

---

**许可证**: MIT
