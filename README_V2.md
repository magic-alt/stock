# A股监控与回测系统 V2.0

全新模块化架构，支持AI、芯片、黄金等主题股票监控与策略回测。

## 🎯 新版特性

### V2.0 更新内容

#### 1. 模块化架构
- ✅ 清晰的目录结构
- ✅ 可扩展的插件式设计
- ✅ 标准化的接口定义
- ✅ 预留backtrader集成接口

#### 2. 新增股票分组
- ✅ **润泽科技** (数据中心概念)
- ✅ **卧龙电驱** (600580) - 电机驱动龙头
- ✅ **歌尔股份** (002241) - AI音频、VR/AR
- ✅ AI芯片主题：中芯国际、宁德时代等
- ✅ 黄金主题：山东黄金、紫金矿业等
- ✅ 新能源主题：电驱、锂电池等

#### 3. 增强的技术指标
- MA (5/10/20/60日均线)
- EMA (指数移动平均)
- RSI (相对强弱指标)
- MACD (平滑异同移动平均线)
- 布林带 (Bollinger Bands)
- KDJ (随机指标)
- ATR (真实波幅)

#### 4. 多策略回测
- 双均线交叉策略
- 三均线策略
- RSI超买超卖策略
- RSI背离策略
- MACD信号策略
- MACD零轴策略

#### 5. 预设监控方案
- AI芯片主题
- 黄金主题
- 新能源汽车
- 优质蓝筹
- 科技综合
- 自定义组合

## 📁 项目结构

```
d:\Project\data\
│
├── main.py                    # 主程序入口（V2.0）
├── start.py                   # 启动菜单（兼容旧版）
├── 启动工具.bat               # Windows快速启动
│
├── src/                       # 源代码模块
│   ├── __init__.py
│   ├── config.py             # 配置文件（股票分组、参数）
│   │
│   ├── data_sources/         # 数据源模块
│   │   ├── __init__.py
│   │   ├── base.py           # 数据源基类
│   │   ├── akshare_source.py # AKShare实现
│   │   └── factory.py        # 数据源工厂
│   │
│   ├── indicators/           # 技术指标模块
│   │   ├── __init__.py
│   │   └── technical.py      # 技术指标计算
│   │
│   ├── strategies/           # 策略模块
│   │   ├── __init__.py
│   │   ├── base.py           # 策略基类
│   │   ├── ma_strategies.py  # 均线策略
│   │   ├── rsi_strategies.py # RSI策略
│   │   └── macd_strategies.py # MACD策略
│   │
│   ├── backtest/             # 回测模块
│   │   ├── __init__.py
│   │   ├── simple_engine.py  # 简单回测引擎
│   │   └── backtrader_adapter.py # Backtrader适配器
│   │
│   ├── monitors/             # 监控模块
│   │   ├── __init__.py
│   │   └── realtime_monitor.py # 实时监控器
│   │
│   └── utils/                # 工具模块
│       ├── __init__.py
│       └── helpers.py        # 辅助函数
│
├── requirements.txt          # 依赖包
├── README_V2.md             # 本文档
├── 项目总览_V2.md           # 详细文档
└── 使用指南_V2.md           # 使用教程

# 旧版文件（保留兼容）
├── stock_monitor.py
├── quick_monitor.py
├── quick_backtest.py
└── test_connection.py
```

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行主程序

```bash
# 方式1: 运行新版主程序
python main.py

# 方式2: Windows双击
启动工具.bat

# 方式3: 旧版兼容
python start.py
```

## 🎮 使用示例

### 1. 实时监控

```bash
python main.py
# 选择 1 - 实时监控
# 选择监控方案（AI芯片、黄金等）
```

**监控方案**：
- 默认方案：AI+芯片+黄金+优质股精选
- AI芯片主题：专注AI和半导体
- 黄金主题：黄金矿业股
- 新能源汽车：电驱、锂电池
- 优质蓝筹：茅台、平安等
- 科技综合：全科技板块
- 全部股票：所有分组
- 自定义：手动输入代码

### 2. 策略回测

```bash
python main.py
# 选择 2 - 策略回测
# 选择股票（手动输入或从分组选择）
# 选择策略和回测周期
```

**可用策略**：
1. 双均线交叉 (MA5/MA20)
2. 三均线策略 (MA5/MA10/MA20)
3. RSI超买超卖
4. MACD信号
5. MACD零轴

### 3. 查看股票分组

```bash
python main.py
# 选择 3 - 查看股票分组
```

## 📊 新增股票详情

### AI & 芯片板块
| 代码 | 名称 | 特点 |
|------|------|------|
| 300750 | 宁德时代 | 新能源电池龙头 |
| 688981 | 中芯国际 | 芯片制造龙头 |
| 002241 | **歌尔股份** | AI音频、VR/AR |
| 002475 | 立讯精密 | 精密制造 |
| 002415 | 海康威视 | AI视觉 |

### 电驱/新能源
| 代码 | 名称 | 特点 |
|------|------|------|
| **600580** | **卧龙电驱** | 电机驱动龙头 |
| 002460 | 赣锋锂业 | 锂业龙头 |
| 300014 | 亿纬锂能 | 锂电池 |
| 002594 | 比亚迪 | 新能源汽车 |

