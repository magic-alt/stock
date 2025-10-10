"""
应急数据源配置
当AKShare连接失败时，自动切换到新浪财经
"""

# 临时应急开关
USE_SINA_BACKUP = True

# 支持的股票代码（新浪格式）
SUPPORTED_STOCKS = {
    "000001": "sh000001",  # 上证指数
    "399001": "sz399001",  # 深证成指
    "399006": "sz399006",  # 创业板指
    "600519": "sh600519",  # 贵州茅台
    "000858": "sz000858",  # 五粮液
    "000001": "sz000001",  # 平安银行（深市）
    "600036": "sh600036",  # 招商银行
    "000002": "sz000002",  # 万科A
    "300750": "sz300750",  # 宁德时代
}

def get_sina_code(stock_code: str) -> str:
    """转换股票代码为新浪格式"""
    if stock_code in SUPPORTED_STOCKS:
        return SUPPORTED_STOCKS[stock_code]
    elif stock_code.startswith('6'):
        return f"sh{stock_code}"
    elif stock_code.startswith(('0', '3')):
        return f"sz{stock_code}"
    else:
        return stock_code
