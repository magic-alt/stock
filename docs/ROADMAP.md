# 项目路线图 | Project Roadmap

**项目**: 量化回测与实盘系统（Unified Quant Platform）
**当前版本**: V3.2.0（Phase 3.x 完成）
**更新日期**: 2026-02-28
**状态**: 🟢 生产可用 | 商业化升级 P0-P5 大部分完成 | V4.0 技术路线规划中

---

## 1) 架构总览（基于当前 `src/` 实现）

```
┌───────────────────────────────────────────────────────────────┐
│ Presentation Layer                                             │
│  CLI / GUI / Examples / Platform API                           │
├───────────────────────────────────────────────────────────────┤
│ Application Layer                                              │
│  BacktestEngine • Auto/Pipeline • StrategyRegistry             │
│  PaperRunnerV3 • TradingGateway • Orchestrator                 │
├───────────────────────────────────────────────────────────────┤
│ Domain Layer                                                   │
│  BaseStrategy • StrategyContext • EventEngine                  │
│  RiskManagerV2 • OrderManager • Performance/Attribution         │
├───────────────────────────────────────────────────────────────┤
│ Infrastructure Layer                                           │
│  Data Providers • SQLite/Cache • MatchingEngine                │
│  Slippage/Fill/Delay Models • RealtimeData                     │
│  Live Gateways (XtQuant/XTP/UFT)                               │
├───────────────────────────────────────────────────────────────┤
│ Platform & Ops                                                 │
│  JobQueue • DataLake • API Server • Monitoring                 │
│  Audit/RBAC • HA Snapshot • Repro Snapshot • Logging           │
└───────────────────────────────────────────────────────────────┘
```

**核心链路**:
- **回测**: Data Provider/SQLite → BacktestEngine → Strategy → 归因/报告 + Repro Snapshot
- **模拟交易**: BaseStrategy → EventEngineContext → PaperGatewayV3 → MatchingEngine → OMS/Risk
- **实盘对接**: Strategy → TradingGateway → Live Gateways → OMS/Risk/Audit
- **平台任务**: API → JobQueue/Orchestrator → BacktestTask → DataLake/Report
- **MLOps**: Adapter → Training/Registry → Inference → SignalSchema → Strategy

---

## 2) 当前功能实现（按模块归类）

### 数据与存储
- ✅ 多数据源：AKShare / YFinance / TuShare
- ✅ 数据标准化与缓存：SQLite + cache 目录
- ✅ DataPortal 统一访问 + DataLake 清单注册
- ✅ 交易日历对齐 / 停复牌填充
- ✅ 数据质量报告 + 数据血缘记录（lineage）
- ✅ 基准指数 NAV 计算与回退
- 🟡 数据版本锁定/快照化（数据湖分区/校验门禁）
- 🟡 统一列式存储（Parquet）与冷热分层

### 回测与分析
- ✅ 单策略回测 / 多策略批量 / 网格搜索 / 自动化流程
- ✅ 组合优化（NAV 权重）
- ✅ 回测报告与图表：Markdown / JSON / PNG + Top-N 重放
- ✅ 绩效归因与风格暴露：VaR/ES/Tracking/Concentration/Sector
- ✅ 复现快照与报告签名（repro snapshot）
- ✅ 滑点与手续费插件（CN 规则）
- ✅ 市场冲击/成交概率/延迟模型（execution_models）
- 🟡 回测性能提升（向量化/并行/缓存复用）

### 交易与执行
- ✅ MatchingEngine（限价/市价/止损/订单簿）
- ✅ PaperGatewayV3 + PaperRunnerV3（事件驱动）
- ✅ Execution models：滑点/成交概率/延迟
- ✅ TradingGateway 统一接口（含模拟交易）
- ✅ Live Gateways: XtQuant / XTP / Hundsun UFT（SDK 依赖）
- 🟡 TradingGateway 与 RiskManagerV2 前置风控整合（TODO）
- 🟡 RealtimeData Providers 实接入（Sina/Eastmoney/Tencent）

### 风控与订单管理
- ✅ OrderManager 订单生命周期
- ✅ RiskManagerV2：订单/仓位/回撤/日亏损/自动止损
- ✅ 审计日志（Hash Chain）+ RBAC/租户隔离
- ✅ Snapshot/Restore（OMS）
- ✅ 事件驱动风控输出
- 🟡 组合级/多账户风险聚合与资金分配
- 🟡 实盘/回测一致性自动对账

