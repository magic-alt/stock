# 项目路线图 | Project Roadmap

**项目**: 量化回测与实盘系统（Unified Quant Platform）
**当前版本**: V3.3.0（双引擎 + Gateway 加固完成）
**更新日期**: 2026-05-18
**状态**: 🟢 生产可用 | 商业化升级 P0-P5 全部完成 | V5.0 商业化产品规划中

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
- 🟡 多租户生产化、Postgres backend 与跨服务调度

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

### ✅ 已补齐的基金级能力（2026-05-19 复核）
- 统一交易链路（TradingGateway/PaperGateway/LiveGateways）与前置风控：GatewayService 连接时注入 RiskManagerV2，Paper/Live adapter 进入报单前共享风险检查路径。
- 实时报价与行情接入（Sina/Eastmoney/Tencent/Level2）：L1 provider 已实接入，Level2 建立 SDK 无关模型、provider 协议、mock/stub adapter 与事件投递契约。
- 数据湖版本化、列式存储与质量门禁：ParquetDataLake promotion 强制 checksum + schema + 缺失率 + OHLC + 索引质量门禁。
- 分布式调度与可扩展队列（非本地）：JobStore 支持 JSON/SQLite/Redis/Postgres DSN，生产可关闭 fallback，并在监控指标中暴露 backend 类型。
- 可观测性体系（metrics/tracing/alert）：MetricCollector 支持 Prometheus 文本导出，FastAPI v2 贯穿 request_id/trace_id，并保留可选 OTLP/HTTP exporter。
- 多账户/组合级风控与资金分配：AccountManager API、组合资金分配预览与 CapitalAllocator 已落地，支持现金缓冲、账户权重、策略权重和风险预算约束。

### 🟡 后续生产增强项
- 真实 Level2 商业 SDK 联调与延迟/丢包基准（需要券商账号、权限与 SDK 路径）。
- Postgres/Redis 高可用部署、跨服务队列调度与容量基准。
- OpenTelemetry Collector/Grafana/Loki/Tempo 部署模板与 SLO 仪表盘。
- 实盘多账户清算/对账/回放与长期不可篡改归档。

### 🔴 尚未实现（基金级“生产化”必要项）
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

### V4.0-D（合规与多租户，持续迭代）✅ 全部完成
- [x] 多账户/多策略隔离：account_id 字段 + enforce_account + AccountManager（CRUD/划拨/关户/风险摘要）
- [x] 审计日志归档/签名存证：archive() + HMAC-SHA256 sign/verify + RetentionPolicy + export_for_compliance
- [x] 灾备：FailoverManager（主备切换/回切）+ DrillRunner（自动化 snapshot-restore-verify 演练）

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

## 8) V5.0 商业化产品路线（2026 Q3 - 2027 Q2）

> 此章节定义本平台从「自用工具 + 开源框架」升级为「**商业级 SaaS / 私有化产品**」
> 的产品形态、商业模式与技术升级路径。

### 8.1 产品形态

| 形态 | 目标客群 | 定价模式 | 部署 |
|------|---------|---------|------|
| **开源版** | 个人量化、学生、教学 | 免费 (MIT) | 本地 / 自建 |
| **Pro 桌面版** | 个人量化进阶、小型工作室 | 订阅 ¥299-999/月 | 本地客户端 + 云授权 |
| **Team 云版** | 私募团队、量化俱乐部 (≤20 人) | ¥3,000-15,000/月 (按席位) | 公有云 / 容器化 SaaS |
| **Enterprise 私有化** | 公募 / 券商 / 资管 / 银行理财 | ¥50 万-500 万/年 | 客户内网 / 专属云 + SLA |
| **Marketplace 策略市场** | 策略生产者 + 消费者 | 抽佣 15-30% | 内嵌于 Team / Enterprise |

