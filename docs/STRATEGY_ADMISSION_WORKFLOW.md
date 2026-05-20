# 历史样本回归基线与策略准入

本文档说明如何用真实历史样本生成回归基线，并输出面向投研评审的策略准入报告。

## 目标

- 用固定样本窗口复跑策略，形成可比对的 `historical_baseline.json`
- 将当前结果与准入阈值、历史基线一起评估，生成 `strategy_admission.md`
- 把数据质量、收益风险、回归漂移放进同一套门禁
- 对 A 股样本使用上交所真实交易日历，避免把法定休市日误判为数据缺失
- 为每个策略维护自己的准入基线，不再依赖人工传入一次性 `--baseline-file`

## 默认历史样本

| sample_id | 标的 | 区间 | regime | 用途 |
|---|---|---|---|---|
| `cn_single_bear_q1_2024` | `600519.SH` | `2024-01-02` -> `2024-02-29` | `bear` | 单标的下跌窗口 |
| `cn_single_range_mid_2024` | `600519.SH` | `2024-03-01` -> `2024-08-30` | `range` | 单标的震荡窗口 |
| `cn_single_high_vol_q4_2024` | `600519.SH` | `2024-09-02` -> `2024-10-31` | `high-vol` | 单标的高波动窗口 |
| `cn_single_bull_q4_2024` | `601318.SH` | `2024-11-01` -> `2024-12-31` | `bull` | 单标的反弹窗口 |
| `cn_single_quality_2024` | `600519.SH` | `2024-01-02` -> `2024-12-31` | `mixed` | 单标的全年质量窗口 |
| `cn_single_financial_2024_2025` | `600036.SH` | `2024-01-02` -> `2025-10-14` | `mixed` | 单标的长窗口 |
| `cn_multi_bear_q1_2024` | `600519.SH`, `601318.SH`, `600036.SH` | `2024-01-02` -> `2024-02-29` | `bear` | 多标的下跌窗口 |
| `cn_multi_range_mid_2024` | `600519.SH`, `601318.SH`, `600036.SH` | `2024-03-01` -> `2024-08-30` | `range` | 多标的震荡窗口 |
| `cn_multi_high_vol_q4_2024` | `600519.SH`, `601318.SH`, `600036.SH` | `2024-09-02` -> `2024-10-31` | `high-vol` | 多标的高波动窗口 |
| `cn_multi_bull_q4_2024` | `600519.SH`, `601318.SH`, `600036.SH` | `2024-11-01` -> `2024-12-31` | `bull` | 多标的反弹窗口 |
| `cn_multi_leaders_2024_2025` | `600519.SH`, `601318.SH`, `600036.SH` | `2024-01-02` -> `2025-10-14` | `mixed` | 多标的长窗口 |

- 单标的策略默认只跑带 `single` 标签的样本
- 多标的策略默认只跑带 `multi` 标签的样本
- 显式指定 `--samples` 时，可以强制只跑选中的样本
- 可通过 `--regimes bull bear range high-vol` 只跑指定市场环境

## 生成回归基线

```bash
python unified_backtest_framework.py baseline \
  --strategy macd \
  --params '{"fast": 12, "slow": 26, "signal": 9}' \
  --register-strategy-baseline \
  --baseline-alias prod \
  --regimes bull bear range high-vol \
  --cache_dir ./cache
```

输出目录默认在 `report/<strategy>_baseline_<timestamp>/`，包含：

- `historical_baseline.json`
- `historical_baseline.md`

如果启用 `--register-strategy-baseline`，还会额外把基线写入：

- `report/strategy_baselines/<strategy>/<alias>/historical_baseline.json`
- `report/strategy_baselines/<strategy>/<alias>/historical_baseline.md`
- `report/strategy_baselines/<strategy>/<alias>/baseline_registry.json`

## 执行准入评估

```bash
python unified_backtest_framework.py admission \
  --strategy macd \
  --params '{"fast": 12, "slow": 26, "signal": 9}' \
  --profile institutional \
  --baseline-alias prod \
  --regimes bull bear range high-vol \
  --cache_dir ./cache
```

如果显式传了 `--baseline-file`，CLI 会优先使用该文件；否则会自动从 `report/strategy_baselines/<strategy>/<alias>/` 解析单策略基线。

## 强制门禁阶段

策略上线阶段现在按同一组参数签名强制推进：

- `research`
- `baseline_registered`
- `admission_passed`
- `paper_validated`
- `live_candidate`
- `production`

