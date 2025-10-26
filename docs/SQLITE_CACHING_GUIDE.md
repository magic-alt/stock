# SQLite3数据缓存系统升级指南

## V2.10.1 更新概览

本次更新将数据存储机制从CSV文件迁移至SQLite3数据库，实现了智能增量数据获取功能。

## 核心改进

### 1. **统一数据库存储**
- 所有股票和指数数据统一保存在 `cache/market_data.db` SQLite3数据库中
- 取代了之前为每个时间范围创建单独CSV文件的方式
- 数据库自动管理索引，查询性能更优

### 2. **智能增量更新**
```python
# 场景示例：
# 第一次请求：2024-01-01 到 2024-06-30  → 下载全部数据
# 第二次请求：2024-01-01 到 2024-12-31  → 只下载 2024-07-01 到 2024-12-31 的缺失部分
# 第三次请求：2023-01-01 到 2024-12-31  → 只下载 2023-01-01 到 2023-12-31 的缺失部分
```

系统会：
- 自动检测数据库中已有的数据范围
- 计算缺失的日期区间
- 仅从远程API（akshare/yfinance/tushare）下载缺失部分
- 将新数据合并到数据库

### 3. **元数据追踪**
数据库维护每个股票/指数的元数据：
- `first_date`: 最早数据日期
- `last_date`: 最晚数据日期
- `last_update`: 最后更新时间
- `adj_type`: 复权类型（noadj/qfq/hfq）

## 数据库架构

### 表结构

#### stock_daily（股票日线数据）
```sql
CREATE TABLE stock_daily (
    symbol TEXT NOT NULL,      -- 股票代码（如 600519.SH）
    date TEXT NOT NULL,         -- 日期 (YYYY-MM-DD)
    open REAL,                  -- 开盘价
    high REAL,                  -- 最高价
    low REAL,                   -- 最低价
    close REAL,                 -- 收盘价
    volume REAL,                -- 成交量
    adj_type TEXT,              -- 复权类型
    PRIMARY KEY (symbol, date, adj_type)
);
```

#### index_daily（指数日线数据）
```sql
CREATE TABLE index_daily (
    symbol TEXT NOT NULL,       -- 指数代码（如 000300.SH）
    date TEXT NOT NULL,          -- 日期
    close REAL,                  -- 收盘价
    adj_type TEXT,               -- 复权类型
    PRIMARY KEY (symbol, date, adj_type)
);
```

#### metadata（元数据追踪）
```sql
CREATE TABLE metadata (
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL,     -- 'stock' 或 'index'
    adj_type TEXT NOT NULL,
    first_date TEXT,             -- 数据起始日期
    last_date TEXT,              -- 数据结束日期
    last_update TEXT,            -- 最后更新时间
    PRIMARY KEY (symbol, data_type, adj_type)
);
```

## 使用示例

### 基本用法（无需改动）
```python
from src.backtest.engine import BacktestEngine

# 现有代码无需修改，自动使用SQLite3缓存
engine = BacktestEngine(source="akshare", cache_dir="./cache")

# 第一次运行：下载数据并存入数据库
metrics = engine.run_strategy(
    "macd",
    ["600519.SH"],
    "2024-01-01",
    "2024-06-30",
    ...
)

# 第二次运行不同日期范围：只下载新增部分
metrics = engine.run_strategy(
    "macd",
    ["600519.SH"],
    "2024-01-01",
    "2024-12-31",  # 只下载 2024-07-01 到 2024-12-31
    ...
)
```

### 直接使用DataProvider
```python
from src.data_sources.providers import get_provider

# 创建提供者（会自动初始化数据库）
provider = get_provider('akshare', cache_dir='./cache')

# 加载数据（自动使用增量更新）
data_map = provider.load_stock_daily(
    symbols=['600519.SH', '000001.SZ'],
    start='2024-01-01',
    end='2024-12-31',
    adj='qfq'
)
```

### 数据库管理工具
```python
from src.data_sources.db_manager import SQLiteDataManager

# 初始化管理器
db = SQLiteDataManager('./cache/market_data.db')

# 查询数据范围
data_range = db.get_data_range('600519.SH', 'stock', 'noadj')
print(f"数据范围: {data_range[0]} 到 {data_range[1]}")

# 检测缺失范围
missing = db.get_missing_ranges(
    '600519.SH', 'stock', '2023-01-01', '2024-12-31', 'noadj'
)
print(f"需要下载的缺失范围: {missing}")

# 清除特定股票数据
db.clear_symbol_data('600519.SH', 'stock', 'noadj')

# 获取所有已缓存的股票
symbols = db.get_all_symbols('stock')
print(f"已缓存 {len(symbols)} 只股票")

# 优化数据库（回收空间）
db.vacuum()
```

## 日志输出

新系统会输出清晰的日志信息：

```
✓ 600519.SH: Loaded from database (250 bars)
↓ 000001.SZ: Fetching 2 missing range(s) from AKShare
  Saved 120 bars for range 2024-07-01 to 2024-12-31
✓ 000001.SZ: Complete (370 bars)
✗ 000002.SZ: Error loading data: ...
```

符号说明：
- `✓` - 从数据库加载成功
- `↓` - 正在从远程API下载
- `✗` - 加载失败

## 迁移说明

### 从CSV到SQLite3的迁移