### 事件、监控与运维
- ✅ EventEngine + 统一事件类型
- ✅ 监控：SystemMonitor + 心跳检测 + 自动重启
- ✅ 结构化日志（structlog）
- ✅ 全局异常处理与错误统计
- ✅ 健康检查 / 备份脚本
- 🟡 指标导出（Prometheus/OTel）与告警联动
- 🟡 日志集中化与 Trace

### 策略与 ML / MLOps
- ✅ 技术指标策略库（趋势、均值回归、多因子、期货等）
- ✅ ML 策略：`ml_walk`, `ml_meta`, `ml_prob_band`, `ml_enhanced`, `ml_ensemble`
- ✅ DL/RL/特征选择/集成的示例策略
- ✅ Qlib / FinRL 适配器 + SignalSchema + 策略包装
- ✅ Model Registry + Training/Inference + Drift 校验
- 🟡 实验追踪与模型部署流水线
- 🟡 在线推理服务弹性与批量推理

### 平台 / API / 分布式
- ✅ JobQueue / Orchestrator / Distributed（本地线程/进程）
- ✅ Minimal API Server（HTTP）+ 版本化 `/api/v1/*` 路由
- ✅ DataLake（manifest）
- ✅ API Bearer Token 鉴权 + `request_id` 透传 + 审计注入
- ✅ SQLite JobStore（幂等提交、事务恢复）+ 队列分位指标
- ✅ 工作流超时/重试/失败策略
- ✅ `/readyz` 健康探针 + `/metrics`（JSON + Prometheus）指标端点
- 🟡 任务编排 DAG、持久队列与多租户（Redis/Postgres backend）

### GUI / CLI / Examples
- ✅ CLI：`run/grid/auto/combo/list`
- ✅ GUI：tkinter GUI（已优化响应速度）
- ✅ 示例：`quick_start`, `batch_backtest`, `ml_strategy_gallery`, `ml_enhanced_examples`

---

## 3) 商业级 / 基金级能力对照（真实实现状态）

### ✅ 已具备（核心框架可支撑基金级回测）
- 统一策略接口与事件驱动架构
- 多数据源与缓存
- DataPortal + SQLite 数据库
- 数据质量 + 交易日历对齐 + 数据血缘
- 多策略批量回测 + 参数优化 + 复现快照
- 订单/风控/撮合模块 + 审计/RBAC
- 可视化报告输出
- 实盘网关接口层（XTP/XtQuant/UFT，SDK 依赖）
- 平台化 MVP（API/JobQueue/Distributed）

### 🟡 需要补齐的基金级能力
- 统一交易链路（TradingGateway/PaperGateway/LiveGateways）与前置风控
- 实时报价与行情接入（Sina/Eastmoney/Tencent/Level2）
- 数据湖版本化、列式存储与质量门禁
- 分布式调度与可扩展队列（非本地）
- 可观测性体系（metrics/tracing/alert）
- 多账户/组合级风控与资金分配

### 🔴 尚未实现（基金级“生产化”必要项）
- 服务化 API 的权限/审计/隔离完备实现
- 高可用集群与自动故障切换（多节点）
- 统一清算/对账/回放体系
- 合规与审计存证（长期不可篡改存储）

---

## 4) 当前进度（高优先级清单）

- [x] 添加更多 ML 策略示例
- [x] 提升测试覆盖率到 90%+（ML 模块门槛）
- [x] 优化 GUI 界面响应速度
- [x] 增加 Heartbeat 事件
- [x] 实现自动重启监控
- [x] 完善英文文档
- [x] **P0** API 版本化（`/api/v1/*`）+ Bearer Token 鉴权 + 统一响应信封
- [x] **P0** `/readyz` 健康探针 + `/metrics`（JSON + Prometheus）双格式
- [x] **P0** JobQueue 任务取消（pending 状态）+ 契约测试
- [x] **P1** SQLite JobStore（幂等提交、事务恢复）+ 队列分位指标（P50/P95/P99）
- [x] **P1** 工作流超时/重试/失败策略（abort/continue）
- [x] **P1** 压测脚本（`benchmark_platform.py`）+ 阈值代码化断言 + 回归基线检测
- [x] **P2** 审计哈希链 + 关键动作覆盖 + 完整性巡检脚本
- [x] **P2** 订单状态机一致性测试 + 风控一致性测试（跨三种模式）
- [x] **P2** 运维文档（`OPERATIONS_RUNBOOK.md` / `SRE_INCIDENT_RESPONSE.md`）
- [x] **P3** 网关异步查询结果缓存（`QueryResultCache`）+ SDK 路径动态配置
- [x] **P3** 实盘运行器加固（错误恢复/仓位校验/审计日志）
- [x] **P3** 仿真 A 股规则（T+1/涨跌停/整手）+ 告警外发（邮件/企业微信/钉钉）
- [x] **P3** 网关 Mock SDK 测试（`test_gateway_mock_sdk.py`）+ SDK 安装文档
- [x] **P4** 基本面因子模块（7 因子）+ 跨因子相关性分析
- [x] **P4** ECharts K 线图可视化（暗色主题 + 成交量 + 缩放）+ `/api/v1/chart-data`
- [x] **P4** L1/L2 冷热缓存（`TieredCache`）+ QLib Provider 错误处理改进
- [x] **P5** 负载测试（`test_load.py`）+ 故障场景测试（`test_fault_scenarios.py`）+ E2E 测试
- [x] **P5** CI 性能回归门禁（`performance` job，基线缓存 + 阈值断言 + 回归检测）
- [x] **P5** 策略参考文档（41 个策略，`docs/STRATEGY_REFERENCE.md`）

