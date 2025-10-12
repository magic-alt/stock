"""
配置文件 - 股票分组和监控参数
"""

# ==================== 股票分组配置 ====================

# AI相关股票
import os


AI_STOCKS = {
    '300750': '宁德时代',
    '002475': '立讯精密',
    '002415': '海康威视',
    '300059': '东方财富',
    '688981': '中芯国际',
}

# 芯片/半导体股票
CHIP_STOCKS = {
    '688981': '中芯国际',
    '603986': '兆易创新',
    '688012': '中微公司',
    '688008': '澜起科技',
    '300782': '卓胜微',
}

# AI算力/服务器相关
AI_COMPUTING_STOCKS = {
    '300496': '中科创达',
    '300803': '指南针',
    '300768': '迪普科技',
    '300661': '圣邦股份',
}

# 智能制造/机器人
INTELLIGENT_MFG_STOCKS = {
    '603806': '福斯特',
    '300124': '汇川技术',
    '603568': '伟明环保',
}

# 电子/消费电子
ELECTRONICS_STOCKS = {
    '002241': '歌尔股份',  # AI音频、VR/AR
    '002594': '比亚迪',
    '000333': '美的集团',
}

# 电驱/新能源汽车
EV_DRIVE_STOCKS = {
    '600580': '卧龙电驱',  # 电机驱动
    '002460': '赣锋锂业',
    '300014': '亿纬锂能',
}

# 数据中心/云计算
DATA_CENTER_STOCKS = {
    '300674': '宇信科技',
    '603019': '中科曙光',
    '002439': '启明星辰',
    '300442': '润泽科技',
}

# 通信/5G相关
TELECOM_STOCKS = {
    '600498': '烽火通信',
    '002281': '光迅科技',
}

# 黄金相关股票
GOLD_STOCKS = {
    '600547': '山东黄金',
    '600489': '中金黄金',
    '601899': '紫金矿业',
    '002155': '湖南黄金',
}

# 润泽科技 (数据中心)
DATA_INFRA_STOCKS = {
    '300204': '舒泰神',
    '300339': '润和软件',
    '603869': '新智认知',
}

# 传统优质股
BLUE_CHIP_STOCKS = {
    '600519': '贵州茅台',
    '000858': '五粮液',
    '601318': '中国平安',
    '600036': '招商银行',
    '000001': '平安银行',
    '600276': '恒瑞医药',
}

# ==================== 默认监控组合 ====================

# 默认自选股票 - AI、芯片、黄金、电驱主题
DEFAULT_WATCHLIST = {
    # AI & 芯片
    '300750': '宁德时代',
    '688981': '中芯国际',
    '002241': '歌尔股份',
    '600580': '卧龙电驱',
    
    # 黄金
    '600547': '山东黄金',
    '601899': '紫金矿业',
    # 数据中心 / 自选新增
    '300442': '润泽科技',
    
    # 优质股
    '600519': '贵州茅台',
    '601318': '中国平安',
    '600036': '招商银行',
}

# 完整监控列表（所有主题）
FULL_WATCHLIST = {}
for group in [AI_STOCKS, CHIP_STOCKS, ELECTRONICS_STOCKS, 
              EV_DRIVE_STOCKS, GOLD_STOCKS, BLUE_CHIP_STOCKS]:
    FULL_WATCHLIST.update(group)

# ==================== 主要指数 ====================

INDICES = {
    '000001': '上证指数',
    '399001': '深证成指',
    '399006': '创业板指',
    '000300': '沪深300',
    '000016': '上证50',
    '000688': '科创50',
    '399975': '证券公司',
    '000905': '中证500',
}

# 行业指数
SECTOR_INDICES = {
    '000800': '新能源',
    '931079': '半导体',
    '884004': '黄金',
    '399812': '养老产业',
}

# ==================== 监控参数 ====================

# 刷新间隔（秒）
REFRESH_INTERVAL = 30

# 显示配置
DISPLAY_CONFIG = {
    'show_indices': True,          # 显示指数
    'show_tech_indicators': True,  # 显示技术指标
    'show_volume_info': True,      # 显示成交量信息
    'clear_screen': True,          # 刷新时清屏
    'color_enabled': True,         # 启用颜色显示
}

# ==================== 技术指标参数 ====================

# 移动平均线周期
MA_PERIODS = {
    'short': 5,    # 短期
    'mid': 10,     # 中期
    'long': 20,    # 长期
    'ema12': 12,   # MACD快线
    'ema26': 26,   # MACD慢线
}

# RSI参数
RSI_CONFIG = {
    'period': 14,
    'overbought': 70,   # 超买线
    'oversold': 30,     # 超卖线
}

# MACD参数
MACD_CONFIG = {
    'fast': 12,
    'slow': 26,
    'signal': 9,
}

# 布林带参数
BOLLINGER_CONFIG = {
    'period': 20,
    'std_dev': 2,
}

