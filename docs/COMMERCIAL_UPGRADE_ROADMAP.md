# 商业级升级路线图

## 目标
在不破坏当前可用能力的前提下，分阶段达到与 vn.py / qlib 的核心能力同级：
- 可靠可复现
- 安全可审计
- 可观测可运维
- 可扩展可持续演进

---

## P0：商业可用底座 ✅ 已完成

### 目标
- API 契约稳定化、安全基线可用、任务运行态可控。

### 工作项
1. 平台 API 契约化
- 统一 `/api/v1/*` 路由。
- 统一响应对象与错误码体系。
- 旧路由兼容保留，发布弃用公告。

2. 鉴权与安全最小闭环
- 为 v1 路由引入 Bearer Token。
- 规范 `request_id` 透传与日志关联。
- 明确对外公开与受保护端点边界。

3. 任务系统可控性
- 增加 pending 任务取消能力。
- 增加队列运行指标：pending/running/success/failed/cancelled。
- 新增 `/metrics` 暴露与 `/readyz` 健康探针。

4. 测试补齐
- 增加 API v1 契约测试。
- 增加任务取消与指标测试。

### 验收标准
- ✅ 新旧接口并存可用。
- ✅ v1 鉴权有效，未授权访问返回 401。
- ✅ `/metrics` 可输出核心计数指标（JSON + Prometheus 双格式）。
- ✅ 新增测试通过且稳定（5 项契约测试全部通过）。

### 代码审计结论（2026-02-28）
全部 P0 工作项已落地并通过测试验收：
- `src/platform/api_server.py`：v1 路由（healthz/readyz/metrics/jobs/gateway）、统一响应信封 `{code, message, data, request_id}`、错误码体系（40101/40001/40401/40901）、旧路由兼容。
- Bearer Token 鉴权：`_is_authorized_v1()` 方法，公开端点（healthz/readyz/metrics）免鉴权，其余强制 401。
- 任务取消：`job_queue.py` `cancel()` 方法，pending 可取消，running 拒绝。
- 指标端点：JSON（`/api/v1/metrics`）+ Prometheus（`/metrics`）双格式输出。
- 契约测试：`tests/test_platform_api_server.py` 含 5 项集成测试（鉴权/工作流/幂等/健康/审计）。

---

## P1：性能与编排可靠性 ✅ 已完成

### 目标
- 中等并发可用，性能可量化，作业编排更稳健。

### 工作项
1. 任务编排升级
- JobStore 升级到 SQLite/PostgreSQL（事务、幂等、恢复）。
- 工作流执行支持超时、重试、失败策略。

2. 回测性能优化
- 明确数据冷热分层缓存策略。
- 建立网格与多策略并发模型的性能阈值。
- 引入标准压测任务集和基线报告。

3. 可观测性增强
- 输出结构化日志字段标准。
- 指标覆盖任务耗时分位、失败分类、队列延迟。

### 验收标准
- ✅ 作业失败后可恢复且可追溯。
- ✅ 标准压测场景下吞吐达标（压测脚本含合成负载及阈值断言）。
- ✅ 关键性能指标可持续对比（阈值嵌入代码自动校验，历史基线对比与回归检测已实现）。

### 代码审计结论（2026-02-28）

**已完成项：**
- ✅ SQLite JobStore（`job_queue.py:140-296`）：事务支持、线程安全、元数据表、索引。
- ✅ 幂等提交（`job_queue.py:285-296, 353-356`）：基于 `(task_type, idempotency_key)` 去重。
- ✅ 工作流超时/重试/失败策略（`orchestrator.py:35-151`）：`ThreadPoolExecutor` 超时、指数退避重试、`abort`/`continue` 策略，测试覆盖。
- ✅ 队列分位指标（`job_queue.py:429-472`）：queue_delay P50/P95/P99、run_duration P50/P95/P99、failure_categories。
- ✅ 压测脚本（`scripts/benchmark_platform.py`）：合成负载、吞吐率、JSON 报告输出。

