# 项目路线图 | Project Roadmap

**项目**: 量化回测与实盘系统（Unified Quant Platform）  
**当前版本**: V3.2.0  
**更新日期**: 2026-01-31  
**状态**: 🟢 本地部署就绪 | 商业级加固中

---

## 1) 架构总览（基于当前 `src/` 实现）

```
┌───────────────────────────────────────────────────────────────┐
│ Presentation Layer                                             │
│  CLI / GUI / Examples                                          │
├───────────────────────────────────────────────────────────────┤
│ Application Layer                                              │
│  BacktestEngine • Auto Pipeline • StrategyRegistry             │
│  OrderManager • RiskManagerV2 • TradingGateway                 │
├───────────────────────────────────────────────────────────────┤
│ Domain Layer                                                   │
│  BaseStrategy • StrategyContext • EventEngine • Data Models    │
├───────────────────────────────────────────────────────────────┤
│ Infrastructure Layer                                           │
│  Data Providers • SQLite Cache • MatchingEngine                │
│  Live Gateways (XtQuant/XTP/UFT) • Monitoring • Logging         │
└───────────────────────────────────────────────────────────────┘
```

**核心链路**:
- **回测**: Data Provider → BacktestEngine → Backtrader Strategy → 绩效/报告
- **模拟交易**: BaseStrategy → EventEngineContext → PaperGatewayV3 → MatchingEngine
- **实盘对接**: TradingGateway / LiveGateways → 订单/成交/资金/持仓事件

---

## 2) 当前功能实现（按模块归类）

### 数据与存储
- ✅ 多数据源：AKShare / YFinance / TuShare
- ✅ 数据标准化与缓存：SQLite + cache 目录
- ✅ 基准指数 NAV 计算与回退
- 🟡 公司行动/复权一致性校验（基础支持，需完善）

### 回测与分析
- ✅ 单策略回测 / 多策略批量 / 网格搜索 / 自动化流程
- ✅ 组合优化（NAV 权重）
- ✅ 回测报告与图表：Markdown / JSON / PNG
- ✅ 滑点与手续费插件（CN 规则）
- 🟡 市场冲击模型、成交概率模型（需完善）

### 交易与执行
- ✅ MatchingEngine（限价/市价/止损）
- ✅ PaperGatewayV3（模拟撮合）
- ✅ TradingGateway 统一接口
- ✅ Live Gateways: XtQuant / XTP / Hundsun UFT（SDK 可用时）
- 🟡 交易日历、撮合延迟/排队模型（需完善）

### 风控与订单管理
- ✅ OrderManager 订单生命周期
- ✅ RiskManagerV2：订单/仓位/回撤/日亏损/自动止损
- ✅ 事件驱动风控输出
- 🟡 组合层风险指标（VaR/ES/行业暴露）

### 事件、监控与运维
- ✅ EventEngine + 统一事件类型
- ✅ 监控：SystemMonitor + 心跳检测 + 自动重启
- ✅ 结构化日志（structlog）
- ✅ 全局异常处理与错误统计
- ✅ 健康检查 / 备份脚本

### 策略与 ML
- ✅ 技术指标策略库（趋势、均值回归、多因子、期货等）
- ✅ ML 策略：`ml_walk`, `ml_meta`, `ml_prob_band`, `ml_enhanced`, `ml_ensemble`
- ✅ DL/RL/特征选择/集成的示例策略
- 🟡 MLOps（模型版本/训练可追溯）

### GUI / CLI / Examples
- ✅ CLI：`run/grid/auto/combo/list`
- ✅ GUI：tkinter GUI（已优化响应速度）
- ✅ 示例：`quick_start`, `batch_backtest`, `ml_strategy_gallery`, `ml_enhanced_examples`

---

## 3) 商业级 / 基金级能力对照（真实实现状态）

