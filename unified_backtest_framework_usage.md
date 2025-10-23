# Unified Backtest Framework - 完整使用指南# Unified Backtest Framework - 完整使用指南



**版本**: V2.5.1  **版本**: V2.5.1  

**更新日期**: 2025-01-XX  **更新日期**: 2025-01-XX  

**状态**: ✅ 生产就绪 (Production Ready)**状态**: ✅ 生产就绪



---本指南详细介绍如何使用 `unified_backtest_framework.py` 进行股票策略回测、参数优化和自动化分析。



## 📑 目录## 📑 目录



1. [快速开始](#1-快速开始)1. [快速开始](#1-快速开始)

2. [安装配置](#2-安装配置)2. [安装配置](#2-安装配置)

3. [数据源配置](#3-数据源配置)3. [数据源配置](#3-数据源配置)

4. [策略目录](#4-策略目录)4. [策略目录](#4-策略目录)

5. [命令行使用](#5-命令行使用)5. [命令行使用](#5-命令行使用)

6. [高级功能](#6-高级功能)6. [高级功能](#6-高级功能)

7. [扩展开发](#7-扩展开发)7. [扩展开发](#7-扩展开发)

8. [故障排除](#8-故障排除)8. [故障排除](#8-故障排除)

9. [最佳实践](#9-最佳实践)9. [最佳实践](#9-最佳实践)



------



## 1. 快速开始## 1. 快速开始



### 1.1 三行命令入门### 1.1 最简单的回测



```bash## 1. Prerequisites

# 1️⃣ 单策略回测 - 贵州茅台 2023年

python unified_backtest_framework.py single \- Python 3.9+

  --symbol 600519.SH --start 2023-01-01 --end 2023-12-31 \- Recommended virtual environment (e.g. `python -m venv .venv`)

  --strategy sma_cross --provider akshare- Core dependencies:

  ```bash

# 2️⃣ 参数优化 - 网格搜索  pip install backtrader pandas numpy matplotlib

python unified_backtest_framework.py grid \  ```

  --symbol 600519.SH --strategy sma_cross \- Optional data providers:

  --param-grid "fast_period=[5,10,20]" "slow_period=[30,50,60]"  - `pip install akshare` (default provider)

  - `pip install yfinance`

# 3️⃣ 自动化流程 - 多股票多策略 (推荐)  - `pip install tushare`

python unified_backtest_framework.py auto \

  --symbols 600519.SH 000333.SZ 600031.SH \> **Note**

  --strategies sma_cross macd_signal bollinger \> TuShare requires the `TUSHARE_TOKEN` environment variable. Obtain a token from the TuShare website and export it before running the script.

  --workers 4 --top-n 5

```## 2. Quick Start (akshare default)



### 1.2 5分钟完整演示```bash

python unified_backtest_framework.py run   --strategy turning_point   --symbols 600519.SH 000001.SZ   --start 2020-01-01   --end 2024-01-01   --benchmark 000300.SH   --out_dir reports_demo

```bash```

# 步骤1: 克隆或进入项目目录

cd e:\work\Project\stockThis command:

- Downloads daily prices for the provided symbols.

# 步骤2: 安装依赖 (首次运行)- Runs the turning-point strategy with default parameters.

pip install -r requirements.txt- Compares performance against the CSI 300 index.

- Writes NAV series and summary metrics to `reports_demo/`.

# 步骤3: 查看可用策略

python unified_backtest_framework.py list-strategies## 3. Selecting Data Providers



# 步骤4: 运行自动化流程| Provider  | Flag        | Requirements                           |

python unified_backtest_framework.py auto \|-----------|-------------|----------------------------------------|

  --symbols 600519.SH 000333.SZ 600036.SH 601318.SH \| Akshare   | `akshare`   | `pip install akshare`                   |

  --start 2022-01-01 --end 2025-01-01 \| yfinance  | `yfinance`  | `pip install yfinance`                  |

  --strategies sma_cross macd_signal triple_ma \| TuShare   | `tushare`   | `pip install tushare`, `TUSHARE_TOKEN` |

  --workers 4 --top-n 5 \

  --out-dir reports_demoSpecify providers via `--source` and optionally `--benchmark_source` if the benchmark should come from a different feed.



# 步骤5: 查看结果Example using yfinance:

# - reports_demo/pareto_front.png  (帕累托前沿图)```bash

# - reports_demo/rerun_*/          (前5名策略详细报告)python unified_backtest_framework.py run   --strategy ema   --symbols AAPL   --start 2018-01-01   --end 2023-12-31   --source yfinance   --benchmark ^GSPC   --benchmark_source yfinance

``````



### 1.3 预期输出示例## 4. Strategy Catalogue



```Run `python unified_backtest_framework.py list` to see available strategies. Out of the box the framework bundles:

📊 Loaded data for 4 symbols: ['600519.SH', '000333.SZ', '600036.SH', '601318.SH']

🔍 Testing strategies: sma_cross, macd_signal, triple_ma- `turning_point` — multi-symbol intent engine with Pareto analysis support.

⚙️  Running grid search with 4 workers...- `ema` — EMA cross-over (single asset).

✅ Completed 124 parameter evaluations in 26.4 seconds- `macd` — MACD signal line cross-over.

📈 Pareto front: 12 optimal configurations identified- `bollinger` — Bollinger band channel reversals.

🏆 Rerunning top 5 configurations with detailed plotting...- `rsi` — RSI threshold entries.

✅ Pipeline completed! Check reports_demo/

```Each strategy includes sensible defaults and a grid spec used for optimisation.



---## 5. Grid Search



## 2. 安装配置Run a parameter sweep via:

```bash

### 2.1 系统要求python unified_backtest_framework.py grid   --strategy macd   --symbols 600519.SH   --start 2019-01-01   --end 2024-01-01   --benchmark 000300.SH   --out_csv reports_macd/grid_results.csv   --workers 4

```

- **Python**: 3.9+ (推荐 3.10 或 3.11)

- **操作系统**: Windows, Linux, macOSPass a custom grid if required:

- **内存**: 最低 4GB RAM (多进程优化需要 8GB+)```bash

- **磁盘**: 500MB (包含数据缓存)python unified_backtest_framework.py grid   --strategy ema   --symbols 000001.SZ   --start 2021-01-01   --end 2024-01-01   --grid '{"period": [10, 20, 50, 100]}'

```

### 2.2 安装依赖

```bash

```bashpython unified_backtest_framework.py auto --symbols 600519.SH 000333.SZ 600036.SH 601318.SH 600276.SH 600104.SH 600031.SH 000651.SZ 000725.SZ 600887.SH --start 2022-01-01 --end 2025-01-01 --benchmark 000300.SS --strategies adx_trend macd triple_ma donchian zscore keltner bollinger rsi --hot_only --min_trades 1 --top_n 6 --workers 4 --use_benchmark_regime --regime_scope trend --out_dir reports_bulk_10

# 方式1: 使用 requirements.txt (推荐)```

pip install -r requirements.txt```bash

python unified_backtest_framework.py auto --symbols 600519.SH 000333.SZ 600036.SH 601318.SH 600276.SH 600104.SH 600031.SH 000651.SZ 000725.SZ 600887.SH 600000.SH 600030.SH 600016.SH 600703.SH 600690.SH 600660.SH 601988.SH 601939.SH 601888.SH 600438.SH --start 2022-01-01 --end 2025-01-01 --benchmark 000300.SS --strategies adx_trend macd triple_ma donchian zscore keltner bollinger rsi --hot_only --min_trades 1 --top_n 6 --workers 6 --use_benchmark_regime --regime_scope trend --out_dir reports_bulk_20

# 方式2: 手动安装核心依赖```

pip install backtrader pandas numpy matplotlib akshare## 6. Automated Pipeline



# 可选依赖 (根据需要安装)The `auto` sub-command performs:

pip install yfinance      # 全球市场数据1. Grid search for all selected strategies.

pip install tushare       # 中国市场高级接口 (需要token)2. CSV/PNG exports for each heatmap (if applicable).

pip install scipy         # 科学计算 (Pareto优化)3. Pareto frontier calculation.

```4. Top-N replays to generate comparative NAV plots.



### 2.3 数据源配置Example:

```bash

#### AKShare (默认, 无需配置)python unified_backtest_framework.py auto   --symbols 600519.SH 000333.SZ   --start 2018-01-01   --end 2024-01-01   --benchmark 000300.SS   --top_n 3   --out_dir reports_auto_demo \

  --workers 4

```bash```

# 无需额外配置, 开箱即用

python unified_backtest_framework.py single --symbol 600519.SH --provider akshareOutput structure under `reports_auto_demo/`:

```- `opt_<strategy>.csv` — Raw grid search metrics.

- `heat_<strategy>.png` — Visual heatmaps (strategy dependent).

#### TuShare (需要 Token)- `opt_all.csv` — Aggregated optimisation results.

- `pareto_front.csv` — Non-dominated configurations.

```bash- `topN_navs.csv` / `topN_navs.png` — Replay of the Pareto leaders.

# 1. 访问 https://tushare.pro/ 注册并获取 token

# 2. 设置环境变量## 7. Saving Results

export TUSHARE_TOKEN="your_token_here"  # Linux/Mac

set TUSHARE_TOKEN=your_token_here       # Windows CMD- `--out_dir` controls where NAV curves, comparisons, and the JSON console summary are written for `run`.

$env:TUSHARE_TOKEN="your_token_here"    # Windows PowerShell- `--out_csv` (grid) stores tabular results.

- `--cache_dir` defines where raw downloads are cached. Reuse the same folder to avoid repeated downloads.

# 3. 使用 TuShare

python unified_backtest_framework.py single --symbol 600519.SH --provider tushare## 8. Extending the Framework

```

1. **Create a Backtrader strategy** in `unified_backtest_framework.py` or an imported module.

#### YFinance (全球市场)2. **Provide a coercer** that cleans user parameters.

3. **Register a `StrategyModule`** in the `STRATEGY_REGISTRY` list with:

```bash   - Unique `name`

# 使用标准 Yahoo Finance 代码   - Description

python unified_backtest_framework.py single \   - Strategy class

  --symbol AAPL --provider yfinance \   - Default parameters and grid definition

  --start 2020-01-01 --end 2023-12-314. Optional: override `multi_symbol` or supply custom pre/post-processing.

```

New strategies automatically become available in the CLI once registered.

### 2.4 验证安装

## 9. Troubleshooting

```bash

# 测试脚本是否正常运行- Missing dependency errors indicate the provider’s package is not installed.

python unified_backtest_framework.py --version- Empty data frames usually mean the symbol is not supported by the provider (use provider-specific tickers).

- TuShare authentication problems are resolved by re-exporting `TUSHARE_TOKEN`.

# 测试数据加载 (不运行回测)- Use `--cache_dir` to isolate data per experiment and delete it for a clean re-download.

python unified_backtest_framework.py test-data \

  --symbol 600519.SH --provider akshare## 10. Further Ideas



# 运行内置测试 (如果存在)- Add new providers by subclassing `DataProvider` and updating `_PROVIDER_FACTORIES`.

python -m pytest test/- Wrap the engine in a higher-level API (e.g. FastAPI) for remote execution.

```- Integrate custom analyzers by extending `_execute_strategy`.



---Happy backtesting!



## 3. 数据源配置Tip: Use --workers to parallelise grid search/backtests (default 1).


### 3.1 数据源对比

| 提供商 | 适用市场 | 优点 | 缺点 | 配置难度 |
|--------|---------|------|------|---------|
| **AKShare** | 中国 A股/指数 | 免费, 无需注册 | 速度较慢, 有时限流 | ⭐ 简单 |
| **TuShare** | 中国 A股/指数 | 数据全面, 速度快 | 需要积分/付费 | ⭐⭐ 中等 |
| **YFinance** | 全球市场 | 全球覆盖, 稳定 | 中国市场数据少 | ⭐ 简单 |

### 3.2 符号格式规范

**重要**: V2.5.1 修复了 AKShare 符号格式问题, 现在统一使用标准格式:

| 市场 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 上交所 | `代码.SH` | `600519.SH` | 6位数字 + .SH |
| 深交所 | `代码.SZ` | `000333.SZ` | 6位数字 + .SZ |
| 指数 | `代码.SH/SS` | `000300.SH` | ⚠️ 部分数据源用 .SS |
| 美股 | `TICKER` | `AAPL` | YFinance 格式 |

**自动转换**: 框架内部会自动将 `600519.SH` 转换为 AKShare 需要的 `600519` 格式。

### 3.3 数据缓存机制

```bash
# 缓存位置: cache/
cache/
  ak_600519.SH_2023-01-01_2023-12-31_noadj.csv  # AKShare缓存
  yf_AAPL_2020-01-01_2023-12-31.csv            # YFinance缓存
  
# 清除缓存
rm -rf cache/    # Linux/Mac
rmdir /s cache   # Windows

# 强制重新下载 (忽略缓存)
python unified_backtest_framework.py single \
  --symbol 600519.SH --force-reload
```

### 3.4 基准指数配置

```bash
# 使用沪深300作为基准
--benchmark 000300.SH --benchmark-provider akshare

# 使用标普500作为基准
--benchmark ^GSPC --benchmark-provider yfinance

# 不使用基准 (仅计算绝对收益)
# 省略 --benchmark 参数即可
```

---

## 4. 策略目录

### 4.1 查看所有策略

```bash
# 列出所有可用策略
python unified_backtest_framework.py list-strategies

# 输出示例:
# Available strategies:
#   1. sma_cross       - 简单移动平均线交叉
#   2. ema_cross       - 指数移动平均线交叉
#   3. macd_signal     - MACD信号线策略
#   4. bollinger       - 布林带突破策略
#   5. rsi             - RSI超买超卖策略
#   6. adx_trend       - ADX趋势跟踪
#   7. donchian        - 唐奇安通道突破
#   8. triple_ma       - 三重移动平均线
#   9. zscore          - Z-Score均值回归
#  10. keltner         - Keltner通道策略
#  11. risk_parity     - 风险平价组合 (⚠️ 多资产)
```

### 4.2 内置策略详解

#### 4.2.1 SMA Cross (简单移动平均线交叉)

**原理**: 快线上穿慢线买入, 下穿卖出

```bash
# 默认参数: fast=10, slow=30
python unified_backtest_framework.py single \
  --symbol 600519.SH --strategy sma_cross

# 自定义参数
python unified_backtest_framework.py single \
  --symbol 600519.SH --strategy sma_cross \
  --params "fast_period=5" "slow_period=20"
```

**参数说明**:
- `fast_period`: 快线周期 (默认 10)
- `slow_period`: 慢线周期 (默认 30)
- 建议范围: fast=[5,20], slow=[20,60]

#### 4.2.2 MACD Signal (MACD信号线策略)

**原理**: MACD线上穿信号线买入, 下穿卖出

```bash
# 默认参数
python unified_backtest_framework.py single \
  --symbol 000333.SZ --strategy macd_signal

# 激进参数 (更频繁交易)
python unified_backtest_framework.py single \
  --symbol 000333.SZ --strategy macd_signal \
  --params "fast_period=8" "slow_period=17" "signal_period=6"
```

**参数说明**:
- `fast_period`: 快速EMA周期 (默认 12)
- `slow_period`: 慢速EMA周期 (默认 26)
- `signal_period`: 信号线周期 (默认 9)

#### 4.2.3 Bollinger Bands (布林带策略)

**原理**: 价格触及下轨买入, 触及上轨卖出

```bash
python unified_backtest_framework.py single \
  --symbol 600036.SH --strategy bollinger \
  --params "period=20" "devfactor=2.0"
```

**参数说明**:
- `period`: 移动平均线周期 (默认 20)
- `devfactor`: 标准差倍数 (默认 2.0)
- 适合震荡市, 趋势市慎用

#### 4.2.4 RSI (相对强弱指标策略)

**原理**: RSI < 30买入, RSI > 70卖出

```bash
python unified_backtest_framework.py single \
  --symbol 601318.SH --strategy rsi \
  --params "period=14" "oversold=30" "overbought=70"
```

**参数说明**:
- `period`: RSI计算周期 (默认 14)
- `oversold`: 超卖阈值 (默认 30)
- `overbought`: 超买阈值 (默认 70)

#### 4.2.5 Risk Parity (风险平价策略)

**原理**: 多资产组合, 根据波动率动态调整权重

```bash
# ⚠️ 需要多个股票
python unified_backtest_framework.py single \
  --symbols 600519.SH 000333.SZ 600036.SH 601318.SH \
  --strategy risk_parity \
  --params "rebalance_days=20" "lookback=60"
```

**参数说明**:
- `rebalance_days`: 再平衡频率 (默认 20天)
- `lookback`: 波动率计算窗口 (默认 60天)
- **注意**: 至少需要 3-4 只股票

### 4.3 策略选择建议

| 市场状态 | 推荐策略 | 不推荐 |
|---------|---------|--------|
| **趋势市** (单边行情) | `sma_cross`, `macd_signal`, `adx_trend` | `bollinger`, `zscore` |
| **震荡市** (横盘) | `bollinger`, `rsi`, `keltner` | `sma_cross`, `donchian` |
| **高波动** | `risk_parity`, `keltner` | `zscore`, `triple_ma` |
| **低波动** | `sma_cross`, `ema_cross` | `adx_trend` |

---

## 5. 命令行使用

### 5.1 命令结构

```bash
python unified_backtest_framework.py <MODE> [OPTIONS]
```

**可用模式**:
- `single` - 单次回测
- `grid` - 网格搜索优化
- `auto` - 自动化流程 (推荐)
- `list-strategies` - 列出策略
- `test-data` - 测试数据加载

### 5.2 Single 模式 (单次回测)

```bash
python unified_backtest_framework.py single \
  --symbol SYMBOL \                # 必选: 股票代码
  --strategy STRATEGY \            # 必选: 策略名称
  --start YYYY-MM-DD \             # 可选: 开始日期 (默认3年前)
  --end YYYY-MM-DD \               # 可选: 结束日期 (默认今天)
  --provider PROVIDER \            # 可选: 数据源 (默认akshare)
  --benchmark BENCHMARK \          # 可选: 基准指数
  --params "key=value" \           # 可选: 策略参数
  --cash 100000 \                  # 可选: 初始资金 (默认100000)
  --commission 0.0003 \            # 可选: 手续费率 (默认0.03%)
  --out-dir DIR                    # 可选: 输出目录 (默认reports/)
```

**完整示例**:

```bash
python unified_backtest_framework.py single \
  --symbol 600519.SH \
  --start 2020-01-01 --end 2023-12-31 \
  --strategy sma_cross \
  --params "fast_period=10" "slow_period=30" \
  --provider akshare \
  --benchmark 000300.SH \
  --cash 100000 \
  --commission 0.0003 \
  --out-dir reports_maotai
```

### 5.3 Grid 模式 (参数优化)

```bash
python unified_backtest_framework.py grid \
  --symbol SYMBOL \
  --strategy STRATEGY \
  --param-grid "param1=[v1,v2,...]" "param2=[v1,v2,...]" \
  --workers N \                    # 并行进程数
  --out-csv results.csv            # 输出CSV文件
```

**示例1: 优化双均线参数**

```bash
python unified_backtest_framework.py grid \
  --symbol 600519.SH \
  --strategy sma_cross \
  --param-grid "fast_period=[5,10,15,20]" "slow_period=[30,40,50,60]" \
  --workers 4 \
  --out-csv grid_results.csv
  
# 结果: 4×4=16 组参数, 约10秒完成
```

**示例2: 优化MACD参数**

```bash
python unified_backtest_framework.py grid \
  --symbol 000333.SZ \
  --strategy macd_signal \
  --param-grid "fast_period=[8,12,16]" "slow_period=[20,26,32]" "signal_period=[6,9,12]" \
  --workers 6 \
  --out-csv macd_grid.csv
  
# 结果: 3×3×3=27 组参数
```

**示例3: 优化RSI阈值**

```bash
python unified_backtest_framework.py grid \
  --symbol 601318.SH \
  --strategy rsi \
  --param-grid "oversold=[20,25,30,35]" "overbought=[65,70,75,80]" \
  --workers 4 \
  --out-csv rsi_grid.csv
  
# 结果: 4×4=16 组参数
```

### 5.4 Auto 模式 (自动化流程) ⭐ 推荐

**功能**: 多股票 × 多策略 × 参数优化 × Pareto分析 × 详细报告

```bash
python unified_backtest_framework.py auto \
  --symbols SYMBOL1 SYMBOL2 ... \  # 必选: 股票列表
  --strategies STRAT1 STRAT2 ... \ # 必选: 策略列表
  --start YYYY-MM-DD \
  --end YYYY-MM-DD \
  --workers N \                     # 并行进程数
  --top-n N \                       # 重跑前N名 (默认5)
  --out-dir DIR                     # 输出目录
```

**示例1: 小规模测试 (3股票 × 3策略)**

```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH \
  --strategies sma_cross macd_signal bollinger \
  --start 2022-01-01 --end 2025-01-01 \
  --workers 4 --top-n 5 \
  --out-dir reports_test3
```

**示例2: 中等规模 (10股票 × 8策略)** - V2.5.1 测试通过

```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600031.SH 000651.SZ 600036.SH \
            600276.SH 000725.SZ 600104.SH 600887.SH 601318.SH \
  --strategies sma_cross macd_signal triple_ma donchian \
               zscore keltner bollinger rsi \
  --start 2022-01-01 --end 2025-01-01 \
  --workers 4 --top-n 5 \
  --benchmark 000300.SH \
  --out-dir reports_bulk_10
  
# 预期时间: 约 25-30 秒
# 参数组合: 10 × 8 × 多参数 ≈ 120-150 组
```

**示例3: 大规模测试 (20股票 × 8策略)**

```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH 601318.SH 600276.SH \
            600104.SH 600031.SH 000651.SZ 000725.SZ 600887.SH \
            600000.SH 600030.SH 600016.SH 600703.SH 600690.SH \
            600660.SH 601988.SH 601939.SH 601888.SH 600438.SH \
  --strategies adx_trend macd triple_ma donchian \
               zscore keltner bollinger rsi \
  --start 2022-01-01 --end 2025-01-01 \
  --workers 6 --top-n 8 \
  --benchmark 000300.SH \
  --out-dir reports_bulk_20
  
# 预期时间: 约 60-90 秒
# 参数组合: 20 × 8 × 多参数 ≈ 300-500 组
```

### 5.5 输出结果解读

#### Single/Grid 模式输出

```
reports_maotai/
  summary.json          # 策略指标 (夏普率, 收益率, 最大回撤等)
  nav_series.csv        # 净值曲线数据
  trades.csv            # 交易记录
  backtest_plot.png     # 回测图表 (价格+指标+信号)
```

#### Auto 模式输出

```
reports_bulk_10/
  pareto_front.png                # 帕累托前沿图 (夏普率 vs 收益率)
  all_results.csv                 # 所有参数组合的结果
  grid_search_log.txt             # 详细日志
  
  rerun_rank_1_sma_cross_600519/ # 第1名详细报告
    summary.json
    nav_series.csv
    trades.csv
    backtest_plot.png
    
  rerun_rank_2_macd_000333/      # 第2名详细报告
    ...
    
  rerun_rank_3_bollinger_600036/ # 第3名详细报告
    ...
```

---

## 6. 高级功能

### 6.1 自定义参数网格

```bash
# 方式1: 命令行指定 (推荐小范围)
--param-grid "fast=[5,10,20]" "slow=[30,50]"

# 方式2: JSON文件 (推荐大范围)
# grid_config.json:
{
  "fast_period": [5, 10, 15, 20],
  "slow_period": [30, 40, 50, 60],
  "threshold": [0.01, 0.02, 0.05]
}

python unified_backtest_framework.py grid \
  --symbol 600519.SH --strategy sma_cross \
  --param-grid-file grid_config.json
```

### 6.2 多进程加速

```bash
# 根据CPU核心数选择
--workers 4   # 适合4核CPU
--workers 8   # 适合8核CPU
--workers 16  # 适合16核服务器

# 查看CPU核心数
# Windows: echo %NUMBER_OF_PROCESSORS%
# Linux/Mac: nproc 或 sysctl -n hw.ncpu

# 建议: workers = CPU核心数 - 1
```

### 6.3 Pareto 优化

Auto模式自动执行Pareto分析, 找出多目标最优解:

**优化目标**:
1. 最大化夏普率 (Sharpe Ratio)
2. 最大化总收益率 (Total Return)
3. 最小化最大回撤 (Max Drawdown)

**输出**: `pareto_front.png` 显示非支配解集合

### 6.4 基准对比

```bash
# 添加基准指数
--benchmark 000300.SH --benchmark-provider akshare

# 输出增加:
# - 超额收益 (Alpha)
# - 贝塔系数 (Beta)
# - 信息比率 (Information Ratio)
# - 跟踪误差 (Tracking Error)
```

### 6.5 风险管理参数

```bash
# 初始资金
--cash 1000000

# 手续费率 (双向)
--commission 0.0003    # 0.03% 买卖各收一次

# 滑点
--slippage 0.0001      # 0.01% 价格滑点

# 单笔最大仓位
--max-position 0.95    # 不超过95%资金

# 止损止盈
--params "stop_loss=0.05" "take_profit=0.20"  # 策略支持的话
```

---

## 7. 扩展开发

### 7.1 添加自定义策略

**步骤1**: 在 `src/strategies/` 创建策略文件

```python
# src/strategies/my_strategy.py
import backtrader as bt

class MyCustomStrategy(bt.Strategy):
    params = (
        ('param1', 10),
        ('param2', 30),
    )
    
    def __init__(self):
        self.signal = bt.indicators.CrossOver(
            bt.indicators.SMA(period=self.params.param1),
            bt.indicators.SMA(period=self.params.param2)
        )
    
    def next(self):
        if not self.position:
            if self.signal > 0:
                self.buy()
        elif self.signal < 0:
            self.sell()
```

**步骤2**: 在 `src/backtest/strategy_modules.py` 注册策略

```python
from src.strategies.my_strategy import MyCustomStrategy

MY_CUSTOM_MODULE = StrategyModule(
    name='my_custom',
    display_name='我的自定义策略',
    strategy_class=MyCustomStrategy,
    default_params={'param1': 10, 'param2': 30},
    param_grid={
        'param1': [5, 10, 15, 20],
        'param2': [20, 30, 40, 50],
    },
    description='自定义双均线策略'
)

STRATEGY_REGISTRY['my_custom'] = MY_CUSTOM_MODULE
```

**步骤3**: 使用新策略

```bash
python unified_backtest_framework.py single \
  --symbol 600519.SH --strategy my_custom
```

### 7.2 添加自定义数据源

**步骤1**: 在 `src/data_sources/providers.py` 创建 Provider 类

```python
class MyDataProvider(BaseDataProvider):
    def load_stock_daily(self, symbol, start_date, end_date, adjust=''):
        # 1. 调用你的API获取数据
        raw_df = my_api.get_data(symbol, start_date, end_date)
        
        # 2. 标准化为OHLCV格式
        df = self._standardize_stock_frame(raw_df)
        
        return df
    
    def load_index_daily(self, symbol, start_date, end_date):
        # 类似实现
        pass
```

**步骤2**: 在 `DataManager` 注册

```python
# data_manager.py
PROVIDERS = {
    'akshare': AkshareProvider,
    'yfinance': YfinanceProvider,
    'tushare': TushareProvider,
    'mydata': MyDataProvider,  # ← 新增
}
```

**步骤3**: 使用新数据源

```bash
python unified_backtest_framework.py single \
  --symbol 600519.SH --provider mydata
```

### 7.3 自定义指标

```python
# src/indicators/my_indicator.py
import backtrader as bt

class MyCustomIndicator(bt.Indicator):
    lines = ('signal',)
    params = (('period', 14),)
    
    def __init__(self):
        self.addminperiod(self.params.period)
    
    def next(self):
        # 计算指标值
        self.lines.signal[0] = ...  # 你的逻辑
```

---

## 8. 故障排除

### 8.1 常见错误及解决方案

#### 错误1: `StopIteration` (V2.5.1 已修复)

```
StopIteration: next(iter(sorted(data_map.keys())))
```

**原因**: 数据加载失败导致 `data_map` 为空

**解决**:
1. 检查符号格式是否正确 (600519.SH 而非 600519)
2. 检查日期范围是否合理
3. 检查网络连接 (数据源API可达)
4. 升级到 V2.5.1+ (已内置空数据检查)

```bash
# 测试数据加载
python unified_backtest_framework.py test-data --symbol 600519.SH
```

#### 错误2: 时区不匹配 (V2.5.1 已修复)

```
TypeError: Cannot join tz-naive with tz-aware DatetimeIndex
```

**原因**: 不同数据源返回的时间索引时区不一致

**解决**: 升级到 V2.5.1+ (已统一为 tz-naive)

#### 错误3: AKShare 数据为空 (V2.5.1 已修复)

```
WARNING: AKShare returned empty DataFrame for 600519.SH
```

**原因**: 旧版本直接传 `600519.SH` 给 AKShare API (需要 `600519`)

**解决**: 升级到 V2.5.1+ (已自动转换符号格式)

#### 错误4: 策略未找到

```
KeyError: 'my_strategy'
```

**解决**:
```bash
# 查看可用策略
python unified_backtest_framework.py list-strategies

# 检查拼写是否正确
--strategy sma_cross  # ✓ 正确
--strategy SMA_Cross  # ✗ 错误 (大小写敏感)
```

#### 错误5: TuShare Token 未设置

```
Exception: TuShare requires TUSHARE_TOKEN environment variable
```

**解决**:
```bash
# Windows PowerShell
$env:TUSHARE_TOKEN="your_token_here"

# Windows CMD
set TUSHARE_TOKEN=your_token_here

# Linux/Mac
export TUSHARE_TOKEN="your_token_here"
```

### 8.2 性能优化

#### 数据加载慢

```bash
# 1. 使用缓存 (默认启用)
# 缓存位置: cache/

# 2. 减少日期范围
--start 2023-01-01 --end 2023-12-31  # 1年数据

# 3. 切换更快的数据源
--provider tushare  # 比 akshare 快
```

#### 网格搜索慢

```bash
# 1. 增加并行进程
--workers 8  # 根据CPU核心数调整

# 2. 减少参数空间
--param-grid "fast=[10,20]" "slow=[30,60]"  # 2×2=4组
# 而非 "fast=[5,10,15,20]" "slow=[30,40,50,60]"  # 4×4=16组

# 3. 使用更小的股票池
--symbols 600519.SH 000333.SZ  # 2只股票
# 而非 10-20 只
```

### 8.3 调试技巧

```bash
# 1. 启用详细日志
python unified_backtest_framework.py single \
  --symbol 600519.SH --strategy sma_cross \
  --verbose

# 2. 单步运行 (先测数据, 再测策略)
# 步骤1: 测试数据加载
python unified_backtest_framework.py test-data --symbol 600519.SH

# 步骤2: 测试单策略
python unified_backtest_framework.py single --symbol 600519.SH --strategy sma_cross

# 步骤3: 测试网格搜索 (小范围)
python unified_backtest_framework.py grid --symbol 600519.SH --strategy sma_cross \
  --param-grid "fast=[10,20]" "slow=[30,60]"

# 3. 检查数据质量
python -c "
import pandas as pd
df = pd.read_csv('cache/ak_600519.SH_2023-01-01_2023-12-31_noadj.csv')
print(df.info())
print(df.head())
print(df.isnull().sum())
"
```

---

## 9. 最佳实践

### 9.1 开发工作流

```bash
# 阶段1: 快速验证 (单股票单策略)
python unified_backtest_framework.py single \
  --symbol 600519.SH --strategy sma_cross

# 阶段2: 参数优化 (小范围网格搜索)
python unified_backtest_framework.py grid \
  --symbol 600519.SH --strategy sma_cross \
  --param-grid "fast=[10,20]" "slow=[30,60]"

# 阶段3: 扩展测试 (3-5只股票)
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH \
  --strategies sma_cross macd_signal \
  --workers 4 --top-n 3

# 阶段4: 生产级测试 (10-20只股票)
python unified_backtest_framework.py auto \
  --symbols [完整股票列表] \
  --strategies [完整策略列表] \
  --workers 6 --top-n 5
```

### 9.2 参数调优建议

| 策略 | 保守参数 | 中性参数 | 激进参数 |
|------|---------|---------|---------|
| **SMA Cross** | fast=20, slow=60 | fast=10, slow=30 | fast=5, slow=20 |
| **MACD** | (12,26,9) | (12,26,9) | (8,17,6) |
| **RSI** | (14,25,75) | (14,30,70) | (7,20,80) |
| **Bollinger** | (20,2.5) | (20,2.0) | (10,1.5) |

### 9.3 风险控制

```bash
# 1. 设置合理的初始资金
--cash 100000  # 10万元, 适合回测

# 2. 考虑真实交易成本
--commission 0.0005  # 0.05% (买卖各收一次 = 0.1%)

# 3. 限制单笔仓位
--max-position 0.80  # 最多80%资金

# 4. 分散投资
--symbols [至少5-10只股票]  # 降低个股风险

# 5. 多策略组合
--strategies sma_cross macd_signal bollinger  # 不同类型策略
```

### 9.4 性能基准

| 指标 | 优秀 | 良好 | 一般 | 较差 |
|------|------|------|------|------|
| **夏普率** | > 2.0 | 1.0-2.0 | 0.5-1.0 | < 0.5 |
| **年化收益** | > 30% | 15-30% | 5-15% | < 5% |
| **最大回撤** | < 10% | 10-20% | 20-30% | > 30% |
| **胜率** | > 60% | 50-60% | 40-50% | < 40% |

### 9.5 文件组织

```
项目目录/
  unified_backtest_framework.py  # 主入口
  src/                           # 源代码
  cache/                         # 数据缓存
  reports_production/            # 生产环境报告
  reports_testing/               # 测试报告
  reports_archive/               # 历史报告归档
  configs/                       # 配置文件
    production.json              # 生产环境配置
    testing.json                 # 测试环境配置
```

---

## 附录

### A. 完整参数列表

```bash
# 全局参数
--cash FLOAT              # 初始资金 (默认 100000)
--commission FLOAT        # 手续费率 (默认 0.0003)
--slippage FLOAT          # 滑点 (默认 0)
--out-dir PATH            # 输出目录 (默认 reports/)
--verbose                 # 详细日志

# 数据参数
--symbol SYMBOL           # 股票代码 (单个)
--symbols SYMBOL [...]    # 股票代码 (多个)
--start DATE              # 开始日期 (YYYY-MM-DD)
--end DATE                # 结束日期 (YYYY-MM-DD)
--provider PROVIDER       # 数据源 (akshare/yfinance/tushare)
--benchmark SYMBOL        # 基准指数
--benchmark-provider      # 基准数据源

# 策略参数
--strategy STRATEGY       # 策略名称
--strategies STRAT [...]  # 策略列表 (多个)
--params "key=value" [...] # 策略参数
--param-grid "key=[...]"  # 参数网格

# 优化参数
--workers INT             # 并行进程数
--top-n INT               # Auto模式重跑前N名 (默认 5)
```

### B. 常用命令速查

```bash
# 列出策略
python unified_backtest_framework.py list-strategies

# 测试数据
python unified_backtest_framework.py test-data --symbol 600519.SH

# 快速回测
python unified_backtest_framework.py single --symbol 600519.SH --strategy sma_cross

# 参数优化
python unified_backtest_framework.py grid --symbol 600519.SH --strategy sma_cross \
  --param-grid "fast=[5,10,20]" "slow=[30,50]"

# 自动化流程
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH \
  --strategies sma_cross macd_signal bollinger \
  --workers 4 --top-n 5
```

### C. 更新记录

**V2.5.1** (2025-01-XX)
- 🐛 修复 `StopIteration` 错误 (空数据验证)
- 🐛 修复 AKShare 符号格式问题 (自动转换)
- 🐛 修复时区不匹配错误 (统一 tz-naive)
- ✅ 完整测试通过 (10股票 × 8策略)

**V2.5.0** (2024-XX-XX)
- ✅ Phase 2 模块化完成
- 🚀 新增 `risk_parity` 策略
- 📊 增强可视化系统

**V2.4.0** (2024-XX-XX)
- ✅ Phase 1 模块化完成
- 🔧 统一数据接口

---

## 获取帮助

- **GitHub Issues**: [项目地址]/issues
- **文档**: 查看 `docs/` 目录
- **示例**: 查看 `test/` 目录

---

**最后更新**: 2025-01-XX | **版本**: V2.5.1 | **状态**: ✅ 生产就绪