**未完成项：**
- ~~❌ **数据冷热分层缓存**~~ → ✅ 已实现 `TieredCache`（`performance.py`）：L1 内存 TTLCache + L2 SQLite 持久化，自动升降级，命中率统计。
- ~~❌ **性能阈值代码化**~~ → ✅ 已实现（`benchmark_platform.py`）：`THRESHOLDS` 字典 + `check_thresholds()` 断言函数，`--check-thresholds` CLI 标志，超阈值非零退出。
- ~~❌ **压测基线对比**~~ → ✅ 已实现（`benchmark_platform.py`）：`save_baseline()` / `load_latest_baseline()` / `detect_regression()` 函数，`--save-baseline` / `--check-regression` CLI 标志，回归 > 15% 自动报警。

---

## P2：一致性与运维工程化 ✅ 已完成

### 目标
- 回测/仿真/实盘核心路径一致，运维流程可演练。

### 工作项
1. 一致性校验
- 订单状态机一致性测试（回测 vs 仿真 vs 实盘）。
- 风控规则在三种模式下行为一致。

2. 安全与合规深化
- 审计覆盖关键动作（下单、撤单、配置变更）。
- 审计完整性定期巡检与告警。

3. 发布与运维
- 灰度发布、回滚、故障演练手册。
- SRE 值班指标和事件响应流程。

### 验收标准
- ✅ 运维演练可复现，恢复时间达标。
- ✅ 商业交付所需文档齐备。
- ✅ 核心行为一致性偏差在阈值内（一致性测试通过，price_deviation 风控已实现）。

### 代码审计结论（2026-02-28）

**已完成项：**
- ✅ 订单状态机一致性测试（`tests/test_consistency_modes.py:7-25`）：验证 live gateway 与 simulation 状态映射一致。
- ✅ 风控规则一致性测试（`tests/test_consistency_modes.py:28-50`）：同一 `RiskManagerV2` 实例跨 backtest/paper/live 三模式结果一致。
- ✅ 审计覆盖（`src/core/audit.py`）：哈希链审计日志，覆盖下单/撤单/成交/网关连接/API 操作。
- ✅ 审计完整性巡检（`scripts/audit_integrity_check.py`）：哈希链校验 + 新鲜度检查 + 篡改检测，测试通过。
- ✅ 运维文档：`OPERATIONS_RUNBOOK.md`（灰度发布/回滚/故障演练）、`SRE_INCIDENT_RESPONSE.md`（P1-P3 分级/响应流程/RCA）。
- ✅ 商业文档：API_REFERENCE、LIVE_TRADING_API、DEPLOYMENT_GUIDE、SECURITY_BASELINE、PERFORMANCE_BENCHMARK_SPEC 等齐全。

**未完成项：**
- ~~❌ **风控 price_deviation 检查**~~ → ✅ 已实现（`risk_manager_v2.py`）：`_check_price_deviation()` 方法，基于参考价对比偏离度，配合 `update_reference_price()` / `update_reference_prices()` 方法设置参考价。

---

## 全源码审计发现的额外缺陷（2026-02-28）

### 核心基础设施

| 模块 | 文件 | 状态 | 缺陷 |
|------|------|------|------|
| 异常体系 | `core/exceptions.py` (508行) | ✅ 完备 | 无 |
| 错误处理 | `core/error_handler.py` (614行) | ✅ 完备 | 无 |
| 系统监控 | `core/monitoring.py` | ✅ 完备 | 已实现外部告警通道（邮件/企业微信/钉钉 webhook） |
| 性能工具 | `core/performance.py` (769行) | ✅ 完备 | 无 |
| 实盘运行器 | `core/live_runner.py` | ✅ 生产级 | 已实现错误恢复（skip/retry/halt）、仓位同步校验、审计日志 |

### 交易网关

| 网关 | 文件 | 状态 | 缺陷 |
|------|------|------|------|
| 基类 | `gateways/base_live_gateway.py` (1180行) | ✅ 生产级 | 重连、心跳、速率限制均已实现 |
| XtQuant | `gateways/xtquant_gateway.py` (691行) | ✅ 最成熟 | SDK 直接集成，无 stub |
| XTP | `gateways/xtp_gateway.py` (868行) | ⚠️ 结构完整 | SDK import 失败已明确报错，重度 stub 模式（待真实 SDK 对接） |
| 恒生 UFT | `gateways/hundsun_uft_gateway.py` (1026行) | ⚠️ 结构完整 | SDK import 失败已明确报错，重度 stub 模式（待真实 SDK 对接） |
| 数据映射 | `gateways/mappers.py` (476行) | ✅ 完备 | 无 |