### 黄金板块
| 代码 | 名称 | 特点 |
|------|------|------|
| 600547 | 山东黄金 | 黄金开采 |
| 600489 | 中金黄金 | 黄金加工 |
| 601899 | 紫金矿业 | 矿业龙头 |
| 002155 | 湖南黄金 | 黄金矿业 |

### 数据中心
| 代码 | 名称 | 特点 |
|------|------|------|
| 300339 | 润和软件 | 软件服务 |
| 603869 | 新智认知 | 数据智能 |

## ⚙️ 配置文件说明

### 主配置文件：`src/config.py`

```python
# 修改默认监控股票
DEFAULT_WATCHLIST = {
    '002241': '歌尔股份',  # 新增
    '600580': '卧龙电驱',  # 新增
    '600547': '山东黄金',
    # ... 添加更多
}

# 修改刷新间隔
REFRESH_INTERVAL = 30  # 秒

# 修改技术指标参数
MA_PERIODS = {
    'short': 5,
    'mid': 10,
    'long': 20,
}

# 修改回测参数
BACKTEST_CONFIG = {
    'initial_capital': 100000,
    'commission': 0.0003,
    'stamp_duty': 0.001,
}
```

## 🔧 扩展开发

### 1. 添加新的数据源

```python
# src/data_sources/custom_source.py
from .base import DataSource

class CustomDataSource(DataSource):
    def get_stock_realtime(self, stock_code: str):
        # 实现你的数据获取逻辑
        pass
```

### 2. 添加自定义策略

```python
# src/strategies/my_strategy.py
from .base import BaseStrategy

class MyStrategy(BaseStrategy):
    def generate_signals(self, df):
        # 实现你的策略逻辑
        df['Signal'] = ...
        return df
```

### 3. 集成Backtrader

```python
from src.backtest import BacktraderAdapter

adapter = BacktraderAdapter()
if adapter.setup(initial_capital=100000):
    adapter.add_data(df)
    adapter.add_strategy(MyBacktraderStrategy)
    results = adapter.run()
    adapter.plot()
```

## 📈 技术指标说明

### 移动平均线 (MA)
- **MA5**: 短期趋势
- **MA10**: 中期趋势  
- **MA20**: 长期趋势
- **金叉**: 短期上穿长期，看涨
- **死叉**: 短期下穿长期，看跌

### RSI (相对强弱)
- **> 70**: 超买，可能回调
- **< 30**: 超卖，可能反弹
- **背离**: 价格与RSI走势相反时的信号

### MACD
- **金叉**: MACD上穿Signal线
- **死叉**: MACD下穿Signal线
- **零轴**: MACD穿越零轴的趋势信号

### 布林带
- **价格触及上轨**: 可能超买
- **价格触及下轨**: 可能超卖
- **收窄**: 可能突破

## 🎯 回测策略详解

### 1. 双均线策略
```
买入条件: MA5 上穿 MA20
卖出条件: MA5 下穿 MA20
适用场景: 趋势明显的市场
```

### 2. RSI超买超卖
```
买入条件: RSI < 30
卖出条件: RSI > 70
适用场景: 震荡市场
```

### 3. MACD信号
```
买入条件: MACD 上穿 Signal线
卖出条件: MACD 下穿 Signal线
适用场景: 中期趋势跟踪
```

## 💡 使用技巧

### 1. 组合监控
选择"默认方案"或"科技综合"可以同时监控多个主题的龙头股。

### 2. 主题轮动
根据市场热点切换不同的监控方案：
- 市场热点在AI → 选择"AI芯片主题"
- 避险需求 → 选择"黄金主题"
- 新能源政策利好 → 选择"新能源汽车"

### 3. 策略对比
对同一只股票使用不同策略回测，选择最适合的策略。

### 4. 参数优化
修改 `src/config.py` 中的策略参数，寻找最优参数组合。

## ⚠️ 注意事项

1. **数据延迟**: 免费数据源有15分钟左右延迟
2. **回测陷阱**: 历史回测结果不代表未来表现
3. **交易成本**: 回测已包含手续费和印花税
4. **资金管理**: 建议单只股票仓位不超过30%
5. **风险控制**: 设置止损止盈，控制回撤

## 🔄 版本历史

**V2.0** (2025-10-09)
- ✅ 模块化重构
- ✅ 新增AI、芯片、黄金主题股票
- ✅ 新增卧龙电驱、歌尔股份、润泽科技等
- ✅ 预留backtrader接口
- ✅ 增强技术指标
- ✅ 多策略回测
- ✅ 预设监控方案

**V1.0** (2025-10-09)
- ✅ 基础实时监控
- ✅ 简单回测功能

## 🚧 未来计划

- [ ] 集成backtrader完整回测
- [ ] 添加图表可视化
- [ ] 支持多只股票组合回测
- [ ] 机器学习策略
- [ ] Web界面
- [ ] 实时告警推送
- [ ] 自动交易接口

## 📞 技术支持

遇到问题？

1. 查看 `使用指南_V2.md`
2. 检查 `src/config.py` 配置
3. 运行 `test_connection.py` 测试数据连接

## 📝 免责声明

**重要提示**：
- 本工具仅供学习和研究使用
- 所有数据和分析不构成投资建议
- 投资有风险，入市需谨慎
- 请根据自身情况做出投资决策

---

**祝你投资顺利！📈🚀**

V2.0 - 更专业，更强大，更易扩展！
