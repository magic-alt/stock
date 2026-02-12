# 目标架构（商业级）

## 架构原则
- 分层清晰：Presentation / Application / Domain / Infrastructure。
- 契约优先：外部接口版本化，内部协议显式化。
- 可观测优先：日志、指标、追踪是默认能力。
- 安全默认开启：最小权限、鉴权必选、审计可追溯。

## 目标分层

### 1. Presentation
- CLI：`unified_backtest_framework.py`
- GUI：`scripts/backtest_gui.py`
- Platform API：`/api/v1/*`

### 2. Application
- Backtest Application Service（编排参数校验、任务装配、执行调度）
- Platform Job Orchestrator（队列调度、状态机、重试/超时）

### 3. Domain
- Strategy / Signal / Risk / Order / Fill / Portfolio
- 统一订单生命周期状态机
- 回测-仿真-实盘一致风控规则

### 4. Infrastructure
- Data Providers / Cache / DB / Data Lake
- Live Gateway Adapters
- Metrics / Audit / Logging

## API 契约标准
- 统一响应：
```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "uuid"
}
```
- 认证：Bearer Token（可由环境变量或启动参数注入）。
- 可用性端点：`/api/v1/healthz`、`/api/v1/readyz`。
- 可观测端点：`/metrics`（Prometheus 文本）。

## 作业状态机
- `pending` -> `running` -> `success|failed`
- `pending` -> `cancelled`（支持用户取消）
- 运行中取消默认拒绝（线程任务不可安全强杀）

## 兼容策略
- 旧接口 `/jobs`、`/gateway/*`、`/health` 保留一个兼容周期。
- 新功能仅在 `/api/v1/*` 增强；旧接口进入维护模式。

## 关键非功能目标
- 可用性：接口异常路径可控、错误可诊断。
- 可扩展性：新增任务类型不影响现有契约。
- 可靠性：作业状态与指标一致，支持恢复分析。

## 当前已实现映射
- 版本化接口：`src/platform/api_server.py`
- 作业取消与指标：`src/platform/job_queue.py`
- 启动参数：`scripts/run_platform_api.py`
- 契约测试：`tests/test_platform_api_server.py`