### 业务模块

| 模块 | 状态 | 缺陷 |
|------|------|------|
| 回测引擎 (1234行) | ✅ 高成熟度 | 30+ 指标、网格搜索、归因分析、并行优化 |
| 策略库 (41个) | ✅ 丰富 | 经典技术/ML/专用策略齐全，策略调参文档已补齐（`docs/STRATEGY_REFERENCE.md`） |
| 数据源 (4个 provider) | ⚠️ 中高 | QLib provider 为 stub（回退到 YFinance，初始化失败已明确警告）、无实时流数据 |
| 仿真引擎 | ✅ 高成熟度 | 完整订单生命周期，已实现 A 股规则（T+1/涨跌停/停牌/整手），部分成交概率模型 |
| 因子管道 (4文件) | ✅ 完备 | 15+ 技术因子 + 7 个基本面因子（PE/PB/ROE/税后收益/股息率等）+ 跨因子相关性分析 |
| Web 前端 | ✅ 可用 | 已实现状态管理、表单验证、通知、自动刷新、WebSocket 推送、ECharts K 线图（暗色主题 + 成交量 + 缩放） |
| 编排器 | ⚠️ 可用 | SQLite 持久化工作流 + 超时/重试/失败策略，缺少 DAG 调度和外部持久队列 |

### 测试覆盖

| 维度 | 状态 |
|------|------|
| 测试文件 | 43 个，覆盖核心/平台/ML/运维/负载/故障/E2E |
| 负载测试 | ✅ `test_load.py`：队列吞吐量（>5 jobs/sec）、并发提交、因子管道扩展性 |
| 故障场景测试 | ✅ `test_fault_scenarios.py`：数据源、网关、数据库、资源耗尽共 4 类故障 |
| 端到端测试 | ✅ `test_e2e_workflows.py`：回测工作流、模拟交易全周期、因子管道组合计算 |
| 性能回归测试 | ✅ CI `performance` job：基线存储 + 阈值断言 + >15% 回归自动阻断 |

---

## P3：实盘交易生产就绪 ✅ 大部分完成

### 目标
- 三个交易网关真实 SDK 可用，实盘运行器具备故障恢复能力，仿真引擎补齐 A 股规则。

### 工作项
1. 网关 SDK 实机对接
- XTP 网关接入真实 SDK，移除 stub 模式，增加连接/下单/回报集成测试。
- 恒生 UFT 网关接入真实 SDK，移除 stub 模式，增加集成测试。
- ✅ 统一 SDK import 失败时的明确错误提示（替代静默 try/except pass）。
- ✅ 异步查询结果缓存（`QueryResultCache`）：线程安全 Event 同步等待。
- ✅ SDK 路径动态配置（`GatewayConfig.sdk_path` / `sdk_log_path`）。
- ✅ 网关 Mock SDK 测试（`test_gateway_mock_sdk.py`）：12 个测试类覆盖 stub 模式全生命周期。
- ✅ SDK 安装文档（`docs/GATEWAY_SDK_SETUP.md`）。

2. 实盘运行器加固 ✅
- ✅ 增加策略执行异常捕获与自动恢复（按策略配置决定 skip / retry / halt）。
- ✅ 增加仓位定期同步校验（网关查询 vs 内存状态比对，异常告警）。
- ✅ 接入审计日志（实盘运行启动/停止/异常事件记录）。

3. 仿真引擎补齐 ✅
- ✅ 支持部分成交（基于概率模型 `FillProbabilityModel`）。
- ✅ 增加 A 股特殊规则：T+1 限制、涨跌停判断、停牌处理、整手限制。
- 增加大单流动性影响建模。

4. 监控告警外发 ✅
- ✅ 系统监控指标接入外部告警通道（邮件/企业微信/钉钉 webhook）。
- ✅ 关键指标阈值触发自动告警（CPU > 80%、内存 > 85%、磁盘 > 90%，可配置）。

