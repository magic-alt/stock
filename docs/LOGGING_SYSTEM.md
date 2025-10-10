# 日志系统配置说明 (V2.2.3)

## 🎯 优化目标

### 问题
网络错误时控制台被日志信息淹没：
```
⚠ 网络异常，无法刷新数据: ...
刷新缓存失败: ...，保留旧缓存  ← logger.warning() 重复输出
刷新缓存失败: ...，保留旧缓存
... (重复多次)
```

### 解决方案
**分层日志策略：**
- ✅ **控制台**：只显示用户友好信息（`print()`）和严重错误（`ERROR`）
- ✅ **日志文件**：记录所有 WARNING 及以上级别，供调试使用

---

## 📋 配置详情

### main.py 日志配置

```python
import logging

# 配置日志系统
logging.basicConfig(
    level=logging.WARNING,           # 文件记录WARNING及以上
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

### 日志级别映射

| 级别 | 控制台 | 文件 | 用途 |
|------|--------|------|------|
| **DEBUG** | ❌ | ❌ | 开发调试（需手动开启）|
| **INFO** | ❌ | ❌ | 信息记录 |
| **WARNING** | ❌ | ✅ | 警告信息（如网络错误）|
| **ERROR** | ✅ | ✅ | 错误信息（需要关注）|
| **CRITICAL** | ✅ | ✅ | 严重错误 |

---

## 🔧 代码实现

### 数据源层（akshare_source.py）

```python
except Exception as e:
    # 60秒去重检查
    should_print = True
    if self._last_error_time:
        time_since_error = (now - self._last_error_time).total_seconds()
        should_print = time_since_error > 60
    
    if should_print:
        # 用户友好提示（显示在控制台）
        print(f"⚠ 网络异常，无法刷新数据: {e}")
        if self._cache_time:
            cache_age_min = int(cache_age / 60)
            print(f"  继续使用旧缓存（缓存年龄: {cache_age_min}分钟）")
        
        # 详细日志（写入文件，不显示在控制台）
        logger.warning(f"刷新缓存失败: {e}，保留旧缓存")
        
        self._last_error_time = now
```

**优势：**
- ✅ `print()` - 用户看到友好提示
- ✅ `logger.warning()` - 开发者查看详细日志（在文件中）
- ✅ 去重机制 - 60秒内只输出一次

---

## 📊 效果对比

### 优化前 ❌
```
⚠ 网络异常，无法刷新数据: ('Connection aborted.', ...)
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
... (重复17次)
```

### 优化后 ✅
**控制台（用户视角）：**
```
【主要指数】
  交易状态: 午间休市

⚠ 网络异常，无法刷新数据: ('Connection aborted.', ...)
  继续使用旧缓存（缓存年龄: 5分钟）

  ⚠ 网络连接异常，无法获取实时数据
  提示: 检查网络连接或稍后重试
```

**日志文件（开发者视角）：**
```
2025-10-10 11:48:22 - src.data_sources.akshare_source - WARNING - 刷新缓存失败: ('Connection aborted.', ...), 保留旧缓存
2025-10-10 11:48:22 - src.data_sources.akshare_source - ERROR - ⚠ 缓存已过期 300秒（超过5倍TTL），可能存在网络问题
```

---

## 🛠 使用方式

### 查看实时日志（开发调试）

**PowerShell：**
```powershell
# 实时查看日志
Get-Content monitor.log -Wait -Tail 20

# 搜索错误
Select-String -Path monitor.log -Pattern "ERROR"

# 查看今天的日志
Get-Content monitor.log | Select-String (Get-Date -Format "yyyy-MM-dd")
```

**Linux/Mac：**
```bash
# 实时查看日志
tail -f monitor.log

# 搜索错误
grep ERROR monitor.log

# 查看最后100行
tail -n 100 monitor.log
```

### 调整日志级别

#### 临时开启详细日志（调试）
修改 `main.py`：
```python
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG
    # ...
)
console.setLevel(logging.DEBUG)  # 控制台也显示详细信息
```

#### 完全禁用文件日志
```python
logging.basicConfig(
    level=logging.ERROR,  # 只记录ERROR
    handlers=[
        logging.FileHandler('monitor.log', encoding='utf-8'),
    ]
)
```

---

## 📁 日志文件管理

### 文件位置
```
D:\Project\data\
├── monitor.log          # 主程序日志
├── test_monitor.log     # 测试日志
└── backtest.log         # 回测日志（未来）
```

### 日志轮转（推荐）

对于长期运行，建议使用 `RotatingFileHandler`：

```python
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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

这样日志会自动切割：
- `monitor.log` - 当前日志
- `monitor.log.1` - 上一次日志
- `monitor.log.2` - 更早的日志
- ...

---

## 🔍 调试技巧

### 问题排查流程

1. **查看控制台输出** - 用户友好提示
2. **检查日志文件** - 详细技术信息
3. **搜索关键字** - 快速定位问题

### 常见场景

#### 网络连接问题
```bash
# 搜索网络错误
grep "Connection aborted" monitor.log
```

#### 数据异常
```bash
# 搜索NaN相关错误
grep -i "nan\|none" monitor.log
```

#### 性能问题
```bash
# 搜索缓存相关信息
grep "缓存" monitor.log
```

---

## 📌 最佳实践

### 开发阶段
- ✅ 控制台 DEBUG 级别 - 查看所有细节
- ✅ 文件记录完整日志
- ✅ 频繁查看日志文件

### 生产环境
- ✅ 控制台 ERROR 级别 - 保持清爽
- ✅ 文件 WARNING 级别 - 记录异常
- ✅ 定期清理旧日志

### 用户使用
- ✅ 控制台输出友好 - 易于理解
- ✅ 不需要关心日志文件
- ✅ 出问题时提供日志文件给开发者

---

## 🎯 关键改进

| 方面 | 优化前 | 优化后 |
|------|--------|--------|
| **控制台输出** | 17条技术错误 | 1条友好提示 |
| **用户体验** | 混乱 | 清爽 |
| **调试信息** | 丢失 | 完整保留 |
| **日志管理** | 无 | 文件记录 |
| **错误去重** | 无 | 60秒去重 |

---

**优化版本：** V2.2.3  
**优化日期：** 2025-10-10  
**核心改进：** 分层日志 + 错误去重 + 友好提示
