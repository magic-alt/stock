# 🔧 "保留旧缓存" 日志重复问题 - 完全解决方案

## 问题现象

```
⚠ 网络异常，无法刷新数据: ('Connection aborted.', ...)
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存  ← 重复17次
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
...
```

## 根本原因

### 原因1：每个股票调用一次
- 监控器循环查询每个股票/指数
- 每次调用 `get_stock_realtime()` 都触发 `_refresh_spot_cache()`
- 网络错误时，每个股票都打印一次错误

### 原因2：logger 默认输出到控制台
- Python 的 `logging.warning()` 默认输出到控制台
- 即使添加了 `print()` 去重，logger 仍然每次输出
- 用户看到双重错误信息（print + logger）

---

## 完整解决方案 (V2.2.3)

### 修复1：错误去重机制 ✅
**文件：** `src/data_sources/akshare_source.py`

```python
def _refresh_spot_cache(self):
    # ...
    except Exception as e:
        # 60秒去重检查
        should_print = True
        if self._last_error_time:
            time_since_error = (now - self._last_error_time).total_seconds()
            should_print = time_since_error > 60
        
        if should_print:
            # 用户友好提示 (print)
            print(f"⚠ 网络异常，无法刷新数据: {e}")
            
            # 详细日志 (logger) - 同样去重
            logger.warning(f"刷新缓存失败: {e}，保留旧缓存")
            
            self._last_error_time = now
```

### 修复2：日志分层 ✅
**文件：** `main.py`

```python
import logging

# 配置日志：WARNING写入文件，ERROR显示在控制台
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log', encoding='utf-8'),
    ]
)

# 控制台只显示ERROR级别
console = logging.StreamHandler()
console.setLevel(logging.ERROR)
logging.getLogger('').addHandler(console)
```

---

## 效果对比

### 修复前 ❌

**控制台输出：**
```
⚠ 网络异常，无法刷新数据: ...
刷新缓存失败: ...，保留旧缓存
刷新缓存失败: ...，保留旧缓存
刷新缓存失败: ...，保留旧缓存
[重复17次，刷屏]
```

### 修复后 ✅

**控制台输出（用户视角）：**
```
【主要指数】
  交易状态: 午间休市

⚠ 网络异常，无法刷新数据: ('Connection aborted.', ...)
  继续使用旧缓存（缓存年龄: 5分钟）

  ⚠ 网络连接异常，无法获取实时数据
  提示: 检查网络连接或稍后重试

【自选股票】
  ⚠ 网络连接异常，无法获取实时数据
  提示: 检查网络连接或稍后重试
```

**日志文件（开发者视角）：**
```
2025-10-10 11:48:22 - src.data_sources.akshare_source - WARNING - 刷新缓存失败: ('Connection aborted.', ...), 保留旧缓存
2025-10-10 11:48:22 - src.data_sources.akshare_source - ERROR - ⚠ 缓存已过期 300秒（超过5倍TTL）
```

---

## 关键改进

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| **控制台错误行数** | 17行 | 1行 |
| **错误重复频率** | 每次调用 | 60秒/次 |
| **用户体验** | 刷屏 | 清爽 |
| **调试信息** | 丢失 | 文件保留 |
| **日志管理** | 无 | 分层管理 |

---

## 应用更新

### ⚠️ 重要：必须重启进程

**为什么？**
- Python 进程缓存了已导入的模块
- `main.py` 的日志配置只在启动时执行一次
- 必须重启才能应用新配置

### 步骤

1. **退出当前程序**
   ```
   按 Ctrl+C
   ```

2. **关闭终端窗口**
   - 完全关闭当前 PowerShell/CMD 窗口

3. **打开新终端**
   ```powershell
   conda activate base
   cd D:\Project\data
   ```

4. **重新运行**
   ```powershell
   python main.py
   # 或使用
   python start_monitor.py
   ```

---

## 验证修复

### 运行测试脚本
```powershell
python test_logging_config.py
```

**预期输出：**
- ✅ 控制台只显示1条友好提示
- ✅ logger.warning() 不在控制台显示
- ✅ 详细日志写入 `test_monitor.log`

### 查看日志文件
```powershell
# 查看最新日志
Get-Content monitor.log -Tail 20

# 实时监控日志
Get-Content monitor.log -Wait -Tail 20

# 搜索错误
Select-String -Path monitor.log -Pattern "ERROR"
```

---

## 技术细节

### 日志级别流程

```
异常发生
    ↓
[60秒去重检查]
    ↓
should_print = True?
    ├─ Yes → print() → 控制台 ✓
    │         logger.warning() → 文件 ✓
    └─ No  → 静默处理 (无输出)
```

### 日志系统架构

```
用户层 (控制台)
    ├─ print() 友好提示
    └─ logger.error() 严重错误
    
开发层 (文件)
    ├─ logger.warning() 警告信息
    ├─ logger.error() 错误信息
    └─ logger.critical() 严重错误
```

---

## 扩展功能

### 日志轮转（可选）

如果长期运行，建议添加日志轮转：

```python
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    handlers=[
        RotatingFileHandler(
            'monitor.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,           # 保留5个备份
            encoding='utf-8'
        )
    ]
)
```

### 自定义日志格式

```python
logging.basicConfig(
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

---

## 相关文档

- `docs/LOGGING_SYSTEM.md` - 日志系统详细文档
- `docs/OPTIMIZE_ERROR_LOGGING.md` - 错误日志优化说明
- `CHANGELOG.md` - 版本更新历史
- `test_logging_config.py` - 日志配置测试脚本

---

**修复版本：** V2.2.3  
**最终修复：** 2025-10-10  
**核心改进：** 错误去重 + 日志分层 + 友好提示  
**状态：** ✅ 完全解决
