# 快速部署指南

## 🚀 5分钟快速部署

### Windows用户

1. **安装Python**
   ```powershell
   # 下载并安装Python 3.8+ from python.org
   python --version
   ```

2. **克隆项目**
   ```powershell
   git clone <repository-url>
   cd stock
   ```

3. **安装依赖**
   ```powershell
   pip install -r requirements.txt
   ```

4. **配置系统**
   ```powershell
   # 复制配置模板
   copy config.yaml.example config.yaml
   # 编辑配置文件（可选）
   notepad config.yaml
   ```

5. **启动系统**
   ```powershell
   # 方式1: 使用批处理脚本（推荐）
   scripts\start_production.bat

   # 方式2: 使用Python脚本
   python scripts\start_production.py
   ```

### Linux/Mac用户

1. **安装Python**
   ```bash
   python3 --version
   # 如果没有，安装: sudo apt install python3 python3-pip  # Ubuntu
   ```

2. **克隆项目**
   ```bash
   git clone <repository-url>
   cd stock
   ```

3. **安装依赖**
   ```bash
   pip3 install -r requirements.txt
   ```

4. **配置系统**
   ```bash
   # 复制配置模板
   cp config.yaml.example config.yaml
   # 编辑配置文件（可选）
   nano config.yaml
   ```

5. **启动系统**
   ```bash
   # 方式1: 使用Shell脚本（推荐）
   chmod +x scripts/start_production.sh
   ./scripts/start_production.sh

   # 方式2: 使用Python脚本
   python3 scripts/start_production.py
   ```

---

## ✅ 验证部署

### 1. 健康检查

```bash
# Windows
python scripts\health_check.py

# Linux/Mac
python3 scripts/health_check.py
```

预期输出：
```
✓ [通过] directories
✓ [通过] database
✓ [通过] dependencies
✓ [通过] data_providers
✓ [通过] disk_space
✓ [通过] log_files

总计: 6 | 通过: 6 | 失败: 0
```

### 2. 运行示例回测

```bash
# Windows
python unified_backtest_framework.py run --strategy macd --symbols 600519.SH --start 2023-01-01 --end 2024-12-31 --plot

# Linux/Mac
python3 unified_backtest_framework.py run --strategy macd --symbols 600519.SH --start 2023-01-01 --end 2024-12-31 --plot
```

### 3. 检查日志

```bash
# Windows
type logs\quant.log

# Linux/Mac
cat logs/quant.log
```

---

## 🔧 常见问题

### Q: 健康检查失败怎么办？

**A**: 检查以下项目：

1. **目录不存在**
   ```bash
   # 手动创建目录
   mkdir cache logs reports
   ```

2. **数据库不存在**
   ```bash
   # 运行一次回测会自动创建数据库
   python unified_backtest_framework.py run --strategy macd --symbols 600519.SH --start 2023-01-01 --end 2023-12-31
   ```

3. **依赖缺失**
   ```bash
   pip install -r requirements.txt
   ```

### Q: 如何配置数据源？

**A**: 编辑 `config.yaml`:

```yaml
data:
  provider: akshare  # 或 yfinance, tushare
  cache_dir: ./cache
```

### Q: 如何设置日志级别？

**A**: 编辑 `config.yaml`:

```yaml
logging:
  level: DEBUG  # DEBUG, INFO, WARNING, ERROR
```

或在启动时指定：

```bash
python scripts/start_production.py --log-level DEBUG
```

---

## 📚 下一步

- 阅读 [完整部署指南](DEPLOYMENT_GUIDE.md)
- 查看 [架构审查报告](ARCHITECTURE_REVIEW.md)
- 学习 [用户手册](../README.md)

---

**需要帮助？** 查看 [故障排查指南](DEPLOYMENT_GUIDE.md#故障排查)
