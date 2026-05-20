# Operations Runbook

## 1. 灰度发布流程
1. 在预发环境运行 `python -m pytest tests -v`。
2. 启动新版本 API：
   `PLATFORM_API_TOKEN=$TOKEN PLATFORM_JOB_STORE=./cache/platform/jobs.db python -m uvicorn src.platform.api_v2:app --host 0.0.0.0 --port 8000`。
3. 先将 10% 流量切换到新实例，观察 15 分钟。
4. 关键指标通过后扩到 50%，再扩到 100%。

## 2. 回滚流程
1. 触发条件：
   - `platform_api_requests_by_status_total{status="5xx"}` 快速上升。
   - `platform_job_queue_failed_jobs` 连续增长超过阈值。
2. 操作步骤：
   - 切回旧版本实例。
   - 保留当前 `jobs.db` 与审计日志。
   - 执行 `python scripts/audit_integrity_check.py --path ./logs/platform_api_audit.log --strict`。
3. 回滚后复盘：记录故障窗口、影响范围、根因与修复计划。

## 3. 故障演练
- 演练频率：每月 1 次。
- 场景：
  - 作业队列拥塞
  - API 鉴权配置错误
  - 审计日志链断裂
- 演练输出：恢复时间、误报率、改进项。

## 4. 数据与日志保留
- `jobs.db`：建议每日快照，保留 30 天。
- 审计日志：建议保留 180 天，并定期归档。
- 压测报告：每周保留一个基线版本。

## 5. 生产能力运行配置
- 任务队列：`PLATFORM_JOB_STORE` 支持 `./cache/platform/jobs.json`、`sqlite:///...`、`redis://...`、`postgresql://...`。生产环境建议使用 Redis/Postgres，并设置 `PLATFORM_JOB_STORE_FALLBACK=false`，避免队列服务异常时静默降级到本地 JSON。
- 指标与追踪：`/api/v2/metrics?format=prometheus` 输出 API、JobQueue 和 MetricCollector 指标；API 响应会回传 `X-Request-ID` 与 `X-Trace-ID`。需要外部追踪时配置 `monitoring.otlp_endpoint` 指向 OpenTelemetry Collector HTTP endpoint。
- 数据湖门禁：Parquet 数据集 promotion 会执行 checksum、schema、缺失率、索引和 OHLC 校验。质量门禁失败时不得标记为 production，应先修复上游数据源或重新落盘版本。
- Level2 行情：`data.level2.provider` 可选 `stub`、`xtp`、`hundsun`、`qmt`。真实 provider 需要券商 Level2 权限和 SDK 路径；本地/CI 使用 `stub` 固定 payload 验证 10 档盘口与逐笔成交契约。
- 多账户资金分配：通过 `/api/v2/accounts` 管理账户，通过 `/api/v2/portfolio/capital-allocation/preview` 预览账户 × 策略分配矩阵。上线前确认现金缓冲、账户权重上限、策略权重上限和账户风险预算。