### ✅ 已具备（核心框架可支撑基金级回测）
- 统一策略接口与事件驱动架构
- 多数据源与缓存
- 多策略批量回测 + 参数优化
- 订单/风控/撮合模块
- 可视化报告输出
- 实盘网关接口层（A 股三类主流柜台）

### 🟡 需要补齐的基金级能力
- 投资组合级风险指标（VaR/ES/行业暴露/集中度）
- 市场冲击模型 + 成交概率模型
- 交易日历 / 停复牌 / 价格带规则
- 数据质量与版本控制（数据血缘、校验、锁定）
- 回测可复现性（配置快照 + 数据快照 + 依赖锁定）
- 回测/实盘一致性校验与对账

### 🔴 尚未实现（基金级“生产化”必要项）
- 多账户/多策略隔离与权限
- 审计日志与合规模块（操作留痕）
- 灾备/高可用（多实例、主备切换）
- Web API / 任务编排 / 分布式回测

---

## 4) 当前进度（高优先级清单）

- [x] 添加更多 ML 策略示例
- [x] 提升测试覆盖率到 90%+（ML 模块门槛）
- [x] 优化 GUI 界面响应速度
- [x] 增加 Heartbeat 事件
- [x] 实现自动重启监控
- [ ] 完善英文文档

---

## 5) 下一步技术路线（面向基金级生产能力）

### Phase 3.2.1（1-2 周）稳定化
- [x] 统一运行配置快照（参数/版本/数据快照）
- [x] 数据质量校验与报告（缺失/异常/复权一致性）
- [x] 交易日历/停牌处理增强
- [x] 回测结果复现命令与报告签名

### Phase 3.3（1-2 月）风控与交易建模升级
- [x] 组合级风险指标（VaR/ES/行业暴露/集中度）
- [x] 市场冲击模型 + 成交概率模型
- [x] 执行延迟与排队撮合
- [x] 绩效归因与风格暴露

### Phase 3.4（2-3 月）生产化与合规
- [x] 审计日志 + 权限与账户隔离
- [x] 数据血缘与合规模块
- [x] 高可用部署（服务化、主备、监控告警）
- [x] 灾备与回放机制

### Phase 3.5（1-2 月）AI 框架接入与 MLOps
- [x] 许可证与合规评估（MIT/Apache 优先，GPL/AGPL 隔离方案）
- [x] 框架选型与 PoC：FinRL / Qlib（研究与训练）接口与示例打通
- [x] 统一数据/特征适配器（对齐 OHLCV、复权、交易日历、缺失处理）
- [x] 统一信号协议 `SignalSchema` 与策略包装器（BaseStrategy 兼容）
- [x] 模型注册与版本管理（模型签名、训练配置快照、数据血缘）
- [x] 推理服务化（本地推理 + 延迟/吞吐基准）
- [x] 回测/实盘一致性验证（结果对比 + 漂移检测）
- [x] 安全与风控隔离（模型仅输出意图，最终下单走 RiskManagerV2）
- [x] 文档与示例：`docs/AI_FRAMEWORK_INTEGRATION.md` + 端到端样例流程

### Phase 4（长期）平台化
- [x] Web API / 作业编排 / 任务队列
- [x] Docker/K8s 容器化
- [x] 分布式回测与数据湖

---

## 6) 功能规范（当前统一标准）

- **策略接口**: BaseStrategy / StrategyContext 统一
- **事件驱动**: EventEngine 作为消息中枢
- **风险控制**: RiskManagerV2 为订单/持仓/账户风控入口
- **日志与异常**: 统一日志 + 全局异常处理
- **测试规范**: pytest + 覆盖率门槛（ML 模块 ≥ 90%）

---

## 7) 说明

- 路线图以 **代码实现** 为准，优先记录现有能力与缺口
- 如需落地基金级生产化能力，建议优先完成 **风控、数据治理、审计、回测复现** 四类能力

---

**维护者**: magic-alt  
**许可证**: MIT