1. **自动迁移**
   - 新系统会自动创建数据库
   - 旧的CSV文件不会被删除（可手动清理）
   - 首次运行时会下载数据到数据库

2. **手动清理旧CSV文件**（可选）
   ```bash
   # Windows PowerShell
   Remove-Item cache\ak_*.csv
   Remove-Item cache\yf_*.csv
   Remove-Item cache\ts_*.csv
   
   # Linux/Mac
   rm cache/ak_*.csv cache/yf_*.csv cache/ts_*.csv
   ```

3. **数据库位置**
   - 默认: `./cache/market_data.db`
   - 可通过 `cache_dir` 参数自定义

## 性能优势

### 存储空间
- **之前**: 每个时间范围创建一个CSV文件
  - 600519.SH_2024-01-01_2024-06-30.csv
  - 600519.SH_2024-01-01_2024-12-31.csv
  - 600519.SH_2023-01-01_2024-12-31.csv
  - ... (大量重复数据)

- **现在**: 单一数据库文件
  - market_data.db (包含所有数据，无重复)

### 下载效率
```python
# 场景：多次回测不同时间范围
# CSV方式：
# 第1次: 下载 2024-01-01 ~ 2024-06-30 (250个交易日)
# 第2次: 下载 2024-01-01 ~ 2024-12-31 (全部370个交易日，重复250)
# 第3次: 下载 2023-01-01 ~ 2024-12-31 (全部620个交易日，重复370)
# 总下载: 1240个交易日数据

# SQLite方式：
# 第1次: 下载 2024-01-01 ~ 2024-06-30 (250个交易日)
# 第2次: 下载 2024-07-01 ~ 2024-12-31 (120个交易日)
# 第3次: 下载 2023-01-01 ~ 2023-12-31 (250个交易日)
# 总下载: 620个交易日数据（减少50%）
```

### 查询性能
- 数据库自动索引，快速查询任意时间范围
- 无需读取整个CSV文件
- 支持并发读取

## 复权类型支持

系统自动区分不同复权类型：
- `noadj`: 不复权（默认）
- `qfq`: 前复权
- `hfq`: 后复权

每种复权类型的数据独立存储，互不干扰。

```python
# 同一股票的不同复权数据可并存
provider.load_stock_daily(['600519.SH'], '2024-01-01', '2024-12-31', adj=None)    # noadj
provider.load_stock_daily(['600519.SH'], '2024-01-01', '2024-12-31', adj='qfq')   # 前复权
provider.load_stock_daily(['600519.SH'], '2024-01-01', '2024-12-31', adj='hfq')   # 后复权
```

## 故障排除

### 数据库损坏
```python
# 删除并重建数据库
import os
if os.path.exists('./cache/market_data.db'):
    os.remove('./cache/market_data.db')
# 下次运行会自动重建
```

### 强制重新下载特定股票
```python
from src.data_sources.db_manager import SQLiteDataManager

db = SQLiteDataManager('./cache/market_data.db')
db.clear_symbol_data('600519.SH', 'stock', 'noadj')
# 下次加载会重新下载
```

### 数据库优化
```python
from src.data_sources.db_manager import SQLiteDataManager

db = SQLiteDataManager('./cache/market_data.db')
db.vacuum()  # 压缩数据库，回收删除的空间
```

## 向后兼容性

✅ 完全兼容现有代码，无需修改：
- `BacktestEngine` API不变
- `DataProvider` 接口不变
- CLI命令不变

## 技术细节

### 增量更新算法
```python
# 伪代码
existing_range = db.get_data_range(symbol)  # (2024-01-01, 2024-06-30)
requested_range = (2024-01-01, 2024-12-31)

missing_ranges = []
if requested_start < existing_start:
    missing_ranges.append((requested_start, existing_start - 1day))
if requested_end > existing_end:
    missing_ranges.append((existing_end + 1day, requested_end))

for start, end in missing_ranges:
    download_data(symbol, start, end)
    save_to_db(symbol, data)
```

### 线程安全
- SQLite3提供进程间并发读取
- 写入操作自动序列化
- 适合多进程回测场景

## 相关文件

- `src/data_sources/db_manager.py` - 数据库管理器
- `src/data_sources/providers.py` - 数据提供者（已更新）
- `test/test_sqlite_caching.py` - 测试用例
- `cache/market_data.db` - 数据库文件（运行时生成）

## 更新日志

**V2.10.1 (2025-01-26)**
- ✨ 新增SQLite3数据库存储
- ✨ 智能增量数据更新
- ✨ 元数据追踪和范围检测
- 🔧 优化存储空间和下载效率
- 📚 完整文档和测试用例
- ✅ 完全向后兼容

## 常见问题

**Q: 旧的CSV文件会被删除吗？**
A: 不会。系统会创建新数据库，旧CSV文件保留。可以手动删除。

**Q: 数据库文件在哪里？**
A: 默认在 `./cache/market_data.db`

**Q: 如何知道哪些数据已缓存？**
A: 使用 `db.get_all_symbols()` 和 `db.get_data_range()`

**Q: 支持多个数据库吗？**
A: 支持。通过不同的 `cache_dir` 创建独立的数据库。

**Q: 数据库会自动更新最新数据吗？**
A: 当请求的结束日期超过已有数据时，系统会自动下载新增部分。

**Q: 性能如何？**
A: 查询速度更快，存储空间更少，下载量显著减少。