### 8.2 V5.0-A：商业化基础设施（2026 Q3 - Q4）

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| 多租户隔离 | 单一部署支持 ≥100 租户、租户级资源/数据隔离 | `src/platform/tenancy/` + Postgres schema 隔离 |
| 计费与配额 | 按调用次数 / 任务时长 / 数据量计费 | `src/platform/billing/` + Stripe / 支付宝接入 |
| 用户身份 | OAuth2 / SSO / SAML / 手机短信验证 | 扩展 `src/core/auth.py`，集成 Keycloak |
| 订阅管理 | 试用、订阅、续费、退款、发票 | `src/platform/subscription/` |
| 审计合规 | SOC2 Type II / 等保 2.0 三级（私有化版） | 审计哈希链上链选项 + 不可篡改归档 (S3 Object Lock / WORM) |
| 客户支持 | 工单、知识库、Discord / 企业微信群 | 集成 Zendesk / Crisp |

#### 任务拆解
- **租户隔离**：`src/platform/tenancy/manager.py`（CRUD）+ Postgres `tenant_id` 行级过滤 + Redis namespace
- **配额管理**：基于 `JobQueue` 添加配额计数器；超额返回 `429 Too Many Requests`
- **计费 Hook**：每个 `BacktestTask` 完成时写入 `BillingEvent`；月底批量结算
- **测试**：`tests/test_tenancy_isolation.py` / `tests/test_billing_events.py` / `tests/test_quota_enforcement.py`

### 8.3 V5.0-B：高级数据与执行（2026 Q4 - 2027 Q1）

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| **L2 行情接入** | 上交所/深交所 Level2 实时行情 (10 档 + 逐笔) | `src/data_sources/level2/` + 通过 XTP/UFT 转发 |
| **多资产支持** | 股票 + ETF + 可转债 + **股指期货 + 商品期货 + 期权** | 新增 `src/gateways/ctp_gateway.py` + `src/instruments/derivatives.py` |
| **FIX 协议网关** | 海外交易所 / 跨境券商接入 | `src/gateways/fix_gateway.py` (QuickFIX-Python) |
| **算法母单** | TWAP / VWAP / POV / Iceberg / Sniper 等执行算法 | `src/execution/algos/` + 母单/子单 OMS 扩展 |
| **跨账户资金分配** | 多账户/多策略统一资金池 + 实时风险预算 | 扩展 `src/core/portfolio.py` + `src/core/capital_allocator.py` |
| **实时风控 (前置)** | 报单前 <1ms 风控决策；硬熔断 + 软警告 | `src/core/risk_manager_v3.py`（C 扩展或 Cython） |

#### 任务拆解
- **CTP 集成**：基于 `vnpy-ctp` / `openctp` 实现 `CTPGateway`；先 SimNow 模拟，后真实期货账户
- **算法母单**：定义 `AlgoOrder` 类（`OrderManager` 子类型），引擎驱动子单按时间/成交量切片
- **L2 行情**：实现 `Level2DataAdapter`，将 10 档 + 逐笔事件投递到 `EventEngine`；新增 `OrderBookFeature` 工具
- **测试**：`tests/test_ctp_simnow.py` (skip if no SimNow account) / `tests/test_algo_twap.py` / `tests/test_l2_orderbook.py`

### 8.4 V5.0-C：研究与策略市场（2027 Q1 - Q2）

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| **JupyterLab Hub** | 浏览器内研究环境，预装本平台 SDK | K8s + JupyterHub + 自定义 Docker 镜像 |
| **特征仓库 (Feature Store)** | 在线/离线特征统一存储与服务 | `src/platform/feature_store/` (Feast / 自研) |
| **策略市场** | 策略发布、订阅、回测验证、收益分成 | `src/platform/marketplace/` + 前端商店页面 |
| **回测即服务 (BaaS)** | REST API 提交任务 → 返回任务 ID + 报告 | 已有 `/api/v2/backtest/jobs`，需上传策略代码沙箱执行 |
| **策略沙箱** | Docker / gVisor 隔离运行不受信策略代码 | `src/platform/sandbox/` + 安全 evaluator |
| **协作研究** | 多人共享数据集、Notebook、回测结果 | 工作区 (Workspace) 抽象 + 权限 |

#### 任务拆解
- **沙箱**：gVisor / Firecracker 微 VM；策略代码白名单 import（禁 socket / subprocess）；CPU/内存配额
- **特征仓库**：以 Parquet + DuckDB 为离线后端；Redis 为在线服务后端
- **策略市场前端**：复用 `frontend/`（Vue3 + Vite），增加 store 路由
- **测试**：`tests/test_sandbox_isolation.py` / `tests/test_feature_store.py` / `tests/test_marketplace_flow.py`

