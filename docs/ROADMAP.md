# 项目路线图 | Project Roadmap

**项目**: 量化回测与实盘系统（Unified Quant Platform）
**当前版本**: V5.0.0（双引擎 + Gateway 加固 + 策略准入门禁完成）
**更新日期**: 2026-05-18
**状态**: 🟢 生产可用 | 开源可信度修复与平台能力收敛持续推进

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
- ✅ 数据版本锁定/快照化（数据湖分区/校验门禁）
- ✅ 统一列式存储（Parquet）与冷热分层

### 回测与分析
- ✅ 单策略回测 / 多策略批量 / 网格搜索 / 自动化流程
- ✅ 组合优化（NAV 权重）
- ✅ 回测报告与图表：Markdown / JSON / PNG + Top-N 重放
- ✅ 绩效归因与风格暴露：VaR/ES/Tracking/Concentration/Sector
- ✅ 复现快照与报告签名（repro snapshot）
- ✅ 滑点与手续费插件（CN 规则）
- ✅ 市场冲击/成交概率/延迟模型（execution_models）
- ✅ 回测性能提升（向量化/并行/缓存复用）

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
- ✅ 组合级/多账户风险聚合与资金分配
- ✅ 实盘/回测一致性自动对账

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
- ✅ JobQueue / Orchestrator / Distributed（本地线程/进程 + Ray/Dask 适配器）
- ✅ FastAPI v2 REST API（`/api/v2/*` + OpenAPI）与版本化 `/api/v1/*` 兼容入口
- ✅ DataLake（manifest）
- ✅ API Bearer Token 鉴权 + `request_id` 透传 + 审计注入
- ✅ SQLite JobStore（幂等提交、事务恢复）+ 队列分位指标
- ✅ 工作流超时/重试/失败策略
- ✅ `/readyz` 健康探针 + `/metrics`（JSON + Prometheus）指标端点
- ✅ DAG 拓扑排序与并行执行、Redis JobStore backend（含 fallback）
- 🟡 Postgres backend 生产化与跨服务调度

### 部署 / 安全 / 前端（中长期规划复核）
- ✅ REST API：`src/platform/api_v2.py` 提供 `/api/v2/*` 生产入口，`/api/v2/docs` 暴露 OpenAPI。
- ✅ Docker 容器化：根目录 `Dockerfile` 多阶段生产镜像，`docker-compose.yml` 编排 API/Frontend/Redis，`frontend/Dockerfile` 支持独立前端镜像。
- ✅ 配置加密：`src/core/security.py` + `src/core/vault.py` 已提供敏感值加密与本地加密 vault。
- ✅ Web 前端：`frontend/` Vue3 SPA 已覆盖回测、交易、策略、数据与监控页面。
- 🟡 微服务架构：当前为模块化单体 + 容器编排，尚未拆分为独立 backtest/data/trading/ml 服务。
- 🟡 分布式回测生产化：框架级 LocalProcessPool/Ray/Dask 已完成，集群部署、容量基准和任务数据治理仍待补齐。

### GUI / CLI / Examples
- ✅ CLI：`run/grid/auto/combo/list`
- ✅ GUI：tkinter GUI（已优化响应速度）
- ✅ 示例：`quick_start`, `batch_backtest`, `ml_strategy_gallery`, `ml_enhanced_examples`

---

## 3) 生产可用能力对照（真实实现状态）

### ✅ 已具备（核心框架可支撑稳定研究与回测流程）
- 统一策略接口与事件驱动架构
- 多数据源与缓存
- DataPortal + SQLite 数据库
- 数据质量 + 交易日历对齐 + 数据血缘
- 多策略批量回测 + 参数优化 + 复现快照
- 订单/风控/撮合模块 + 审计/RBAC
- 可视化报告输出
- 实盘网关接口层（XTP/XtQuant/UFT，SDK 依赖）
- 平台化 MVP（API/JobQueue/Distributed）

