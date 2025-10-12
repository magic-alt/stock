# 📊 数据库预览功能使用指南

## 📍 数据库位置

**正确的数据库文件路径**: `datacache/stock_data.db`

⚠️ **注意**：测试脚本可能创建其他数据库文件（如 `test_cache/stock_data.db` 或 `demo_cache/stock_data.db`），这些是测试数据，请使用主数据库。

---

## 📦 当前数据概况

根据最新检查，数据库包含：
- 📈 **股票历史数据**: 1,021 条记录
- 🎯 **股票数量**: 34 只
- 📊 **指数历史数据**: 210 条记录
- 🔢 **指数数量**: 7 个
- 🔄 **更新记录**: 41 条

数据日期范围：2025-09-12 至 2025-10-12（约30天）

---

## 🛠️ 使用方法

### 方法一：命令行工具

#### 1. 查看数据汇总
```bash
python data_manager.py preview
# 或
python data_manager.py preview --type summary
```

**输出示例**：
```
📊 股票数据汇总
====================================
代码       名称      数据量    开始日期      结束日期
----------------------------------------------------
000001    平安银行    31     2025-09-12   2025-10-12
000002    万科A       30     2025-09-12   2025-10-12
...

📈 指数数据汇总
====================================
代码       名称      数据量    开始日期      结束日期
----------------------------------------------------
000001    上证指数    30     2025-09-12   2025-10-12
399001    深证成指    30     2025-09-12   2025-10-12
...
```

#### 2. 查看指定股票详情
```bash
python data_manager.py preview --type stock --symbol 000001
```

**输出示例**：
```
📈 股票数据详情: 000001
====================================
日期          开盘     最高     最低     收盘     成交量         成交额
------------------------------------------------------------------------
2025-10-12   11.32   11.49   11.30   11.43   108,794,775   1,241,857,088
2025-10-11   11.48   11.54   11.39   11.40   108,831,062   1,246,053,632
...
```

#### 3. 查看指定指数详情
```bash
python data_manager.py preview --type index --symbol 000001
```

#### 4. 查看最近更新记录
```bash
python data_manager.py preview --type updates
```

#### 5. 查看指定股票（限制行数）
```bash
python data_manager.py preview --type stock --symbol 000001 --rows 10
```

---

### 方法二：主程序交互菜单

#### 启动主程序
```bash
python main.py
```

#### 选择数据管理菜单
```
量化投资分析系统
=========================
1. 策略回测
2. 实时监控
3. 数据管理
4. 退出
=========================
请选择功能 (1-4): 3
```

#### 选择预览功能
```
数据管理中心
=========================
1. 下载预定义股票数据
2. 下载自定义股票数据
3. 更新现有数据
4. 查看缓存信息
5. 清理缓存
6. 数据库预览          <--- 选择这个
7. 返回主菜单
=========================
```

#### 预览选项
```
数据库预览
=========================
1. 查看股票数据汇总
2. 查看指数数据汇总
3. 查看最近更新记录
4. 查看指定股票详情
5. 查看指定指数详情
6. 返回
=========================
```

---

### 方法三：使用 DB Browser for SQLite

#### 1. 下载 DB Browser for SQLite
- 官网: https://sqlitebrowser.org/
- 或在 Windows 上使用包管理器: `winget install DBBrowserForSQLite.DBBrowserForSQLite`

#### 2. 打开数据库
1. 启动 DB Browser for SQLite
2. 点击 "Open Database"
3. 导航到项目目录的 `datacache/stock_data.db`
4. 点击 "打开"

#### 3. 浏览数据
- **Browse Data** 选项卡：查看表内容
- **Execute SQL** 选项卡：运行SQL查询
- **Database Structure** 选项卡：查看表结构

#### 示例 SQL 查询：
```sql
-- 查看股票数量
SELECT COUNT(DISTINCT stock_code) as 股票数量 FROM stock_history;

-- 查看最新数据
SELECT * FROM stock_history 
ORDER BY date DESC, stock_code 
LIMIT 10;

-- 查看指定股票
SELECT * FROM stock_history 
WHERE stock_code = '000001' 
ORDER BY date DESC;

-- 查看数据日期范围
SELECT 
    stock_code as 代码,
    MIN(date) as 开始日期,
    MAX(date) as 结束日期,
    COUNT(*) as 数据量
FROM stock_history
GROUP BY stock_code;
```

