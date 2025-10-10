# 网络错误日志优化 (V2.2.2)

## 🐛 问题描述

### 症状
实时监控时，网络错误信息重复打印过多：
```
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
刷新缓存失败: ('Connection aborted.', ...)，保留旧缓存
... (重复17次，每个股票/指数都打印一次)
```

### 根本原因
每次调用 `get_stock_realtime()` 或 `get_index_realtime()` 都会触发 `_refresh_spot_cache()`，而网络错误通过 `logger.warning()` 输出到控制台，导致：
- 同一个网络错误被打印多次（每个股票一次）
- 控制台被错误信息淹没
- 用户体验差

---

## ✅ 优化方案

### 1. 错误去重机制

**数据源层**（`src/data_sources/akshare_source.py`）：

```python
class AKShareDataSource(DataSource):
    def __init__(self):
        # ...
        self._last_error_time = None  # 记录上次错误时间
    
    def _refresh_spot_cache(self):
        try:
            # 刷新数据...
            self._last_error_time = None  # 成功后清除
        except Exception as e:
            # 60秒内只打印一次相同错误
            should_print = True
            if self._last_error_time:
                time_since_error = (now - self._last_error_time).total_seconds()
                should_print = time_since_error > 60
            
            if should_print:
                print(f"⚠ 网络异常，无法刷新数据: {e}")
                if self._cache_time:
                    cache_age_min = int(cache_age / 60)
                    print(f"  继续使用旧缓存（缓存年龄: {cache_age_min}分钟）")
                self._last_error_time = now
```

**优势：**
- ✅ 相同错误60秒内只打印一次
- ✅ 显示缓存年龄（分钟），便于判断数据新鲜度
- ✅ 保留日志记录（logger），便于调试

---

### 2. 友好的错误提示

**监控器层**（`src/monitors/realtime_monitor.py`）：

```python
def display_indices(self):
    has_data = False
    error_count = 0  # 统计错误次数
    
    for code, name in self.indices.items():
        index_data = self.data_source.get_index_realtime(code)
        if index_data and index_data['最新价'] > 0:
            has_data = True
            # 显示数据...
        elif not index_data:
            error_count += 1  # 记录错误
    
    if not has_data:
        if error_count > 0:
            print(f"\n  ⚠ 网络连接异常，无法获取实时数据")
            print(f"  提示: 检查网络连接或稍后重试")
        else:
            print(f"\n  {get_trading_hint()}")  # 非交易时间提示
```

**优势：**
- ✅ 区分网络错误 vs 非交易时间
- ✅ 提供明确的用户提示
- ✅ 避免技术细节暴露给用户

---

## 📊 优化效果对比

### 优化前 ❌
```
【主要指数】
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存

【自选股票】
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))，保留旧缓存
... (重复17次)
```

### 优化后 ✅
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
  建议: 可在交易时间再次运行，或使用'策略回测'功能测试历史数据
```

**改进：**
- ✅ 错误信息从17次减少到1次
- ✅ 用户友好的提示文字
- ✅ 显示缓存年龄，便于判断
- ✅ 提供行动建议

---

## 🔧 技术细节

### 去重逻辑
```python
# 时间戳对比
if self._last_error_time:
    time_since_error = (now - self._last_error_time).total_seconds()
    should_print = time_since_error > 60  # 60秒阈值

# 首次错误或超过阈值才打印
if should_print:
    print(error_message)
    self._last_error_time = now
```

### 错误分类
1. **网络错误** - 无法连接 AKShare API
   - 提示：检查网络连接
   - 行动：使用旧缓存（如果有）

2. **非交易时间** - 数据全为0
   - 提示：当前非交易时间
   - 行动：显示下次交易时间

3. **数据异常** - 其他问题
   - 提示：数据获取失败
   - 行动：记录日志供调试

---

## 📌 影响范围

### 已修改文件
1. ✅ `src/data_sources/akshare_source.py` - 错误去重
2. ✅ `src/monitors/realtime_monitor.py` - 友好提示

### 行为变更
- **错误日志频率**：从每个股票一次 → 60秒一次
- **用户提示**：技术错误信息 → 友好提示文字
- **缓存信息**：添加缓存年龄显示

---

## 🎯 用户体验提升

### 场景1：网络临时中断
- **优化前**：屏幕充满错误信息，用户不知道发生了什么
- **优化后**：显示"网络异常"，提示检查网络，显示使用旧缓存

### 场景2：午间休市
- **优化前**：错误信息混淆非交易时间提示
- **优化后**：清晰显示"午间休市"，提供下次交易时间

### 场景3：交易时间正常运行
- **优化前**：偶尔的网络抖动会打印错误
- **优化后**：60秒内相同错误只显示一次

---

## 🔍 调试信息保留

虽然用户看到的错误减少了，但完整的日志仍然保留：

```python
# 用户看到的（精简）
print(f"⚠ 网络异常，无法刷新数据: {e}")

# 日志记录的（完整）
logger.warning(f"刷新缓存失败: {e}，保留旧缓存")
logger.error(f"⚠ 缓存已过期 {cache_age:.0f}秒")
```

开发者可以通过配置日志级别查看完整信息。

---

**优化版本：** V2.2.2  
**优化日期：** 2025-10-10  
**优化目标：** 改善网络错误的用户体验