# KDJ参数
KDJ_CONFIG = {
    'n': 9,
    'm1': 3,
    'm2': 3,
}

# ==================== 回测参数 ====================

# 默认回测参数
BACKTEST_CONFIG = {
    'initial_capital': 100000,      # 初始资金
    # 统一佣金率（万分之一）
    'commission': 0.0001,
    # 印花税：此处为简化，若需仅卖出收印花税可扩展 CommissionInfo
    'stamp_duty': 0.0005,          # 印花税率
    'slippage': 0.0001,            # 滑点
    'min_commission': 5,            # 最低手续费
    # Backtrader 下单手数策略：按金额买入
    'sizer': {
        'min_cash': 20000.0,
        'max_cash': 50000.0,
    }
}

# 回测周期
BACKTEST_PERIODS = {
    'short': 30,      # 短期（天）
    'mid': 90,        # 中期
    'long': 365,      # 长期（1年）
    'ultra_long': 1095,  # 超长期（3年）
}

# ==================== 策略参数 ====================

# 双均线策略参数
MA_CROSS_STRATEGY = {
    'short_window': 5,
    'long_window': 20,
    'position_pct': 1.0,  # 仓位比例
}

# RSI策略参数
RSI_STRATEGY = {
    'period': 14,
    'buy_threshold': 30,
    'sell_threshold': 70,
    'position_pct': 1.0,
}

# MACD策略参数
MACD_STRATEGY = {
    'fast': 12,
    'slow': 26,
    'signal': 9,
    'position_pct': 1.0,
}

# 网格策略参数
GRID_STRATEGY = {
    'grid_count': 10,      # 网格数量
    'price_range': 0.2,    # 价格范围（±20%）
    'position_per_grid': 0.1,  # 每格仓位
}

# ==================== 风险控制参数 ====================

RISK_CONFIG = {
    'max_position': 0.3,         # 单只股票最大仓位
    'stop_loss': -0.08,          # 止损线（-8%）
    'take_profit': 0.15,         # 止盈线（+15%）
    'max_drawdown': -0.20,       # 最大回撤（-20%）
    'trailing_stop': 0.05,       # 移动止损（5%）
}

# ==================== 数据源配置 ====================

# 数据源：akshare|sina|tushare|yfinance|cached|auto
# cached: 优先从本地缓存读取，缺失数据从网络获取
# auto: 自动选择可用数据源
# 默认使用 cached 以提高性能和减少网络请求
DATA_SOURCE = os.environ.get('DATA_SOURCE', 'cached')

# API配置（如需要）
API_CONFIG = {
    'tushare_token': '',  # Tushare token
    'cache_enabled': True,
    'cache_expire': 300,  # 缓存过期时间（秒）
}

# ==================== 日志配置 ====================

LOG_CONFIG = {
    'enabled': True,
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'file': 'logs/stock_monitor.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
}

# ==================== 导出配置 ====================

EXPORT_CONFIG = {
    'auto_export': False,
    'export_format': 'xlsx',  # xlsx, csv, json
    'export_path': 'exports/',
}

# ==================== 预设监控方案 ====================

PRESET_PLANS = {
    'ai_chip': {
        'name': 'AI芯片主题',
        'stocks': {**AI_STOCKS, **CHIP_STOCKS},
        'indices': ['000001', '399006', '000688'],
    },
    'gold': {
        'name': '黄金主题',
        'stocks': GOLD_STOCKS,
        'indices': ['000001', '884004'],
    },
    'ev': {
        'name': '新能源汽车',
        'stocks': {**EV_DRIVE_STOCKS, **AI_COMPUTING_STOCKS},
        'indices': ['000001', '000800'],
    },
    'blue_chip': {
        'name': '优质蓝筹',
        'stocks': BLUE_CHIP_STOCKS,
        'indices': ['000001', '000300', '000016'],
    },
    'tech': {
        'name': '科技综合',
        'stocks': {**AI_STOCKS, **CHIP_STOCKS, **ELECTRONICS_STOCKS},
        'indices': ['399006', '000688'],
    },
}

# ==================== 辅助函数 ====================

def get_stock_groups():
    """获取所有股票分组"""
    return {
        'AI': AI_STOCKS,
        '芯片': CHIP_STOCKS,
        '电子': ELECTRONICS_STOCKS,
        '电驱': EV_DRIVE_STOCKS,
        '黄金': GOLD_STOCKS,
        '蓝筹': BLUE_CHIP_STOCKS,
        'AI算力': AI_COMPUTING_STOCKS,
        '数据中心': DATA_CENTER_STOCKS,
    }

# 股票分组常量，便于其他模块使用
STOCK_GROUPS = get_stock_groups()

def get_preset_plan(plan_name):
    """获取预设方案"""
    return PRESET_PLANS.get(plan_name, None)

def get_all_stocks():
    """获取所有股票代码"""
    all_stocks = {}
    for group in get_stock_groups().values():
        all_stocks.update(group)
    return all_stocks
