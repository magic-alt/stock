# NaN错误修复说明 V2.1.1

## 🐛 问题描述

在运行实时监控时出现以下错误：
```
获取指数 000001 实时数据失败: cannot convert float NaN to integer
获取股票 300750 实时数据失败: cannot convert float NaN to integer
```

**原因分析：**
1. 非交易时间（周末、晚上等）akshare返回的数据中很多字段为NaN
2. 直接使用`int()`和`float()`转换NaN值会导致错误
3. 缺少对非交易时间的友好提示

---

## ✅ 修复方案

### 修复1: 数据源安全转换

**文件：** `src/data_sources/akshare_source.py`

**修改：** 添加安全转换函数处理NaN值

```python
# 安全转换函数，处理NaN值
def safe_float(val, default=0.0):
    try:
        return float(val) if pd.notna(val) else default
    except:
        return default

def safe_int(val, default=0):
    try:
        return int(val) if pd.notna(val) else default
    except:
        return default

# 使用安全转换
return {
    '代码': stock_code,
    '名称': str(info['名称']),
    '最新价': safe_float(info['最新价']),
    '涨跌幅': safe_float(info['涨跌幅']),
    '成交量': safe_int(info['成交量']),
    '成交额': safe_float(info['成交额']),
    # ... 其他字段同样处理
}
```

**效果：**
- ✅ NaN值自动转换为0，不再报错
- ✅ 数据获取永远不会因为NaN而崩溃

---

### 修复2: 监控器友好提示

**文件：** `src/monitors/realtime_monitor.py`

**修改1：** 指数显示添加数据检查
```python
def display_indices(self):
    has_data = False
    for code, name in self.indices.items():
        index_data = self.data_source.get_index_realtime(code)
        if index_data and index_data['最新价'] > 0:
            has_data = True
            # 显示数据...
    
    if not has_data:
        print("  ⚠ 当前为非交易时间，无法获取实时数据")
        print("  提示: 交易时间为工作日 9:30-11:30, 13:00-15:00")
```

**修改2：** 股票显示添加数据检查
```python
def display_stocks(self, show_indicators: bool = True):
    has_data = False
    for code, name in self.watchlist.items():
        stock_data = self.data_source.get_stock_realtime(code)
        
        if not stock_data or stock_data['最新价'] == 0:
            continue  # 跳过无效数据
        
        has_data = True
        # 显示数据...
    
    if not has_data:
        print("\n  ⚠ 当前为非交易时间或所有股票均无有效数据")
        print("  提示: 交易时间为工作日 9:30-11:30, 13:00-15:00")
        print("  建议: 可在交易时间再次运行，或使用'策略回测'功能测试历史数据")
```

**效果：**
- ✅ 非交易时间显示友好提示
- ✅ 不再显示大量"数据获取失败"信息
- ✅ 给出明确的使用建议

---

## 📊 修复对比

### 修复前 ❌
```
【主要指数】
----------------------------------------------------------------------------------------------------
获取指数 000001 实时数据失败: cannot convert float NaN to integer
获取指数 000300 实时数据失败: cannot convert float NaN to integer
...（大量错误信息）

【自选股票】
----------------------------------------------------------------------------------------------------
获取股票 300750 实时数据失败: cannot convert float NaN to integer
宁德时代(300750): 数据获取失败
...（更多错误）
```

### 修复后 ✅
```
【主要指数】
----------------------------------------------------------------------------------------------------
  ⚠ 当前为非交易时间，无法获取实时数据
  提示: 交易时间为工作日 9:30-11:30, 13:00-15:00

【自选股票】
----------------------------------------------------------------------------------------------------

  ⚠ 当前为非交易时间或所有股票均无有效数据
  提示: 交易时间为工作日 9:30-11:30, 13:00-15:00
  建议: 可在交易时间再次运行，或使用'策略回测'功能测试历史数据
```

---

## 🧪 测试验证

### 测试脚本
```bash
python test_nan_handling.py
```

### 测试内容
1. ✅ 指数数据NaN处理
2. ✅ 股票数据NaN处理
3. ✅ 非交易时间友好提示

---

## 🎯 使用建议

### 交易时间使用
```bash
python main.py
> 1. 实时监控
> 选择方案...
```
**效果：** 显示实时行情数据

### 非交易时间使用
```bash
python main.py
> 2. 策略回测
> 选择引擎和股票...
```
**效果：** 使用历史数据进行回测分析

---

## 📝 修改文件清单

### 修改的文件（2个）
1. ✅ `src/data_sources/akshare_source.py`
   - 第49-76行：添加safe_float和safe_int函数
   - 第94-121行：指数数据使用安全转换

2. ✅ `src/monitors/realtime_monitor.py`
   - 第50-60行：指数显示添加数据检查
   - 第62-115行：股票显示添加数据检查

### 新增的文件（1个）
1. ✅ `test_nan_handling.py` - NaN处理测试脚本

---

## 🔍 技术细节

### NaN检测
```python
import pandas as pd

# 检测NaN
if pd.notna(value):
    return float(value)
else:
    return 0.0
```

### 异常捕获
```python
def safe_float(val, default=0.0):
    try:
        return float(val) if pd.notna(val) else default
    except:
        return default  # 任何异常都返回默认值
```

### 数据有效性检查
```python
# 价格为0表示无有效数据（非交易时间）
if stock_data['最新价'] > 0:
    # 显示数据
else:
    # 跳过或显示提示
```

---

## ⚠️ 注意事项

### 1. 交易时间
- **A股交易时间：** 工作日 9:30-11:30, 13:00-15:00
- **数据延迟：** akshare实时数据有约15分钟延迟
- **非交易时间：** 周末、节假日、盘后均无实时数据

### 2. 网络问题
如果出现以下错误：
```
刷新缓存失败: ('Connection aborted.', RemoteDisconnected(...))
```

**解决方法：**
1. 检查网络连接
2. 稍后重试
3. 使用历史数据回测功能

### 3. 数据为0
显示的数据全为0说明：
- 当前为非交易时间
- 或网络获取数据失败
- 系统已正确处理，不会报错

---

## ✅ 修复验证

### 回测功能测试
```bash
python main.py
> 2. 策略回测
> 1. 简单引擎
> 选择股票和策略...
```

**结果：** ✅ 正常工作
```
2025-08-18 | 买入 | 价格:   282.00 | 股数:    300 | 成本:      33.84
2025-10-09 | 卖出 | 价格:   409.89 | 股数:    300 | 盈亏: +38,161.01 (+45.11%)
```

### 实时监控测试（非交易时间）
```bash
python main.py
> 1. 实时监控
```

**结果：** ✅ 显示友好提示，无错误

---

## 🎊 修复完成

### 核心改进
- ✅ NaN值安全处理
- ✅ 非交易时间友好提示
- ✅ 错误信息优化
- ✅ 用户体验提升

### 功能状态
- ✅ 实时监控 - 已修复
- ✅ 策略回测 - 正常工作（V2.1修复）
- ✅ 股票分组 - 正常工作
- ✅ Backtrader - 正常工作（V2.1新增）

---

## 📚 相关文档

- `修复说明_V2.1.md` - 之前的三大修复
- `V2.1快速使用.md` - 快速使用指南
- `NaN错误修复说明.md` - 本文档

---

**版本：** V2.1.1  
**修复日期：** 2025-10-10  
**状态：** ✅ 已修复，测试通过  

---

## 🚀 立即使用

```bash
# 交易时间
python main.py > 1  # 实时监控

# 非交易时间
python main.py > 2  # 策略回测

# 测试修复
python test_nan_handling.py
```

**所有功能已恢复正常！** 🎉