---

## 5) 下一步技术路线（面向 V4.0）

### 历史阶段（已完成）
- [x] Phase 3.2.1 稳定化（配置快照 / 数据质量 / 交易日历 / 复现签名）
- [x] Phase 3.3 风控与交易建模升级（VaR/ES/归因/冲击/延迟）
- [x] Phase 3.4 生产化与合规（审计/RBAC/血缘/灾备）
- [x] Phase 3.5 AI 框架接入与 MLOps（Qlib/FinRL/Registry/Inference）
- [x] Phase 4 MVP 平台化（API/作业编排/分布式/数据湖）

### V4.0-A（架构收敛，4-6 周）
- [ ] 统一交易链路：TradingGateway ↔ PaperGatewayV3 ↔ LiveGateways 适配器合并
- [ ] OMS/Risk/Execution 事件规范化与前置风控落地
- [ ] RealtimeData 实接入：Sina/Eastmoney/Tencent + BarBuilder
- [ ] 统一配置 Schema + 依赖锁定（requirements lock / seed）

#### 任务拆解（模块实施清单 + 测试计划）
- 任务：统一交易链路
  - 模块实施清单：`src/core/trading_gateway.py` 统一适配器入口；`src/core/paper_gateway_v3.py`/`src/gateways/*` 对齐接口；`src/core/interfaces.py` 统一 DTO；`src/core/order_manager.py` 订单生命周期一致化；`src/simulation/matching_engine.py` 成交回报对齐
  - 测试计划：新增 `tests/test_gateway_unification.py`；扩展 `tests/test_trading_infrastructure.py` 覆盖 Paper/Live Stub 流程；回归 `tests/test_order_manager_security.py`
- 任务：OMS/Risk/Execution 事件规范化与前置风控
  - 模块实施清单：`src/core/events.py` 事件 schema；`src/core/risk_manager_v2.py` 前置风控规则；`src/core/trading_gateway.py` 接入风控；`src/core/paper_gateway_v3.py`/`src/simulation/execution_models.py` 事件映射
  - 测试计划：新增 `tests/test_risk_precheck.py`；扩展 `tests/test_trading_infrastructure.py` 验证拒单/事件顺序；回归 `tests/test_monitoring.py`
- 任务：RealtimeData 实接入
  - 模块实施清单：`src/core/realtime_data.py` provider 实装与 BarBuilder；新增 `src/core/realtime_providers/*.py`；`src/core/config.py` 增加数据源配置
  - 测试计划：新增 `tests/test_realtime_data.py`（mock WebSocket/HTTP）；扩展 `tests/test_trading_infrastructure.py` 的实时推送联动
- 任务：统一配置 Schema + 依赖锁定
  - 模块实施清单：`src/core/config.py` 定义 schema 校验；`src/core/defaults.py`/`config.yaml.example` 对齐字段；新增 `requirements.lock` 或 `constraints.txt`
  - 测试计划：新增 `tests/test_config_schema.py`；扩展 `tests/test_system_integration.py` 覆盖加载与缺省值

### V4.0-B（性能与数据治理，6-8 周）
- [ ] BacktestEngine 性能：向量化/Numba、缓存复用、内存基线
- [ ] 数据湖升级：Parquet 分区、版本化、校验门禁、冷热分层
- [ ] 回测/实盘一致性自动化：对账、漂移监控、异常回放
- [ ] 组合级资本分配与风险聚合（多策略/多账户）

