# Scripts - 辅助脚本

本目录包含 GUI、平台 API 与运维辅助脚本。

## 文件列表

### `backtest_gui.py`
图形化回测入口。

```bash
python scripts/backtest_gui.py
```

### `run_platform_api.py`
启动平台 API 服务（支持 v1 鉴权、JSON/SQLite 作业存储、可选审计日志）。

```bash
python scripts/run_platform_api.py --host 127.0.0.1 --port 8080 \
  --jobs ./cache/platform/jobs.db \
  --api-token your_token \
  --audit-log ./logs/platform_api_audit.log
```

### `audit_integrity_check.py`
审计日志完整性巡检（hash 链校验，支持新鲜度检查）。

```bash
python scripts/audit_integrity_check.py --path ./logs/platform_api_audit.log --json
```

### `benchmark_platform.py`
平台任务队列压测脚本，生成吞吐与延迟基线。

```bash
python scripts/benchmark_platform.py --jobs 200 --workers 8 --sleep-ms 10 --out report/bench/platform.json
```

### `health_check.py`
本地部署健康检查。

### `backup_database.py`
数据库备份工具。

## 输出路径
- 回测报告：`report/`
- 运行缓存：`cache/`
- 日志：`logs/`

## 相关文档
- `docs/COMMERCIAL_UPGRADE_ROADMAP.md`
- `docs/SECURITY_BASELINE.md`
- `docs/PERFORMANCE_BENCHMARK_SPEC.md`
