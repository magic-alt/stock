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

### `deploy_release.py`
使用 Docker Compose 构建并启动生产栈，自动等待 API 与前端健康检查通过。

```bash
python scripts/deploy_release.py
python scripts/deploy_release.py --skip-build
python scripts/deploy_release.py --down
```

### `start_production.py`
生产启动与上线预检入口，包含策略上线决策与自动实验复测能力。

```bash
python scripts/start_production.py --preflight --preflight-decision-only \
  --preflight-platform-run \
  --preflight-platform-limit 5 \
  --preflight-auto-regression \
  --preflight-auto-rounds 2 \
  --preflight-use-best \
  --preflight-fail-on-review \
  --preflight-decision-seed-file report/preflight_decision_latest.json \
  --preflight-decision-file report/preflight_release_gate.json
```

常用参数：
- `--preflight`：开启预检（含回测 + 回放自检 + 风控健康项）
- `--preflight-decision-only`：仅产出 `release_decision`，不启动运行时服务
- `--preflight-platform-run`：启用自动实验平台化复测（参数候选池）
- `--preflight-auto-regression`：当决策为 review 且有 recommended_replay 时自动复测（读取快照）
- `--preflight-auto-rounds`：自动复测最大轮次（默认 3）
- `--preflight-fail-on-review`：将 `review` 决策映射为失败码，便于 CI 闸门
- `--preflight-decision-file`：将决策结果 JSON 落盘
- `--preflight-decision-seed-file`：从上轮决策自动回填 `--preflight-params`（默认 `report/preflight_decision_latest.json`）
- `--preflight-use-best`：平台最优候选复跑后用于最终决策

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

### `local_ci.ps1`
本地一键 CI 自测脚本，按 GitHub Actions job 分段输出（test / code-quality / security-scan / build-docs / performance / integration-test）。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1
```

可选参数：
- `-Jobs test,code-quality`：只运行指定 job。
- `-SkipInstall`：跳过依赖安装步骤（默认会按 job 安装）。
- `-IncludeRelease`：将 `release` job 一并纳入执行。
- `-Jobs runtime-smoke`：执行阶段1运行态冒烟（XTP/UFT stub smoke + realtime_data failover/HTTP provider 测试）。
- `-Jobs gateway-integration`：执行真实 SDK 联调冒烟（XTP/UFT，环境不齐全时会 `skip`）。
- `-Jobs preflight-gate`：执行上线决策闸门（`start_production.py --preflight-decision-only`）。

在上线前先做「决策-only」预检，先给一版可直接执行的标准清单。  
本清单与另一份文档的对应段落保持一致，变更时同步更新两处，避免版本漂移。

### 1) local_ci 全流程触发清单（含 preflight-gate）

1. 做纯闸门预检前置（本地快速验证）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs test,code-quality,security-scan -SkipInstall
```

2. 运行阶段1运行态冒烟（XTP/UFT + realtime_data）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs runtime-smoke -SkipInstall
```

3. 运行真实 SDK 联调冒烟（仅在券商测试环境或联调机上）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs gateway-integration -SkipInstall
```

4. 运行闸门（建议接在三项前置之后）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs test,code-quality,security-scan,preflight-gate -SkipInstall
```

5. 做完整上线预检查（含 `preflight-gate` + release 之前校验）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs test,runtime-smoke,code-quality,security-scan,performance,preflight-gate,release -SkipInstall
```

6. 做“全量本地 CI”（额外含文档、集成测试）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs all -IncludeRelease -SkipInstall
```

7. 观察关键结果（必须看到）

```text
Selected jobs: test, code-quality, security-scan, preflight-gate
[preflight-gate] Run launch preflight decision gate passed
```

如果直接执行 `-Jobs preflight-gate` 而没跑前置，通常会看到：

```text
preflight-gate skipped (needs: test, code-quality, security-scan)
```

`preflight-gate` 在脚本中的固定参数如下：

```text
--preflight --preflight-platform-run --preflight-platform-limit 3
--preflight-auto-regression --preflight-auto-rounds 2 --preflight-use-best
--preflight-decision-only --preflight-fail-on-review
--preflight-decision-file report/preflight_gate.json
--preflight-decision-seed-file report/preflight_decision_latest.json
```

`gateway-integration` 的固定参数如下：

```text
python -m pytest tests/test_gateway_xtp_integration.py tests/test_gateway_uft_integration.py -m integration -v --tb=short -x
```

### 2) `--preflight-decision-seed-file` 主-从轮次闭环清单

标准目标：每次 `review + recommended_replay` 自动回填下一轮的 `--preflight-params`，直到 `approve/block/force_hold` 结束。

1. 准备一次主轮的基线参数

```powershell
python scripts/start_production.py --preflight --preflight-decision-only --preflight-platform-run --preflight-platform-limit 5 --preflight-decision-file report/preflight_gate.json --preflight-decision-seed-file report/preflight_decision_latest.json --preflight-fail-on-review
```

2. 设定自动复测闭环（一行即可）

```powershell
python scripts/start_production.py --preflight --preflight-decision-only --preflight-platform-run --preflight-platform-limit 5 --preflight-auto-regression --preflight-auto-rounds 3 --preflight-decision-file report/preflight_gate.json --preflight-decision-seed-file report/preflight_decision_latest.json --preflight-fail-on-review
```

3. 约定文件行为

`local_ci.ps1` 与闭环任务会将决策写到：

```text
report/preflight_gate.json
```

并将下一轮推荐参数回写到：

```text
report/preflight_decision_latest.json
```

主-从轮次重跑时，必须让系统无显示指定 `--preflight-params`，通过 `--preflight-decision-seed-file` 自动注入：

- 第 1 轮：未带 `--preflight-params`，自动读 `report/preflight_decision_latest.json`。
- 第 2+ 轮：`review + recommended_replay.params` 会被写回该 seed 并作为下一轮参数来源。
- 轮次上限：`--preflight-auto-rounds 3`（可调整）。

4. 观察复测触发日志（必须出现）

```text
Preflight decision round 1/3
Decision round 1 is review and has recommended replay. Starting auto round 2.
Preflight decision round 2/3
```

5. 结束条件与人工介入

- 看到 `approved`、`blocked` 或 `force_hold` 时停止并汇总当前决策文件。
- 看到 `review` 且 `--preflight-auto-regression` 关闭时停止人工复核。
- 看到 `review` 且开启自动复测时，观察达到 `--preflight-auto-rounds` 后仍未转为非 review，则按规则阻断或降级复测策略。

### 3) CI dry-run 输出模板（预期）

```text
Repo root: ...
Selected jobs: test, code-quality, security-scan, preflight-gate
Skip install: True
========================================================================
[JOB] test
...
[JOB] code-quality
...
[JOB] security-scan
...
========================================================================
[JOB] preflight-gate
[preflight-gate] Run launch preflight decision gate
  > python scripts/start_production.py --preflight --preflight-platform-run ...
[preflight-gate] Run launch preflight decision gate passed
========================================================================
Summary
========================================================================
preflight-gate passed
Local CI finished without hard failures.
```

如果仅执行 `-Jobs preflight-gate` 且没跑前置，预期输出片段为：

```text
Selected jobs: preflight-gate
...
[JOB] preflight-gate
preflight-gate skipped (needs: test, code-quality, security-scan)
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
