# Operations Runbook

## 1. 灰度发布流程
1. 在预发环境运行 `python -m pytest tests -v`。
2. 启动新版本 API：
   `python scripts/run_platform_api.py --jobs ./cache/platform/jobs.db --api-token $TOKEN`。
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
