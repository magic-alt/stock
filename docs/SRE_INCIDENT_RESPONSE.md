# SRE Incident Response

## 指标与告警
- `platform_api_requests_total`
- `platform_api_requests_by_status_total`
- `platform_job_queue_pending_jobs`
- `platform_job_queue_failed_jobs`
- `platform_job_queue_delay_ms_p95`
- `platform_job_queue_run_ms_p95`

建议阈值：
- 5xx 占比 > 1% 持续 5 分钟。
- pending jobs > 100 持续 10 分钟。
- queue delay p95 > 5000ms 持续 10 分钟。

## 事件分级
- P1：核心交易/回测服务不可用。
- P2：功能降级但可服务。
- P3：非核心功能异常。

## 处置流程
1. 收敛影响面：确认 API、作业、审计三个平面状态。
2. 快速缓解：限流、扩容 worker、必要时回滚版本。
3. 数据校验：检查 `jobs.db` 状态一致性和审计日志完整性。
4. 根因定位：日志 + 指标 + 最近变更。
5. 复盘闭环：24 小时内提交 RCA。

## 常用命令
```bash
python -m pytest tests -v
python scripts/audit_integrity_check.py --path ./logs/platform_api_audit.log --strict --json
python scripts/benchmark_platform.py --jobs 200 --workers 8 --sleep-ms 10
```