### 验收标准
- XTP / 恒生 UFT 网关可在测试环境完成登录—下单—回报全流程。
- 实盘运行器可在策略异常后自动恢复并记录审计日志。
- 仿真引擎 T+1 和涨跌停规则在回归测试中通过。
- 告警消息可发送至至少一个外部通道。

---

## P4：数据管道与前端工程化 ✅ 大部分完成

### 目标
- 数据获取支持实时流、因子管道具备基本面覆盖、Web 前端可用于日常运维。

### 工作项
1. 实时数据接入
- 增加 WebSocket / 行情推送数据源适配器（与交易网关行情回调对接）。
- ✅ 实现 L1/L2 冷热缓存分级策略（`TieredCache`：内存 TTL 热缓存 + SQLite 冷存储，自动升降级，命中率统计）。
- QLib provider 改为真实实现或标记为不支持（移除回退到 YFinance 的隐式逻辑）。
- ✅ QLib provider 错误处理改进（初始化失败时明确警告日志）。

2. 因子管道扩展 ✅
- ✅ 增加基本面因子（PE/PB/ROE/营收增长率/股息率/盈利收益率/资产负债率）— `fundamental_factors.py`。
- ✅ 增加跨因子相关性分析和冗余检测 — `factor_analysis.py`。
- 增加因子持续性回测评估模块。

3. Web 前端完善 ✅
- ✅ 补齐 JavaScript 核心逻辑：表单验证、错误处理、状态管理。
- ✅ 接入 WebSocket 实时推送（仓位/行情/订单状态）。
- ✅ 增加 ECharts K 线图表可视化（暗色主题、缩放控件、成交量柱状图），`/api/v1/chart-data` API 端点。
- 增加策略参数配置界面。

4. 性能基线自动化 ✅
- benchmark 脚本增加真实回测负载场景（补充合成负载）。
- ✅ 实现历史基线存储和自动回归检测（> 15% 回归触发阻断）。
- ✅ 将 `PERFORMANCE_BENCHMARK_SPEC.md` 中的阈值嵌入代码断言。

### 验收标准
- 实时行情数据可推送到策略运行器。
- 冷热缓存命中率可监控。
- Web 前端可完成连接—查看持仓—下单—撤单全流程。
- 性能回归超阈值时 CI 自动阻断。

---

## P5：测试工程化与质量门禁 ✅ 大部分完成

### 目标
- 测试体系覆盖负载/故障/端到端场景，CI 门禁自动化。

### 工作项
1. 测试补齐 ✅
- ✅ 增加负载测试（`test_load.py`：队列吞吐量/并发提交/大载荷/因子管道扩展性）。
- ✅ 增加故障场景测试（`test_fault_scenarios.py`：数据源不可用、网关断连/回调异常/速率限制、数据库锁/写入失败、资源饱和）。
- ✅ 增加端到端集成测试（`test_e2e_workflows.py`：回测工作流/模拟交易全周期/因子管道组合计算）。
- ✅ 增加性能回归测试（关键路径耗时基线 + 自动回归检测）。

2. CI/CD 门禁 ✅
- ✅ 集成 pytest + coverage 门禁（覆盖率 > 90% 方可合并）。
- ✅ 集成 mypy / flake8 / black 检查门禁。
- ✅ 性能基线回归检测接入 CI（`performance` job，基线缓存 + 阈值断言 + 回归检测）。

3. 策略文档 ✅
- ✅ 为 41 个策略补齐参数说明和调参建议文档（`docs/STRATEGY_REFERENCE.md`）。
- 增加策略性能基准报告（标准数据集 + 标准时间窗口）。

### 验收标准
- 负载测试在 CI 中定期运行并输出报告。
- 故障场景测试覆盖至少 4 类故障。
- 端到端测试可一键运行并验证全链路。
- CI 门禁阻断不达标的合并请求。

---

## 依赖与风险
- 依赖：交易 SDK 可用性（XTP/恒生授权与测试环境）、数据源稳定性、CI 资源。
- 风险：历史接口兼容成本、跨模块改造耦合、并发行为回归、SDK 版本升级兼容性。

