# 目标架构（生产可用）

## 架构原则
- 分层清晰：Presentation / Application / Domain / Infrastructure。
- 契约优先：外部接口版本化，内部协议显式化。
- 可观测优先：日志、指标、追踪是默认能力。
- 安全默认开启：最小权限、鉴权必选、审计可追溯。

## 目标分层

### 1. Presentation
- CLI：`unified_backtest_framework.py`
- GUI：`scripts/backtest_gui.py`
- Platform API：`/api/v2/*`（FastAPI 主入口）+ `/api/v1/*`（版本化兼容入口）
- Web：`frontend/` Vue3 SPA，生产态可由 `api_v2` 托管 `frontend/dist`

### 2. Application
- Backtest Application Service（编排参数校验、任务装配、执行调度）
- Platform Job Orchestrator（队列调度、状态机、重试/超时）
- Runtime Contexts：`BacktestRuntime` / `SandboxRuntime` / `LiveRuntime` 统一启动 Kernel、Metrics、Tracer 与 PluginRegistry

### 3. Domain
- Strategy / Signal / Risk / Order / Fill / Portfolio
- 统一订单生命周期状态机
- 回测-仿真-实盘一致风控规则

### 4. Infrastructure
- Adapters：`src/adapters/data/`、`src/adapters/realtime/`、`src/adapters/broker/`、`src/adapters/storage/`、`src/adapters/ml/`、`src/adapters/messaging/`
- Legacy imports：`src/data_sources/`、`src/core/realtime_data.py`、`src/gateways/`、`src/core/repository.py`、`src/core/message_bus.py`、`src/mlops/` 保持兼容导出
- Data Providers / Cache / DB / Data Lake
- Live Gateway Adapters
- Metrics / Audit / Logging

## API 契约标准
- v2 统一响应：
```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "uuid"
}
```
- v1 兼容响应：
```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "uuid"
}
```
- 认证：Bearer Token（可由环境变量或启动参数注入）。
- 可用性端点：`/api/v2/health`、`/api/v2/ready`；v1 兼容 `healthz/readyz`。
- 平台信息端点：`/api/v2/info` 暴露平台版本、`contract_version` 与 runtime 策略。
- 可观测端点：`/api/v2/metrics`；v1 兼容指标端点视部署模式保留。

## 作业状态机
- `pending` -> `running` -> `success|failed`
- `pending` -> `cancelled`（支持用户取消）
- 运行中取消默认拒绝（线程任务不可安全强杀）

## 兼容策略
- 未版本化旧接口 `/jobs`、`/gateway/*`、`/health` 已移除；生产入口应使用 `/api/v2/*` 或 `/api/v1/*`。
- 新功能优先在 `/api/v2/*` 增强，v1 仅保留兼容性修复。

## 关键非功能目标
- 可用性：接口异常路径可控、错误可诊断。
- 可扩展性：新增任务类型不影响现有契约。
- 可靠性：作业状态与指标一致，支持恢复分析。

## 当前已实现映射
- FastAPI v2：`src/platform/api_v2.py`
- v1 兼容接口与平台服务：`src/platform/api_server.py`
- Runtime 统一入口：`src/runtime/` 与平台侧 `src/platform/runtime.py`
- Adapter 统一入口：`src/adapters/{data,realtime,broker,storage,ml,messaging}/`
- 作业取消与指标：`src/platform/job_queue.py`
- 启动参数：`scripts/run_platform_api.py`
- 契约测试：`tests/test_platform_api_server.py`
- 中长期规划状态：`docs/MID_LONG_TERM_STATUS_AUDIT.md`
