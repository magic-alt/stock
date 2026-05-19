# 中长期规划实现状态审计

**审计日期**: 2026-05-18
**审计范围**: `src/`，并结合仓库根目录部署资产（`Dockerfile`、`docker-compose.yml`、`frontend/`、`deploy/k8s/`）核对容器与前端状态。
**结论口径**: 以当前代码可运行能力为准；“完成”表示已有仓库内实现和测试入口，“部分完成”表示有框架或单机能力但未达到生产集群/多服务拆分形态。

## 结论总览

| 规划项 | 原优先级 | 当前状态 | 完成度 | 代码证据 | 剩余缺口 |
|--------|----------|----------|--------|----------|----------|
| REST API 实现 | P2 | ✅ 已完成 | 90% | `src/platform/api_v2.py` FastAPI `/api/v2/*`；`src/platform/api/` Router/Middleware；`src/platform/api_server.py` `/api/v1/*` | OAuth2/OIDC、客户端 SDK、部分 v1/v2 文档一致性仍需收敛 |
| Docker 容器化 | P2 | ✅ 已完成 | 90% | 根目录 `Dockerfile` 多阶段镜像；`docker-compose.yml` API/Frontend/Redis；`frontend/Dockerfile`；`deploy/k8s/` | 镜像发布流水线、Helm Chart、生产 secrets/volumes 标准化 |
| 配置加密 | P2 | ✅ 已完成 | 80% | `src/core/security.py` `SecurityManager.encrypt/decrypt`；`src/core/vault.py` `LocalFileVault` 加密 JSON；`tests/test_v5_security_compliance.py` 覆盖 | 外部 KMS/Vault 托管、全配置文件透明加密、数据库静态加密 |
| Web 前端 | P3 | ✅ 已完成 | 85% | `frontend/` Vue3 + Vite + Element Plus；`src/platform/web/` legacy 控制台；`api_v2` 可托管 `frontend/dist` | 在线策略 IDE、移动端/PWA、复杂组合分析和工作流可视化 |
| 微服务架构 | P3 | 🟡 部分完成 | 35% | `src/platform/` 模块化服务层；Compose 拆分 API/Frontend/Redis；Repository/MessageBus/JobQueue 抽象 | 尚未拆为独立 backtest/data/trading/ml 服务；缺少跨服务 gRPC/消息总线部署、服务发现、独立伸缩 |
| 分布式回测 | P3 | 🟡 大部分完成 | 75% | `src/platform/distributed.py` LocalProcessPool/Ray/Dask；`src/platform/backtest_task.py`；`run_distributed_backtests()` | Ray/Dask 集群部署模板、大规模容量基准、任务数据分片与结果归并治理 |

## 分项说明

### P2：中期规划

- **REST API 实现**：已从早期 HTTP API 演进到 FastAPI v2。当前 `api_v2` 提供健康检查、指标、策略、回测同步运行、回测异步 job、交易网关、监控和 demo 端点，并暴露 OpenAPI 文档。
- **Docker 容器化**：已具备生产镜像、前端镜像和 Compose 栈。根目录生产镜像会构建 Vue 前端并由 API 容器托管静态文件，Compose 也保留 API + Frontend 双服务模式。
- **配置加密**：已有安全管理器和本地加密 vault。当前更准确的表述是“密钥/敏感配置加密能力已实现”，不是“全配置文件透明加密已完成”。

### P3：长期规划

- **Web 前端**：已不再只是规划项。Vue3 SPA 覆盖 Dashboard、Backtest、Trading、Strategies、Data、Monitor、Settings 等页面，旧版 `src/platform/web/` 仍作为轻量控制台存在。
- **微服务架构**：当前是模块化单体 + 容器编排，并非完整微服务。适合继续演进，但不能标记为已完成。
- **分布式回测**：已有本地进程池和 Ray/Dask 适配器，满足框架级并行/分布式入口；生产集群化仍需补齐部署和容量验证。

## 文档同步原则

- 路线图中不再把 P2 三项列为未开始。
- 微服务仍保留为长期规划，状态标注为“部分完成”。
- 分布式回测使用“双层状态”：框架能力已完成，生产集群化未完成。
- 安全文档中区分 `SecurityManager`/`Vault` 已实现与 KMS/数据库静态加密未实现。
