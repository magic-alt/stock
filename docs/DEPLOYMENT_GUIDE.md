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

# 实盘交易模式（需要确认）
CONFIRM_LIVE_TRADING=1 python scripts/start_production.py --mode live
```

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
