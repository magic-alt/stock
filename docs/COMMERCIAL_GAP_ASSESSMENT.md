# 商业级能力差距评估（对标 vn.py / qlib 核心能力）

## 范围与结论
- 审查范围：`src/`、`tests/`、`examples/`、`scripts/`、GUI (`scripts/backtest_gui.py`)、平台 API (`src/platform/api_v2.py`, `src/platform/api_server.py`)、前端 (`frontend/`) 和部署资产。
- 结论：项目已具备平台化底座。REST API、Docker 容器化、配置加密、Web 前端和框架级分布式回测已经落地；商业级剩余差距集中在微服务拆分、生产集群化、外部 KMS/Vault、真实网关 SDK 联调、SLO/容量验证和不可篡改审计存储。

## 顶层架构现状
- 展示层：CLI + Tkinter GUI + Platform Web。
- 应用层：BacktestEngine、策略注册、平台任务编排。
- 领域层：订单、撮合、风险、归因、审计。
- 基础设施层：数据源、缓存、网关、作业队列、本地持久化。

## 差距矩阵

### 1. 功能完整性
- 优势：策略、数据源、撮合、归因、MLOps 模块齐备。
- 差距：
  - 平台 API 已版本化，但 v1/v2 文档和客户端 SDK 仍需统一。
  - 作业取消、指标、异步 job 已具备；跨服务任务编排和多租户配额仍需生产化。
  - GUI、Web SPA 与平台接口仍需统一权限和错误展示标准。

### 2. 性能与容量
- 优势：已有缓存与并行处理工具。
- 差距：
  - 缺少标准化压测规范（数据规模、硬件基线、SLO）。
  - 任务队列指标未标准暴露，无法快速识别拥塞与失败峰值。

### 3. 可扩展性
- 优势：策略与数据源有注册机制，可插拔方向明确。
- 差距：
  - API 和任务编排缺乏稳定版本语义。
  - 插件协议与兼容矩阵尚未制度化。

### 4. 安全与合规
- 优势：已有 RBAC、审计日志基础设施。
- 差距：
  - API 鉴权、request_id、安全响应头和敏感值加密能力已具备。
  - 外部 KMS/Vault、数据库静态加密、OAuth2/OIDC、MFA 与不可篡改存储仍未生产化。
  - 最小权限执行和多租户资源隔离仍需和微服务拆分一起推进。

### 5. 测试与质量
- 优势：测试数量可观，覆盖模块广。
- 差距：
  - 需提高端到端契约测试密度（API/作业状态机）。
  - 需补齐 API 安全和异常路径的自动化回归。

## 风险分级
- P0（立即处理）：v1/v2 文档一致性、未版本化入口清理后的部署指引同步、真实 SDK 环境冒烟。
- P1（短中期）：生产容量基准、Ray/Dask 集群部署模板、外部密钥管理、插件契约版本治理。
- P2（中长期）：微服务拆分、跨服务权限/审计/限流、不可篡改审计存储、监管级对账归档。

## 已落地（本次）
- 新增 `/api/v1/*` 版本化 API 路由。
- 新增统一响应结构：`{code,message,data,request_id}`。
- 新增可选 Bearer Token 鉴权（`--api-token` 或 `PLATFORM_API_TOKEN`）。
- 新增 `healthz/readyz/metrics` 端点与队列指标。
- 新增作业取消接口：`POST /api/v1/jobs/{id}/cancel`。
- FastAPI `/api/v2/*`、Docker/Compose、Vue3 前端、SecurityManager/Vault、Ray/Dask 分布式入口均已落地。
- 未版本化旧接口不再作为生产入口。

## 中长期规划完成度

详见 [中长期规划实现状态审计](MID_LONG_TERM_STATUS_AUDIT.md)。摘要：

- P2：REST API、Docker 容器化、配置加密均已完成。
- P3：Web 前端已完成；分布式回测框架大部分完成；微服务架构部分完成。

## 下一步建议
- 用 `docs/COMMERCIAL_UPGRADE_ROADMAP.md` 的 P0/P1/P2 节点作为执行看板。
- 将 API 契约测试纳入 CI 的必跑集合。
- 按 `docs/PERFORMANCE_BENCHMARK_SPEC.md` 建立每周压测基线。
