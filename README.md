# 量化回测系统 | Quantitative Backtesting Platform

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI Status](https://github.com/magic-alt/stock/workflows/CI/badge.svg)](https://github.com/magic-alt/stock/actions)
[![Code Coverage](https://codecov.io/gh/magic-alt/stock/branch/main/graph/badge.svg)](https://codecov.io/gh/magic-alt/stock)

> 企业级量化回测与实盘系统，基于 **Backtrader + Zipline 双引擎** 与事件驱动架构，支持多数据源、策略库与 ML 策略、自动化流程、商业网关接入与本地/容器化部署。

**版本**: V3.3.0 | **更新日期**: 2026-05-18 | **状态**: 🟢 本地/容器部署就绪 | 商业级加固持续推进 | V5.0 商业化规划中

---

## ✨ 关键能力

- **双回测引擎**: **Backtrader**（默认，事件驱动）+ **Zipline-Reloaded**（向量化，可选安装），统一 `EngineRegistry` 入口（CLI `--engine backtrader|zipline`）
- **多数据源**: AKShare / YFinance / TuShare（Qlib bundle 可选）
- **基本面工厂**: `FinancialDataProvider` ABC + `Null/Tushare/Akshare` 实现，通过 `get_financial_provider(name)` 切换
- **策略库**: 趋势、均值回归、动量、组合优化、ML 策略（共 40+）
- **ML 策略族**: `ml_walk`, `ml_meta`, `ml_prob_band`, `ml_enhanced`, `ml_ensemble` + DL/RL/特征选择/集成示例
- **自动化流程**: `run` / `grid` / `auto` / `combo` / `baseline` / `admission`
- **统一架构**: BaseStrategy + EventEngine + 统一接口层
- **实盘网关**: XtQuant / XTP / Hundsun UFT / EastMoney（easytrader），无 SDK 时自动进入 **Stub Mode** 便于 CI / 开发
- **订单状态机**: `OrderStateMachine` 严格/宽松双模式 + 有界审计历史（默认 1000 条）+ 非法转换审计
- **风险与归因**: VaR/ES、CAPM α/β、跟踪误差、风格暴露
- **执行建模**: 市场冲击滑点 + 成交概率/延迟模拟（A 股 T+1、涨跌停、整手）
- **合规与运维**: 审计哈希链、RBAC 权限隔离、快照恢复（HA/DR）、Prometheus `/metrics`
- **报告输出**: PNG / Markdown / JSON + ECharts 交互图 + 运行快照/数据质量报告；默认写入 `report/`（或 `--out_dir` 指定）
- **部署形态**: 本地 CLI / GUI、Docker、Docker-Compose、Kubernetes、Render（一键托管）

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
# CLI: 单策略回测（默认 backtrader 引擎）
python unified_backtest_framework.py run \
  --strategy macd \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --plot

# 使用 Zipline 向量化引擎（需 pip install zipline-reloaded）
python unified_backtest_framework.py run \
  --engine zipline \
  --strategy ma_cross \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31

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

# 平台控制台功能演示（隔离 Paper 网关）
python scripts/demo_platform_console.py --out report/platform_console_demo.json
```

---

## ✅ 测试与质量

```bash
pytest tests/ -v
```

- `pytest.ini` 已启用 ML 模块覆盖率门槛（`--cov-fail-under=90`）
- 覆盖范围包含 `src/optimizer` 与 ML 策略模块

### 本地 CI / CD

提交前请运行本地 CI 镜像 GitHub Actions：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local_ci.ps1 -Jobs test -SkipInstall
```

---

## 🔌 实盘网关接入

本平台内置 4 个商业网关 + 模拟撮合引擎，**所有网关无 SDK 时自动进入 Stub Mode**，便于开发 / CI / 教学。

| 网关 | 适用 | 状态 |
|------|------|------|
| **XtQuant / QMT** | 个人量化（券商免费） | ✅ 生产就绪 |
| **XTP** (中泰证券) | 私募 / 机构低延迟 | ✅ Vega 模拟 + 生产 |
| **Hundsun UFT** (恒生) | 持牌机构柜台 | ✅ 集成就绪 |
| **EastMoney** (easytrader) | 个人散户 / 教学 | ✅ 已接入 |
| **CTP** (期货) | 期货 / 期权 | 🟡 规划中 (V5.0) |

- 技术安装与配置：[docs/GATEWAY_SDK_SETUP.md](docs/GATEWAY_SDK_SETUP.md)
- **券商账户开通、商业 SDK 申请、合规要求**：[docs/BROKER_ACCOUNT_GUIDE.md](docs/BROKER_ACCOUNT_GUIDE.md)
- 实盘 API 速查：[docs/LIVE_TRADING_API.md](docs/LIVE_TRADING_API.md)

---

## 🚢 部署

| 形态 | 入口 |
|------|------|
| Docker 单机 | `docker build -t stock . && docker run ...` 见 [Dockerfile](Dockerfile) |
| Docker Compose（API + Web） | `docker-compose up -d` |
| Kubernetes | [deploy/k8s/](deploy/k8s/) Helm-friendly YAML |
| Render.com 一键托管 | [render.yaml](render.yaml) |
| 生产启动脚本 | `scripts/start_production.sh` / `.bat` / `.py` |

详细部署指南：[docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) · [docs/QUICK_START_DEPLOYMENT.md](docs/QUICK_START_DEPLOYMENT.md)

---

## 📚 文档地图

| 主题 | 文档 |
|------|------|
| 架构总览 | [docs/PLATFORM_GUIDE.md](docs/PLATFORM_GUIDE.md) · [docs/ARCHITECTURE_REVIEW.md](docs/ARCHITECTURE_REVIEW.md) |
| API 参考 | [docs/API_REFERENCE.md](docs/API_REFERENCE.md) |
| 策略参考（41 个策略） | [docs/STRATEGY_REFERENCE.md](docs/STRATEGY_REFERENCE.md) |
| 路线图 | [docs/ROADMAP.md](docs/ROADMAP.md) |
| 商业化升级路线 | [docs/COMMERCIAL_UPGRADE_ROADMAP.md](docs/COMMERCIAL_UPGRADE_ROADMAP.md) |
| 商业化差距评估 | [docs/COMMERCIAL_GAP_ASSESSMENT.md](docs/COMMERCIAL_GAP_ASSESSMENT.md) |
| 运维手册 | [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) · [docs/SRE_INCIDENT_RESPONSE.md](docs/SRE_INCIDENT_RESPONSE.md) |
| 安全基线 | [docs/SECURITY_BASELINE.md](docs/SECURITY_BASELINE.md) |
| 性能基准 | [docs/PERFORMANCE_BENCHMARK_SPEC.md](docs/PERFORMANCE_BENCHMARK_SPEC.md) |
| 网关接入 | [docs/GATEWAY_SDK_SETUP.md](docs/GATEWAY_SDK_SETUP.md) · [docs/BROKER_ACCOUNT_GUIDE.md](docs/BROKER_ACCOUNT_GUIDE.md) |

---

## 🤝 贡献

本仓库要求所有改动通过 **特性分支 + Pull Request** 流程（不允许直接推送 `main`）。
约定式提交（feat / fix / docs / test / chore）+ `CHANGELOG.md` 更新 + 本地 CI 通过
是合并前置条件。详见 [AGENTS.md](AGENTS.md)。

---

## 📝 许可

MIT License — 见 [LICENSE](LICENSE)。

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
- `docs/PLATFORM_CONSOLE_DEMO.md` - Web 控制台 Paper 交易演示流程

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
