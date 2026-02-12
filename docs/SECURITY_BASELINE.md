# 安全基线规范（Platform API / 回测与实盘）

## 适用范围
- Platform API (`src/platform/api_server.py`)
- 任务编排与执行 (`src/platform/job_queue.py`, `src/platform/backtest_task.py`)
- 交易网关接入 (`src/core/trading_gateway.py`, `src/gateways/*`)

## 基线要求

### 1. 鉴权与访问控制
- `/api/v1/*` 默认启用 Bearer Token 鉴权（若配置 token）。
- `healthz/readyz/metrics` 可设为公开只读端点。
- 旧接口仅用于兼容，生产建议通过反向代理限制访问。

### 2. 凭证管理
- 禁止将账号口令、API Key、Secret 硬编码入仓库。
- 生产环境通过环境变量或密钥管理系统注入。
- GUI 层不持久化明文凭证到配置文件。

### 3. 请求与响应治理
- 所有 v1 响应包含 `request_id` 用于审计关联。
- 错误码和 HTTP 状态要一致映射，避免“200 + error 文本”模式。

### 4. 审计日志
- 对关键动作记录审计事件：
  - 网关连接/断开
  - 下单/撤单
  - 作业提交/取消
  - 配置变更
- 审计字段最小集合：`timestamp, actor, action, resource, result, request_id`。

### 5. 最小权限原则
- 区分只读、交易、管理操作权限。
- 服务账户默认只授予运行所需最小权限。

### 6. 异常处理规范
- 禁止吞异常后静默继续关键交易流程。
- 异常日志必须包含 request_id 和上下文关键字段。

## 运维建议
- 在边界层（Nginx/API Gateway）增加限流和 IP 白名单。
- 将 `/metrics` 接入 Prometheus，基于失败率与队列拥塞设置告警。
- 定期审计敏感配置与环境变量注入流程。

## 本次已落地
- v1 路由 Bearer 鉴权（可选启用）。
- 统一响应包含 request_id。
- 新增 `/metrics` 指标输出与 `/readyz` 运行态检查。
- 新增作业取消接口并返回标准错误码。
