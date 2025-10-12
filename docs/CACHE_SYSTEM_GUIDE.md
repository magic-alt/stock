# 数据缓存系统使用指南

## 概述

本系统实现了一个完整的股票数据本地缓存方案，包括：
- SQLite数据库存储历史数据
- 智能缓存策略（优先本地读取，缺失数据从网络获取）
- 命令行管理工具
- 与现有系统的无缝集成

## 功能特性

### 1. 数据缓存管理
- **自动缓存**: 获取的历史数据自动保存到本地SQLite数据库
- **增量更新**: 只下载缺失的日期区间，避免重复下载
- **智能合并**: 将缓存数据与网络数据智能合并
- **多数据源支持**: 兼容AKShare、新浪财经等数据源

### 2. 本地数据库
- **SQLite存储**: 轻量级、无服务器的数据库
- **规范化设计**: 分别存储股票和指数数据
- **索引优化**: 针对股票代码和日期建立索引，提高查询性能
- **元数据管理**: 记录数据更新时间和覆盖范围

### 3. 命令行工具
- **批量下载**: 支持预定义股票组和自定义股票列表
- **增量更新**: 定期更新最新数据
- **缓存管理**: 查看统计信息、清空缓存
- **数据源测试**: 验证网络连接和数据获取

## 快速开始

### 1. 基础使用

```python
from src.data_sources.cached_source import CachedDataSource

# 创建缓存数据源
data_source = CachedDataSource()

# 获取股票历史数据（自动缓存）
df = data_source.get_stock_history('000001', '2024-01-01', '2024-12-31')
print(f"获取到 {len(df)} 条记录")
```

### 2. 命令行工具使用

```bash
# 查看缓存信息
python data_manager.py cache-info

# 下载最近一年数据
python data_manager.py download-recent --days 365

# 下载指定股票
python data_manager.py download-stocks "000001,000002,600000" "2024-01-01"

# 下载主要指数
python data_manager.py download-indices "2024-01-01"

# 增量更新最近一周数据
python data_manager.py update --days 7

# 测试数据源连接
python data_manager.py test

# 清空所有缓存
python data_manager.py clear-cache
```

### 3. 主程序集成

在主程序中选择"数据管理"菜单，可以通过交互界面进行：
- 查看缓存统计信息
- 下载和更新数据
- 测试数据源连接
- 管理缓存数据

## 配置说明

### 1. 数据源配置

在 `src/config.py` 中设置：

```python
# 默认使用缓存数据源
DATA_SOURCE = 'cached'
```

支持的数据源类型：
- `cached`: 缓存数据源（推荐）
- `akshare`: AKShare数据源
- `sina`: 新浪财经数据源
- `auto`: 自动选择可用数据源

### 2. 缓存目录

默认缓存目录为 `datacache/`，可以自定义：

```python
from src.data_sources.cached_source import CachedDataSource

# 自定义缓存目录
data_source = CachedDataSource(cache_dir="my_cache")
```

## 数据库结构

### 股票历史数据表 (stock_history)
- `stock_code`: 股票代码
- `date`: 交易日期
- `open/high/low/close`: OHLC价格
- `volume`: 成交量
- `amount`: 成交额
- `turnover`: 换手率
- `pct_change`: 涨跌幅
- `adjust_type`: 复权类型

### 指数历史数据表 (index_history)
- `index_code`: 指数代码
- `date`: 交易日期
- `open/high/low/close`: OHLC价格
- `volume`: 成交量
- `amount`: 成交额
- `pct_change`: 涨跌幅

### 数据更新记录表 (data_updates)
- `symbol`: 股票/指数代码
- `symbol_type`: 类型（stock/index）
- `last_update_date`: 最后更新日期
- `data_count`: 数据条数

## 性能优化

### 1. 缓存命中率
- 第一次获取：从网络下载并缓存（较慢）
- 后续获取：直接从本地数据库读取（快速）
- 增量更新：只获取缺失的日期区间

### 2. 查询优化
- 基于股票代码和日期的复合索引
- 按日期范围过滤，减少内存使用
- 批量插入，提高写入性能

### 3. 网络优化
- 自动降级机制（AKShare → 新浪财经）
- 连接池复用
- 错误重试机制

## 维护和管理

### 1. 定期维护

```bash
# 每日增量更新
python data_manager.py update --days 1

# 每周全面更新
python data_manager.py download-recent --days 30

# 清理过期数据（可选）
python data_manager.py clear-cache
```

### 2. 监控和统计

```python
from src.data_sources.cached_source import CachedDataSource

data_source = CachedDataSource()
stats = data_source.get_cache_stats()

print(f"股票数量: {stats['stock_symbols']}")
print(f"数据记录: {stats['stock_records']}")
print(f"数据库大小: {stats['db_size_mb']} MB")
```

## 故障排除

### 1. 网络连接问题
- 检查网络连接
- 使用测试命令验证数据源: `python data_manager.py test`
- 考虑切换数据源（自动降级）

### 2. 数据库问题
- 检查磁盘空间
- 确认数据库文件权限
- 必要时重建缓存: `python data_manager.py clear-cache`

### 3. 数据不一致
- 清空缓存并重新下载
- 检查日期格式和时区设置
- 验证数据源的数据质量

## 扩展和定制

### 1. 添加新数据源

```python
from src.data_sources.base import DataSource
from src.data_sources.cached_source import CachedDataSource

class MyDataSource(DataSource):
    # 实现抽象方法
    pass

# 使用自定义数据源
cached_source = CachedDataSource(underlying_source=MyDataSource())
```

### 2. 自定义缓存策略

```python
from src.data_sources.cache_manager import DataCacheManager

# 扩展缓存管理器
class MyDataCacheManager(DataCacheManager):
    # 自定义缓存逻辑
    pass
```

### 3. 集成到现有系统

```python
# 在现有代码中替换数据源
from src.data_sources import DataSourceFactory

# 将默认数据源设置为缓存数据源
DataSourceFactory._default_source_type = 'cached'
```

## 最佳实践

1. **定期更新**: 建议每天自动更新最新数据
2. **批量下载**: 首次使用时批量下载历史数据
3. **监控空间**: 定期检查数据库大小和磁盘空间
4. **备份数据**: 重要数据建议定期备份
5. **性能测试**: 定期测试缓存性能和数据质量

## 系统集成

缓存系统已与现有的监控和回测系统完全集成：

- **实时监控**: 使用缓存的历史数据计算技术指标
- **策略回测**: 优先从缓存读取历史数据，提高回测速度
- **数据源工厂**: 支持通过工厂模式创建缓存数据源
- **配置管理**: 统一的配置文件管理缓存设置

通过使用缓存系统，可以显著提高系统性能，减少网络依赖，提升用户体验。