## 里程碑交付件
- P0：版本化 API + 安全基线 + 指标与测试。 ✅
- P1：性能基准体系 + 作业编排升级。 ✅ 全部完成（含冷热缓存、阈值断言、基线回归检测）。
- P2：一致性体系 + 运维工程化手册。 ✅ 全部完成（含 price_deviation 风控实现）。
- P3：实盘交易生产就绪（网关实机对接 + 运行器加固 + 仿真补齐）。 ✅ 大部分完成（QueryResultCache、SDK 路径配置、Mock 测试、SDK 文档已完成，待网关真实 SDK 对接）。
- P4：数据管道与前端工程化（实时数据 + 因子扩展 + Web 前端 + 性能自动化）。 ✅ 大部分完成（因子管道扩展、ECharts 图表、QLib 改进已完成，待实时数据源/策略配置界面）。
- P5：测试工程化与质量门禁（负载/故障/E2E 测试 + CI 门禁）。 ✅ 大部分完成（测试套件/CI 门禁/策略文档已完成，待策略性能基准报告）。

## 已实施状态总览（2026-02-28 V4.0-C/D 升级完成）

| 阶段 | 状态 | 已完成 | 未完成 |
|------|------|--------|--------|
| P0 | ✅ 全部完成 | v1 API 契约、Bearer 鉴权、任务取消、健康探针、指标端点（JSON+Prometheus）、5 项契约测试 | — |
| P1 | ✅ 全部完成 | SQLite JobStore、幂等提交、工作流超时/重试/失败策略、队列分位指标、合成压测脚本、**L1/L2 冷热缓存**、**性能阈值代码化断言**、**压测基线历史对比与自动回归检测** | — |
| P2 | ✅ 全部完成 | 审计哈希链+关键动作覆盖、完整性巡检脚本、一致性测试、运维文档齐全、**price_deviation 风控规则实现** | — |
| P3 | ✅ 大部分完成 | SDK import 明确报错、**实盘运行器加固**、**仿真 A 股规则**、**监控告警外发**、**QueryResultCache**、**SDK 路径配置**、**Mock SDK 测试**、**SDK 安装文档** | 网关真实 SDK 对接（XTP/恒生 UFT 仍为 stub 模式） |
| P4 | ✅ 大部分完成 | **L1/L2 冷热缓存**、**Web 前端 JS**、**性能基线自动化**、**基本面因子模块（7 因子）**、**跨因子相关性分析**、**ECharts K 线图表**、**QLib 错误处理改进** | 实时数据源适配、QLib provider 真实化、策略配置界面 |
| P5 | ✅ 大部分完成 | **故障场景测试（4 类）**、**负载测试（队列+因子管道）**、**E2E 工作流测试（3 类）**、**CI 性能回归门禁**、**pytest marker 更新**、**策略参考文档（41 策略）** | 策略性能基准报告 |
| V4.0-A | ✅ 全部完成 | 网关协议统一测试（test_gateway_unification）、PaperGateway 前置风控集成（test_risk_precheck）、AKShare HTTP 轮询实时行情（AKShareDataProvider）、配置 Schema 扩展（LiveTrading/RealtimeData/Portfolio） | — |
| V4.0-B | ✅ 全部完成 | 向量化 BacktestEngine 指标+网格搜索缓存（test_backtest_performance）、Parquet 数据湖+版本/校验和/Schema（test_data_lake_versioning）、回测/实盘对账（Reconciler+test_reconciliation）、组合风险聚合（PortfolioManager+test_portfolio_risk） | — |
| V4.0-C | ✅ 全部完成 | 模块化 API Router+RBAC/速率限制/审计中间件（test_platform_api）、DAG 工作流拓扑排序+并行执行（test_platform_orchestrator）、Redis job store backend+TTL（test_platform_job_queue）、Ray/Dask 分布式回测适配器（test_platform_distributed）、OpenTelemetry 兼容 Tracing+MetricCollector（test_observability_hooks） | — |
| V4.0-D | ✅ 全部完成 | 多账户 RBAC+AccountManager 资金划拨（test_multi_account_routing）、审计日志归档+HMAC-SHA256 签名+保留策略（test_audit_log）、DR FailoverManager 主备切换+DrillRunner 自动化演练（test_dr_restore） | — |