---

## 🔍 快速诊断

### 检查数据库是否有数据

**PowerShell 命令**:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('datacache/stock_data.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM stock_history'); print(f'股票数据: {cursor.fetchone()[0]} 条'); cursor.execute('SELECT COUNT(*) FROM index_history'); print(f'指数数据: {cursor.fetchone()[0]} 条'); conn.close()"
```

**预期输出**:
```
股票数据: 1021 条
指数数据: 210 条
```

---

## 📝 常见问题

### Q1: DB Browser 中看不到数据？
**A**: 确保打开的是 `datacache/stock_data.db`，而不是测试数据库。

### Q2: 如何下载新数据？
**A**: 使用命令行工具：
```bash
python data_manager.py download --preset basic
```
或在主程序的数据管理菜单中选择 "下载预定义股票数据"。

### Q3: 数据多久更新一次？
**A**: 
- 手动更新：运行 `python data_manager.py update`
- 自动更新：每次使用缓存数据源时，如果数据过期会自动更新

### Q4: 如何查看数据覆盖范围？
**A**: 运行 `python data_manager.py info` 查看详细信息。

### Q5: 数据库文件在哪？
**A**: `datacache/stock_data.db`（约 288 KB）

---

## 📊 数据表结构

### stock_history (股票历史数据)
| 列名 | 类型 | 说明 |
|-----|------|-----|
| id | INTEGER | 主键 |
| stock_code | TEXT | 股票代码 |
| date | TEXT | 交易日期 |
| open | REAL | 开盘价 |
| high | REAL | 最高价 |
| low | REAL | 最低价 |
| close | REAL | 收盘价 |
| volume | REAL | 成交量 |
| amount | REAL | 成交额 |
| created_at | TIMESTAMP | 创建时间 |

### index_history (指数历史数据)
| 列名 | 类型 | 说明 |
|-----|------|-----|
| id | INTEGER | 主键 |
| index_code | TEXT | 指数代码 |
| date | TEXT | 交易日期 |
| open | REAL | 开盘点数 |
| high | REAL | 最高点数 |
| low | REAL | 最低点数 |
| close | REAL | 收盘点数 |
| volume | REAL | 成交量 |
| amount | REAL | 成交额 |
| created_at | TIMESTAMP | 创建时间 |

### data_updates (数据更新记录)
| 列名 | 类型 | 说明 |
|-----|------|-----|
| id | INTEGER | 主键 |
| symbol | TEXT | 股票/指数代码 |
| data_type | TEXT | 数据类型 (stock/index) |
| update_time | TIMESTAMP | 更新时间 |
| record_count | INTEGER | 记录数 |
| status | TEXT | 状态 |

---

## 🚀 高级用法

### 使用 Python 直接查询数据库
```python
import sqlite3
import pandas as pd

# 连接数据库
conn = sqlite3.connect('datacache/stock_data.db')

# 查询股票数据
df = pd.read_sql_query(
    "SELECT * FROM stock_history WHERE stock_code = '000001' ORDER BY date DESC LIMIT 30",
    conn
)

print(df)
conn.close()
```

### 导出数据到 CSV
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('datacache/stock_data.db')

# 导出所有股票数据
df = pd.read_sql_query("SELECT * FROM stock_history", conn)
df.to_csv('stock_data_export.csv', index=False, encoding='utf-8-sig')

conn.close()
```

---

## 📞 支持

如有问题，请参考：
- 📖 完整文档：`docs/CACHE_SYSTEM_GUIDE.md`
- 🧪 测试脚本：`test_db_preview.py`
- 🛠️ 命令行帮助：`python data_manager.py --help`

---

**最后更新**: 2025-01-10
**数据库版本**: 1.0
**记录总数**: 1,272 条（股票 1,021 + 指数 210 + 更新记录 41）