阶段状态保存在 `report/strategy_admission_gates/<strategy>/<params_signature>/gate_status.json`。

- 运行 `baseline` 只会记录 `research` 阶段；只有带 `--register-strategy-baseline` 才会推进到 `baseline_registered`。
- 运行 `admission` 只有在对应参数已完成 `baseline_registered` 且报告 `overall_status=PASS` 时，才会推进到 `admission_passed`。
- `scripts/start_production.py --mode paper` 和 paper preflight 会要求当前策略参数至少达到 `baseline_registered`，没有注册基线的策略不能进入仿真入口。
- paper preflight 可以在 `baseline_registered` 后运行，但只有策略已经达到 `admission_passed` 时，paper smoke 结果才会推进到 `paper_validated`。
- `unified_backtest_framework.py combo` 和 `/api/v2/portfolio/capital-allocation/preview` 会要求组合中的每个策略腿达到 `admission_passed`，未通过准入的策略不能进入组合或资金分配预览。
- `scripts/start_production.py --preflight --mode live` 会要求当前策略参数至少达到 `admission_passed`，并在 paper smoke 通过后推进到 `paper_validated`/`live_candidate`。
- 真正进入 live 启动前，`start_production.py` 会再次检查 `live_candidate`；启动成功后才会写入 `production`。

如果重新注册 baseline 或重新跑 admission，同一参数签名下的后续阶段会被回退到对应门禁点，要求重新完成后续验证。

## Live Preflight

```bash
python scripts/start_production.py \
  --mode live \
  --preflight \
  --preflight-strategy macd \
  --preflight-symbols 600519.SH
```

当 live preflight 需要复用非默认 gate 目录时，可追加：

```bash
python scripts/start_production.py --mode live --preflight --preflight-gate-root ./report/strategy_admission_gates
```

## Portfolio Admission Gate

组合优化需要显式声明每条 NAV 对应的策略与参数，CLI 会用同一参数签名检查 gate registry：

```bash
python unified_backtest_framework.py combo \
  --navs report/macd_nav.csv report/ema_nav.csv \
  --names macd-prod ema-prod \
  --strategies macd ema \
  --params-list '[{"fast": 12, "slow": 26, "signal": 9}, {"fast": 10, "slow": 30}]' \
  --gate-root ./report/strategy_admission_gates
```

API 资金分配预览同样检查 `admission_passed`，请求体中的 `strategy_params` 与 `strategy_weights` 使用相同的策略 key：

```json
{
  "strategy_weights": {"macd": 0.6, "ema": 0.4},
  "strategy_params": {
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "ema": {"fast": 10, "slow": 30}
  },
  "gate_root": "./report/strategy_admission_gates"
}
```

输出目录默认在 `report/<strategy>_admission_<timestamp>/`，包含：

- `current_historical_snapshot.json`
- `current_historical_snapshot.md`
- `strategy_admission.json`
- `strategy_admission.md`

## 准入档位

- `standard`: 研究准入门槛，适合策略开发与内部筛选
- `institutional`: 更严格的基金经理使用门槛，重点约束回撤、稳定性和回归漂移

同一个档位下，不同策略族会命中不同模板，不再共用一套统一阈值。当前内置策略族包括：

- `trend`
- `mean_reversion`
- `breakout`
- `portfolio`
- `futures`
- `machine_learning`

## 报告结构

`strategy_admission.md` 固定包含以下几部分：

- 总体结论：`PASS` / `WATCH` / `FAIL`
- 策略族与实际命中的准入模板
- 当前参数签名，以及基线来源/别名/参数匹配状态
- Regime 覆盖与 bull / bear / range / high-vol 汇总
- 汇总指标：平均 Sharpe、平均累计收益、最大回撤、总交易次数
- 单样本检查：收益风险指标、数据质量检查项
- 基线漂移：当前值、基线值、偏差、容许偏差

## 自定义样本文件

可通过 `--samples-file` 传入 YAML/JSON。示例：

```yaml
- sample_id: cn_single_quality_2024
  description: A-share single-name quality baseline window
  symbols: [600519.SH]
  start: 2024-01-02
  end: 2024-12-31
  source: akshare
  benchmark: 000300.SH
  benchmark_source: akshare
  calendar: fill
  tags: [single, cn, daily, real-history]
```

## 建议流程

1. 固定策略参数后先生成一次基线，并将 JSON 纳入版本管理或制品库
2. 每次调参、改撮合、改数据清洗后跑 `admission`
3. 仅 `PASS` 的策略进入下一阶段仿真、组合评审或上线审批