### ✅ 已补齐的生产可用能力（2026-05-19 复核）
- 统一交易链路（TradingGateway/PaperGateway/LiveGateways）与前置风控：GatewayService 连接时注入 RiskManagerV2，Paper/Live adapter 进入报单前共享风险检查路径。
- 策略准入强制门禁：`baseline/admission/start_production.py` 已串成 `research -> baseline_registered -> admission_passed -> paper_validated -> live_candidate -> production`，paper 入口强制要求已注册 baseline，组合优化与资金分配预览强制要求 admission PASS，并按参数签名写入 gate registry。
- 实时报价与行情接入（Sina/Eastmoney/Tencent/Level2）：L1 provider 已实接入，Level2 建立 SDK 无关模型、provider 协议、mock/stub adapter 与事件投递契约。
- 数据湖版本化、列式存储与质量门禁：ParquetDataLake promotion 强制 checksum + schema + 缺失率 + OHLC + 索引质量门禁。
- 分布式调度与可扩展队列（非本地）：JobStore 支持 JSON/SQLite/Redis/Postgres DSN，生产可关闭 fallback，并在监控指标中暴露 backend 类型。
- 可观测性体系（metrics/tracing/alert）：MetricCollector 支持 Prometheus 文本导出，FastAPI v2 贯穿 request_id/trace_id，并保留可选 OTLP/HTTP exporter。
- 多账户/组合级风控与资金分配：AccountManager API、组合资金分配预览与 CapitalAllocator 已落地，支持现金缓冲、账户权重、策略权重和风险预算约束。

### 🟡 后续生产增强项
- 真实 Level2 券商 SDK 联调与延迟/丢包基准（需要券商账号、权限与 SDK 路径）。
- Postgres/Redis 高可用部署、跨服务队列调度与容量基准。
- OpenTelemetry Collector/Grafana/Loki/Tempo 部署模板与 SLO 仪表盘。
- 实盘多账户清算/对账/回放与长期不可篡改归档。

### 🔴 尚未实现（进一步生产化仍需补齐的能力）
- 微服务拆分后的权限/审计/隔离完备实现
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
- [x] **中期 P2** REST API / Docker 容器化 / 配置加密复核完成（见 `docs/MID_LONG_TERM_STATUS_AUDIT.md`）
- [~] **长期 P3** Web 前端已完成，分布式回测框架已完成，微服务化仍在规划中

---

## 5) 下一步技术路线（面向 V4.0）

### 历史阶段（已完成）
- [x] Phase 3.2.1 稳定化（配置快照 / 数据质量 / 交易日历 / 复现签名）
- [x] Phase 3.3 风控与交易建模升级（VaR/ES/归因/冲击/延迟）
- [x] Phase 3.4 生产化与合规（审计/RBAC/血缘/灾备）
- [x] Phase 3.5 AI 框架接入与 MLOps（Qlib/FinRL/Registry/Inference）
- [x] Phase 4 MVP 平台化（API/作业编排/分布式/数据湖）

### V4.0-A（架构收敛，4-6 周）✅ 已完成
- [x] 统一交易链路：TradingGateway ↔ PaperGatewayV3 ↔ LiveGateways 适配器合并
- [x] OMS/Risk/Execution 事件规范化与前置风控落地
- [x] RealtimeData 实接入：Sina/Eastmoney/Tencent + BarBuilder
- [x] 统一配置 Schema + 依赖锁定（requirements lock / seed）

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

### V4.0-B（性能与数据治理，6-8 周）✅ 已完成
- [x] BacktestEngine 性能：向量化、缓存复用、内存基线
- [x] 数据湖升级：Parquet 分区、版本化、校验门禁、冷热分层
- [x] 回测/实盘一致性自动化：对账、漂移监控、异常回放
- [x] 组合级资本分配与风险聚合（多策略/多账户）

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

### V4.0-C（平台化与可靠性，8-12 周）✅ 全部完成
- [x] API 服务化：模块化 Router + RBAC Middleware + 速率限制 + 请求验证 + 审计中间件
- [x] 任务编排：JobQueue → Redis backend（含 fallback）；Orchestrator DAG 拓扑排序+并行执行
- [x] 分布式回测：Ray/Dask 适配器 + LocalProcessPool 默认后端 + DistributedRunner
- [x] 可观测性：TraceContext/Span/Tracer + MetricCollector（counter/gauge/histogram）+ 单例

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

### V4.0-D（合规与隔离，持续迭代）✅ 全部完成
- [x] 多账户/多策略隔离：account_id 字段 + enforce_account + AccountManager（CRUD/划拨/关户/风险摘要）
- [x] 审计日志归档/签名存证：archive() + HMAC-SHA256 sign/verify + RetentionPolicy + export_for_compliance
- [x] 灾备：FailoverManager（主备切换/回切）+ DrillRunner（自动化 snapshot-restore-verify 演练）

#### 任务拆解（模块实施清单 + 测试计划）
- 任务：多账户/多策略隔离
  - 模块实施清单：`src/core/auth.py` 账户/策略隔离；`src/core/trading_gateway.py`/`src/core/order_manager.py` 多账户路由；`src/core/risk_manager_v2.py` 账户级聚合
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
- 如需继续提升生产可用性，建议优先完成 **风控、数据治理、审计、回测复现** 四类能力

