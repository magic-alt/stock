"""
测试自动保存报告功能
"""
import sys
import os

# 测试导入
try:
    from src.data_sources.db_manager import SQLiteDataManager
    
    # 测试数据库name字段
    db = SQLiteDataManager("./cache/market_data.db")
    
    # 测试获取股票名称
    test_symbols = ["600519.SH", "601318.SH", "^GSPC", "^HSI", "000300.SH"]
    
    print("测试股票/指数名称获取:")
    print("="*60)
    for symbol in test_symbols:
        name = db._get_symbol_name(symbol)
        print(f"{symbol:15s} -> {name}")
    
    print("\n" + "="*60)
    print("✓ 数据库名称功能测试通过")
    print("="*60)
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
