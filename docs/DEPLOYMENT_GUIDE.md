# 部署指南 | Deployment Guide

本文档提供量化交易系统的完整部署指南，适用于生产环境部署。

## 📋 目录

- [系统要求](#系统要求)
- [快速部署](#快速部署)
- [配置管理](#配置管理)
- [数据库管理](#数据库管理)
- [监控与运维](#监控与运维)
- [故障排查](#故障排查)
- [安全建议](#安全建议)

---

## 🖥️ 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2核心 | 4核心+ |
| 内存 | 4GB | 8GB+ |
| 磁盘 | 10GB | 50GB+ |
| 网络 | 10Mbps | 100Mbps+ |

### 软件要求

- **操作系统**: Windows 10+, Linux (Ubuntu 20.04+), macOS 10.15+
- **Python**: 3.8+
- **数据库**: SQLite3 (内置)

### Python依赖

```bash
pip install -r requirements.txt
```

核心依赖：
- pandas >= 2.0.0
- numpy >= 1.24.0
- backtrader >= 1.9.76
- akshare >= 1.12.0
- matplotlib >= 3.5.0

---

## 🚀 快速部署

### Docker Compose 生产部署

推荐使用仓库内置的 Docker Compose 栈发布：

```bash
python scripts/deploy_release.py
```

默认会完成以下动作：

1. 构建 API 与前端镜像
2. 启动 `api`、`frontend`、`redis` 服务
3. 等待 `http://127.0.0.1:8000/api/v2/health` 和 `http://127.0.0.1:3000` 健康检查通过

停止部署：

```bash
python scripts/deploy_release.py --down
```

## 🚦 上线决策闸门（Decision Gate）

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

该命令不算失败，表示你要补齐前置 dependencies 后再重跑。

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

### 4) 推荐命令（可直接用于发布前执行）

```bash
python scripts/start_production.py --preflight --preflight-decision-only \
  --preflight-platform-run \
  --preflight-platform-limit 5 \
  --preflight-auto-regression \
  --preflight-auto-rounds 3 \
  --preflight-decision-seed-file report/preflight_decision_latest.json \
  --preflight-use-best \
  --preflight-fail-on-review \
  --preflight-decision-file report/preflight_release_gate.json
```

命令说明：
- `--preflight-decision-only`：仅执行预检并输出 `release_decision`，不启动交易服务。
- `--preflight-platform-run`：启用候选参数实验平台化复测。
- `--preflight-platform-limit 5`：平台化复测候选上限（含 base + 4 个候选）。
- `--preflight-auto-regression`：review 决策时自动回放上轮 `release_decision` 并发起下一轮预检。
- `--preflight-auto-rounds 3`：单次闸门最大复测轮次（默认 3）。
- `--preflight-use-best`：用平台最优参数复跑一次作为最终决策依据。
- `--preflight-fail-on-review`：在策略评分为 `review` 时让命令返回非 0，支持严格 CI 阻断。
- `--preflight-decision-file`：将结构化决策落盘，便于后续审计与回放。
- `--preflight-decision-seed-file`：读取上轮 `release_decision.recommended_replay.params`，无显式 `--preflight-params` 时回填为本轮参数。

`local_ci.ps1` 的 `preflight-gate` 会将闸门决策写入 `report/preflight_gate.json`，并更新 `report/preflight_decision_latest.json`，实现“决策 -> 写入 -> 下一轮回填”的闭环。

本地 CI 可直接接入该闸门：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs preflight-gate
```

若发布流水线要同时执行打包发布与闸门，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_ci.ps1 -Jobs release
```

可选环境变量：

```bash
PLATFORM_API_TOKEN=your_token
TUSHARE_TOKEN=your_tushare_token
```

### 单服务发布模式

`api_v2` 现在支持在生产态直接托管 `frontend/dist`，适合没有 Docker 的机器或单实例云主机：

```bash
cd frontend
npm ci
npm run build
cd ..

python -m uvicorn src.platform.api_v2:app --host 0.0.0.0 --port 8000
```

发布后统一从 `http://127.0.0.1:8000` 访问：

- Web 控制台：`http://127.0.0.1:8000/`
- API 健康检查：`http://127.0.0.1:8000/api/v2/health`
- API 文档：`http://127.0.0.1:8000/api/v2/docs`

可选环境变量：

```bash
PLATFORM_FRONTEND_DIST=frontend/dist
PLATFORM_ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend.example.com
```

### Render Blueprint 部署

仓库根目录新增 `render.yaml`，可以直接作为 Render Blueprint 使用。该方案会使用根目录 `Dockerfile` 构建单服务镜像，并把前端静态文件打包进 API 容器。

发布步骤：

```bash
git add render.yaml Dockerfile
git commit -m "feat(deploy): add render blueprint"
git push origin main
```

打开 Render Blueprint 入口：

`https://dashboard.render.com/blueprint/new?repo=https://github.com/magic-alt/stock`

创建时补充以下密钥：

- `PLATFORM_API_TOKEN`
- `TUSHARE_TOKEN`

### 1. 克隆项目

```bash
git clone <repository-url>
cd stock
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置系统

```bash
# 复制配置模板
cp config.yaml.example config.yaml

# 编辑配置文件
# Windows: notepad config.yaml
# Linux/Mac: nano config.yaml
```

### 4. 初始化目录

```bash
python -c "from src.core.defaults import ensure_directories; ensure_directories()"
```

### 5. 健康检查

```bash
python scripts/health_check.py
```

### 6. 启动系统

```bash
# 回测模式（默认）
python scripts/start_production.py

# 模拟交易模式
python scripts/start_production.py --mode paper

# 实盘交易模式（已实现，需显式确认）
CONFIRM_LIVE_TRADING=1 python scripts/start_production.py --mode live
```

### 7. Web 控制台

生产部署默认暴露：

- 前端控制台：`http://127.0.0.1:3000`
- API 健康检查：`http://127.0.0.1:8000/api/v2/health`
- API 文档：`http://127.0.0.1:8000/api/v2/docs`

单服务发布模式暴露：

- 统一入口：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/health`
- 指标接口：`http://127.0.0.1:8000/metrics`

网页端能力包括：

- 回测配置与结果查看
- 网关连接、下单、撤单、paper 行情注入
- 系统监控、任务列表、告警、账户/持仓/订单/成交查看

---

## ⚙️ 配置管理

### 配置文件位置

系统按以下顺序查找配置文件：

1. `--config` 参数指定的路径
2. `config.yaml` (项目根目录)
3. `config/config.yaml`
4. `~/.backtest/config.yaml`
5. 默认配置

### 环境变量

可以通过环境变量覆盖配置：

```bash
# Windows PowerShell
$env:BACKTEST_DATA_PROVIDER="akshare"
$env:BACKTEST_BACKTEST_CASH="300000"
$env:BACKTEST_LOG_LEVEL="DEBUG"

# Linux/Mac
export BACKTEST_DATA_PROVIDER=akshare
export BACKTEST_BACKTEST_CASH=300000
export BACKTEST_LOG_LEVEL=DEBUG
```

### 配置验证

```python
from src.core.config import ConfigManager

# 加载配置
config = ConfigManager.load_from_file("config.yaml")

# 验证配置
print(config.backtest.initial_cash)
print(config.data.provider)
```

---

## 💾 数据库管理

### 数据库位置

默认位置：`./cache/market_data.db`

### 备份

```bash
# 手动备份
python scripts/backup_database.py

# 压缩备份
python scripts/backup_database.py --compress

# 查看备份统计
python scripts/backup_database.py --stats
```

### 自动备份

#### Windows (任务计划程序)

创建 `backup_task.bat`:

```batch
@echo off
cd /d E:\work\Project\stock
python scripts\backup_database.py --compress --retention-days 30
```

在任务计划程序中设置每日执行。

#### Linux (Cron)

```bash
# 编辑crontab
crontab -e

# 添加每日凌晨2点备份
0 2 * * * cd /path/to/stock && python scripts/backup_database.py --compress --retention-days 30 >> /var/log/backup.log 2>&1
```

### 数据库迁移

如果数据库结构变更，系统会自动迁移：

```python
from src.data_sources.db_manager import SQLiteDataManager

db = SQLiteDataManager("./cache/market_data.db")
# 自动检测并执行迁移
```

### 数据库优化

```python
from src.data_sources.db_manager import SQLiteDataManager

db = SQLiteDataManager("./cache/market_data.db")
db.vacuum()  # 优化数据库，回收空间
```

---

## 📊 监控与运维

### 健康检查

```bash
# 基本检查
python scripts/health_check.py

# JSON格式（用于监控系统集成）
python scripts/health_check.py --json

# 返回退出码（用于脚本集成）
python scripts/health_check.py --exit-code
```

### 日志管理

日志位置：`./logs/quant.log`

日志级别：
- `DEBUG`: 详细调试信息
- `INFO`: 一般信息（生产环境推荐）
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误

日志轮转：
- 大小：10MB
- 保留：5个文件

### 性能监控

关键指标：

1. **数据加载时间**
   ```python
   # 监控数据加载性能
   import time
   start = time.time()
   # ... 数据加载 ...
   logger.info(f"Data loaded in {time.time() - start:.2f}s")
   ```

2. **回测执行时间**
   ```python
   # 监控回测性能
   from src.backtest.engine import BacktestEngine
   engine = BacktestEngine()
   # ... 回测 ...
   ```

3. **数据库大小**
   ```bash
   python scripts/backup_database.py --stats
   ```

### 告警配置

在 `config.yaml` 中配置：

```yaml
monitoring:
  enabled: true
  health_check_interval: 60
  alert_email: "admin@example.com"
```

---

## 🔧 故障排查

### 常见问题

#### 1. 数据库连接失败

**症状**: `sqlite3.OperationalError: database is locked`

**解决方案**:
```bash
# 检查是否有其他进程占用
# Windows
tasklist | findstr python

# Linux
ps aux | grep python

# 重启系统或关闭占用进程
```

#### 2. 数据源不可用

**症状**: `DataProviderUnavailable`

**解决方案**:
```bash
# 检查网络连接
ping api.fund.eastmoney.com

# 检查AKShare版本
pip install --upgrade akshare

# 尝试其他数据源
# 修改 config.yaml 中的 provider
```

#### 3. 内存不足

**症状**: `MemoryError`

**解决方案**:
- 减少并行工作进程数 (`max_workers`)
- 减少回测数据范围
- 增加系统内存

#### 4. 磁盘空间不足

**症状**: `OSError: No space left on device`

**解决方案**:
```bash
# 清理旧备份
python scripts/backup_database.py --retention-days 7

# 清理缓存
rm -rf cache/*.csv  # 保留数据库文件

# 数据库优化
python -c "from src.data_sources.db_manager import SQLiteDataManager; SQLiteDataManager().vacuum()"
```

### 日志分析

```bash
# 查看错误日志
grep ERROR logs/quant.log

# 查看最近的日志
tail -n 100 logs/quant.log

# 查看特定时间段的日志
grep "2024-12-12" logs/quant.log
```

---

## 🔒 安全建议

### 1. 配置文件安全

- ✅ 不要将包含敏感信息的 `config.yaml` 提交到版本控制
- ✅ 使用环境变量存储敏感配置（如API密钥）
- ✅ 设置适当的文件权限（Linux: `chmod 600 config.yaml`）

### 2. 数据库安全

- ✅ 定期备份数据库
- ✅ 备份文件加密存储
- ✅ 限制数据库文件访问权限

### 3. 实盘交易安全

- ✅ 使用测试环境验证策略
- ✅ 设置严格的风控参数
- ✅ 启用交易日志审计
- ✅ 使用独立的交易账户（小资金测试）

### 4. 网络安全

- ✅ 使用HTTPS连接数据源
- ✅ 配置防火墙规则
- ✅ 定期更新依赖包

---

## 📝 部署检查清单

### 部署前

- [ ] 系统要求满足
- [ ] Python环境配置完成
- [ ] 依赖包安装完成
- [ ] 配置文件创建和验证
- [ ] 目录结构初始化
- [ ] 健康检查通过

### 部署后

- [ ] 系统启动成功
- [ ] 日志正常输出
- [ ] 数据源连接正常
- [ ] 数据库可读写
- [ ] 备份任务配置完成
- [ ] 监控告警配置完成

### 定期维护

- [ ] 每日检查日志
- [ ] 每周备份数据库
- [ ] 每月清理旧数据
- [ ] 每季度更新依赖包
- [ ] 每年审查安全配置

---

## 📚 相关文档

- [用户手册](USER_GUIDE.md)
- [API文档](API_DOCUMENTATION.md)
- [策略开发指南](STRATEGY_DEVELOPMENT.md)
- [故障排查指南](TROUBLESHOOTING.md)

---

## 🤝 获取帮助

如遇到问题，请：

1. 查看本文档的故障排查部分
2. 检查日志文件
3. 运行健康检查脚本
4. 提交Issue到项目仓库

---

**最后更新**: 2025-12-12  
**维护者**: Quantitative Trading Team