---

## 8) V5.0 开源演进路线（2026 H2 - 2027 H1）

> 此章节聚焦开源版本的公开入口、演示体验、平台能力表达和研究工作流。

### 8.1 公开入口与可信度

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| README / Docs | 5 秒理解价值、5 分钟跑通入口 | README 重构、MkDocs 可构建、Getting Started 路线 |
| 社区协作 | 让 issue / PR / 安全反馈路径清晰 | `CONTRIBUTING.md`、`SECURITY.md`、Issue/PR 模板 |
| CI 可验证性 | 公开仓库的质量门禁真实可信 | MkDocs、frontend build、Ruff、MyPy、Docker 校验硬失败 |

### 8.2 演示与新手体验

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| 一键演示 | 降低首次运行门槛 | `examples/one_click_demo.py`、示例报告、ECharts 数据 |
| 确定性 demo | 无需券商 SDK 或外部 token 也能看见核心流程 | `scripts/demo_platform_console.py`、paper demo JSON 输出 |
| 前端 demo mode | 在无真实 API/账户时展示关键页面 | Dashboard/Backtest/Trading 示例状态与样例数据 |
| 示例数据 | 避免新用户卡在联网或授权步骤 | 小样本 A 股风格 OHLCV fixture |

### 8.3 平台与研究工作流表达

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| 策略准入展示 | 把 baseline / admission / gate registry 变成公开卖点 | README 示例、报告页、前端准入摘要 |
| 历史报告加载 | 展示平台不是一次性脚本 | Backtest 页面加载历史 report / snapshot |
| 数据与执行能力 | 强化 A 股研究定位 | L2 接口抽象、CTP 适配、算法执行与回放 |
| 研究协作 | 让回测、报告、数据集可以复用 | Notebook / report / workspace 路径约定 |

### 8.4 可靠性与可观测性

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| OpenTelemetry | API → Job → Engine → Gateway 的 trace 可观察 | OTLP exporter、Grafana/Loki/Tempo 模板 |
| 容量基准 | 定义回测吞吐与稳定性边界 | `benchmark_platform.py` 场景扩展、容量报告 |
| 灾备与演练 | 把 snapshot/restore 从脚本能力提升为流程能力 | Failover / drill runbook 与验证脚本 |

### 8.5 V6 开放平台基座（2026 H2 起，与 V5 演进并行）

> 详细设计见 [`docs/architecture/open-platform.md`](architecture/open-platform.md)。V6 是
> **附加式、向后兼容**的重组，不替代 V5 的策略准入、A 股规则、RBAC、审计哈希链、DR 演练
> 与 MLOps 能力。

| Phase | 主题 | 关键产出 | 改动面 |
|------|------|---------|------|
| 0 | 架构决策与契约冻结 | 目标架构图、`docs/architecture/open-platform.md`、entry-point 分组定义 | 仅文档 + `pyproject.toml` |
| 1 | Kernel 硬化 | `src/core/kernel.py`、`ComponentState` FSM、MessageBus 抛出能力补齐 | Additive |
| 2 | 领域契约 SSOT | `src/core/contracts/`（DTO + Ports + 一致性测试），`interfaces.py` 改为 re-export | Additive |
| 3 | Engines 分层 | `src/engines/data\|execution\|risk\|portfolio\|backtest\|research\|report/`，包装现有实现 | Additive wrappers |
| 4 | Adapters 收敛 | `src/adapters/data\|realtime\|broker\|storage\|ml\|messaging/`，旧路径保留 re-export | Re-exports |
| 5 | Plugin SPI + SDK | 已落地：`src/sdk/`、`PluginRegistry`、cookiecutter 模板、示例插件、`quant-platform plugin test` CLI | Additive |
| 6 | Platform / Runtime 对齐 | `BacktestRuntime/SandboxRuntime/LiveRuntime`、统一 `MetricsPort/Tracer`、`/api/v2/info` 暴露 `contract_version` | Internal refactor |
| 7 | 分发拆包 | `quant_platform_core / sdk / adapters_cn / ml / web / cli` 多发布物，README 架构图重写 | Packaging |
| 8 | 迁移纪律 | `src/_legacy/` 兼容层 + deprecation warning，按 PR 持续清理 | Cleanup |

关键决策默认值（可在后续 Phase 调整）：