#### 任务拆解（模块实施清单 + 测试计划）
- 任务：BacktestEngine 性能提升
  - 模块实施清单：`src/backtest/engine.py` 向量化与缓存复用；`src/backtest/analysis.py` 指标计算优化；`src/data_sources/providers.py` 缓存策略统一
  - 测试计划：新增 `tests/test_backtest_performance.py`（基准对比）；回归 `tests/test_backtest.py`/`tests/test_pipeline.py` 确保一致性
- 任务：数据湖升级
  - 模块实施清单：`src/platform/data_lake.py` 支持 Parquet/版本元数据；新增 `src/platform/data_lake_parquet.py`；`src/data_sources/db_manager.py` 输出 Parquet/分区
  - 测试计划：扩展 `tests/test_platform_data_lake.py`；新增 `tests/test_data_lake_versioning.py`
- 任务：回测/实盘一致性自动化
  - 模块实施清单：新增 `src/core/reconciliation.py`；扩展 `src/mlops/validation.py` 指标对比；`src/backtest/repro.py` 回放链路对齐
  - 测试计划：新增 `tests/test_reconciliation.py`；回归 `tests/test_mlops_validation.py`
- 任务：组合级资本分配与风险聚合
  - 模块实施清单：新增 `src/core/portfolio.py`；扩展 `src/optimizer/combo_optimizer.py` 资金权重；`src/core/risk_manager_v2.py` 聚合风控
  - 测试计划：扩展 `tests/test_combo_optimizer.py`；新增 `tests/test_portfolio_risk.py`

### V4.0-C（平台化与可靠性，8-12 周）
- [ ] API 服务化：FastAPI/gRPC + RBAC/Token + 审计注入
- [ ] 任务编排：JobQueue → Redis/Postgres，DAG/重试/幂等
- [ ] 分布式回测：Ray/Dask + 弹性资源/队列
- [ ] 可观测性：Metrics/Tracing/Alert + 日志聚合

#### 任务拆解（模块实施清单 + 测试计划）
- 任务：API 服务化
  - 模块实施清单：`src/platform/api_server.py` 迁移到 `src/platform/api/*.py`；集成 `src/core/auth.py`/`src/core/audit.py`
  - 测试计划：新增 `tests/test_platform_api.py`（TestClient）；回归 `tests/test_auth_rbac.py`/`tests/test_audit_log.py`
- 任务：任务编排与持久队列
  - 模块实施清单：`src/platform/job_queue.py` 增加 Redis/Postgres backend；`src/platform/orchestrator.py` DAG/重试语义
  - 测试计划：扩展 `tests/test_platform_job_queue.py`；新增 `tests/test_platform_orchestrator.py`（失败重试/幂等）
- 任务：分布式回测
  - 模块实施清单：`src/platform/distributed.py` 适配 Ray/Dask；`src/platform/backtest_task.py` 并行入口统一
  - 测试计划：新增 `tests/test_platform_distributed.py`（本地进程回归 + 远程适配器跳过）
- 任务：可观测性
  - 模块实施清单：`src/core/monitoring.py` 导出指标；`src/core/logger.py` 追踪上下文；关键链路埋点
  - 测试计划：扩展 `tests/test_monitoring.py`；新增 `tests/test_observability_hooks.py`

### V4.0-D（合规与多租户，持续迭代）
- [ ] 多账户/多策略隔离策略、资金划拨与权限模型
- [ ] 审计日志归档/签名存证与保留策略
- [ ] 灾备：多实例主备切换、数据快照恢复演练

#### 任务拆解（模块实施清单 + 测试计划）
- 任务：多账户/多策略隔离
  - 模块实施清单：`src/core/auth.py` 租户/策略隔离；`src/core/trading_gateway.py`/`src/core/order_manager.py` 多账户路由；`src/core/risk_manager_v2.py` 账户级聚合
  - 测试计划：扩展 `tests/test_auth_rbac.py`；新增 `tests/test_multi_account_routing.py`
- 任务：审计日志归档/签名存证
  - 模块实施清单：`src/core/audit.py` 增加归档与签名存证；新增归档存储适配
  - 测试计划：扩展 `tests/test_audit_log.py`（归档/签名验证）
- 任务：灾备与恢复演练
  - 模块实施清单：`src/core/ha.py` 扩展组件快照；`src/core/order_manager.py`/`src/core/trading_gateway.py` 持久化与恢复
  - 测试计划：扩展 `tests/test_ha_snapshot.py`；新增 `tests/test_dr_restore.py`

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