### 8.5 V5.0-D：可观测性与可靠性升级

| 模块 | 目标 | 关键产出 |
|------|------|---------|
| OpenTelemetry 全链路追踪 | 跨服务 trace_id 贯穿 (API → Job → Engine → Gateway) | 已有 `TraceContext`，迁移到 OTLP exporter |
| Grafana / Loki / Tempo | 指标 + 日志 + 追踪统一展示 | `deploy/k8s/observability/` Helm chart |
| 多区域热备 | 单可用区故障 RTO < 5 min, RPO < 1 min | 跨 region 数据库异步复制 + DNS failover |
| 混沌工程 | 注入网络/磁盘/进程故障，验证可靠性 | `tests/chaos/` + ChaosMesh integration |
| Runbook / SLO 仪表盘 | 服务 SLO (99.9% 可用) + 错误预算 | 自动生成 SLO 报告 |

---

## 9) V6.0 企业级 / 监管级（2027 Q3 之后）

> 面向 **公募基金、券商自营、保险资管、跨境机构** 的最高合规与性能要求。

### 9.1 性能与延迟

- **C++ 撮合内核**：将 `MatchingEngine` 核心路径用 C++ / Rust 重写，Python pybind 包装。目标：单线程 100K orders/sec
- **低延迟 OMS**：报单 → 网关延迟 < 50µs（用户态网络 / DPDK / Solarflare TCPDirect）
- **FPGA 行情解码**（可选）：与硬件厂商合作，行情 → 策略 < 5µs
- **GPU 因子计算**：CuDF / RAPIDS 加速横截面因子（>1000 标的 × 100 因子，秒级）
- **分布式回测集群**：Ray Cluster 千核横向扩展，单次回测 10 年 × 沪深 300 ≤ 30 秒

### 9.2 合规与监管报送

- **CSRC 程序化交易报送** 自动生成报送文件（XML/CSV）
- **AML / KYC 集成**（机构客户）
- **可解释性 / Model Card**：每个 ML 模型自动生成 Model Card（数据来源、训练集、性能、偏差报告）
- **不可篡改审计**：审计哈希链可选上 **联盟链 (Hyperledger Fabric)** 存证
- **数据本地化**：客户境内数据不出境（私有化版默认；SaaS 版按区域分仓）

### 9.3 多市场扩展

- **港股通 / 沪伦通 / 深港通**：跨境清算适配
- **美股 / 期货 / 加密货币**：分别通过 FIX / CME / Binance API 接入（仅限合规许可的客户）
- **数字货币**：可选模块，受所在地法规约束

### 9.4 AI / 大模型增强

- **自然语言策略生成**：用户用中文描述 → LLM 生成策略代码 → 沙箱验证 → 部署
- **研报智能摘要**：接入研报 + 新闻数据流，LLM 抽取交易信号
- **代码助手 (Copilot for Quant)**：基于 RAG 检索本仓库 + 私有策略库，辅助策略开发
- **风险预警 Agent**：LLM Agent 监控市场异动 + 持仓 → 主动告警

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

### 2026 H2 OKR（V5.0-A/B 阶段）
- **O1**：商业化平台 MVP 上线
  - KR1：完成多租户基础设施（≥10 试点租户）
  - KR2：上线计费 / 订阅 / 配额（端到端付费跑通）
  - KR3：L2 行情接入 + 期货 CTP 模拟联调
- **O2**：稳定性提升
  - KR1：API 服务 SLO ≥ 99.9%
  - KR2：核心回测路径 P95 延迟降低 30%
  - KR3：测试覆盖率 ≥ 92%（当前 ~88%）

### 2027 H1 OKR（V5.0-C/D 阶段）
- **O1**：策略市场和研究平台
  - KR1：JupyterHub 上线，月活研究员 ≥ 100
  - KR2：策略市场上架 ≥ 50 个策略
  - KR3：BaaS API 调用 ≥ 100K/月
- **O2**：可观测与可靠
  - KR1：完整 OpenTelemetry 覆盖
  - KR2：完成 1 次跨区域演练（RTO < 5min）
  - KR3：SOC2 Type II 报告完成

---

**维护者**: magic-alt  
**许可证**: MIT