- 插件沙箱：保留 `src/core/strategy_loader.py` 的 AST `CodeSafety`；签名插件机制留给运营，subprocess / 容器化隔离由部署侧决定。
- 默认 MessageBus：进程内（`src/core/message_bus.py`），Redis / ZMQ 适配器作为可选 `quant_platform.messaging` 插件。
- 分发节奏：先在单包 `quant-stock` 内完成内核 + 引擎 + SDK 重组，API 稳定后再拆多 distribution。

非目标（V6 不做）：语言层重写（Rust/C++ 内核）、微服务化、多市场扩张。这些仍属于第 9 节长期方向。

---

## 9) 长期技术方向（2027 Q3 之后）

### 9.1 性能与延迟

- **C++ / Rust 撮合内核**：将 `MatchingEngine` 核心路径迁移到更低延迟实现，Python 保留调度与策略层。
- **低延迟 OMS**：缩短报单到网关路径延迟，明确性能基准和硬件依赖。
- **GPU 因子计算**：对大规模横截面因子与特征工程提供 RAPIDS / CuDF 加速路径。
- **分布式回测集群**：Ray/Dask 集群化，支持更大历史区间、更高参数规模和统一报告归并。

### 9.2 合规与审计增强

- **程序化交易报送适配**：支持结构化报送文件生成与留档。
- **可解释性 / Model Card**：为 ML 模型生成数据来源、训练配置、性能和漂移摘要。
- **不可篡改审计归档**：增强审计哈希链与长期归档存储策略。

### 9.3 多市场与研究扩展

- **港股 / 期货 / 期权扩展**：在现有 A 股定位之外逐步增加更多交易所与品种适配。
- **多市场数据适配**：统一不同市场的日历、撮合规则、合约元数据和风控输入。

### 9.4 AI / 大模型增强

- **自然语言策略草稿**：辅助生成策略原型并交给沙箱与 admission 流程验证。
- **研报 / 新闻摘要**：将非结构化文本转化为研究线索，而非直接交易信号。
- **代码助手与知识检索**：用仓库文档、策略库和报告资产提升开发效率。

---

## 10) 技术债与重构清单（持续）

> 来自 PR review 和实际运营中发现的技术债，优先级标注。

| 优先级 | 项目 | 说明 |
|--------|------|------|
| **P0** | `OrderStateMachine` 与 `OrderManager` 状态合并 | 当前两套 enum；统一为单一 SSOT |
| **P0** | 实盘网关接入 RiskManagerV2 前置风控 | 当前回测/Paper 已接，Live 仅事后审计 |
| **P1** | 数据湖统一 Parquet 列存 | 当前混合 SQLite + CSV + Parquet |
| **P1** | 配置 Schema 强校验（Pydantic v2） | 当前部分字段未校验，运行时才报错 |
| **P1** | 测试套件分层（unit/integration/e2e）显式 marker | 当前部分依赖 import-skip 模式 |
| **P2** | Zipline 适配器从「向量化回退」升级为完整 TradingAlgorithm 适配 | 当前是简化映射，未完全利用 zipline pipeline |
| **P2** | GUI 从 tkinter 迁移到 PySide6 / Tauri | tkinter 体验受限 |
| **P3** | 文档双语化（英文版） | 当前以中文为主 |
| **P3** | mypy strict 模式 | 当前是 lenient，部分模块未完全类型化 |

---

## 11) 度量与里程碑（OKR 模板）

### 2026 H2 OKR（开源可信度与体验阶段）
- **O1**：公开入口可信且可复现
  - KR1：README / MkDocs / CI / LICENSE / 社区文件全部闭环
  - KR2：提供无需外部凭证的一键 demo 与样例报告
  - KR3：前端关键页面可在 demo mode 下稳定展示
- **O2**：稳定性提升
  - KR1：API 服务 SLO ≥ 99.9%
  - KR2：核心回测路径 P95 延迟降低 30%
  - KR3：测试覆盖率 ≥ 92%（当前 ~88%）

### 2027 H1 OKR（开源增长与研究工作流阶段）
- **O1**：形成可传播的研究平台体验
  - KR1：连续发布高质量 release，并附截图、demo 与已知限制
  - KR2：策略准入、A 股规则仿真、Web 控制台形成三条清晰展示路径
  - KR3：建立稳定的 examples/tutorials 路线，降低新用户首小时流失
- **O2**：可观测与可靠
  - KR1：完整 OpenTelemetry 覆盖
  - KR2：完成 1 次跨区域演练（RTO < 5min）
  - KR3：容量基准和运行看板纳入常规发布流程

---

**维护者**: magic-alt  
**许可证**: MIT
