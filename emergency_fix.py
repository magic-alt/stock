#!/usr/bin/env python3
"""
临时修复：直接使用新浪财经API测试
"""

import requests
import json
from datetime import datetime

def test_sina_api():
    """测试新浪财经API"""
    print("🔍 测试新浪财经API")
    print("=" * 40)
    
    # 测试股票列表
    test_stocks = [
        ('sh000001', '上证指数'),
        ('sz399001', '深证成指'), 
        ('sh600519', '贵州茅台'),
        ('sz000001', '平安银行'),
        ('sz300750', '宁德时代')
    ]
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'http://finance.sina.com.cn/'
    })
    
    success_count = 0
    for code, name in test_stocks:
        try:
            url = f"http://hq.sinajs.cn/list={code}"
            response = session.get(url, timeout=10)
            
            if response.status_code == 200 and len(response.text) > 50:
                # 解析数据
                import re
                match = re.search(r'var hq_str_[^=]+="([^"]+)"', response.text)
                if match:
                    data_parts = match.group(1).split(',')
                    if len(data_parts) >= 4:
                        current_price = data_parts[3] if 'sh0000' in code or 'sz3999' in code else data_parts[3]
                        print(f"✅ {name}({code}): {current_price}")
                        success_count += 1
                    else:
                        print(f"⚠ {name}({code}): 数据格式异常")
                else:
                    print(f"❌ {name}({code}): 无法解析数据")
            else:
                print(f"❌ {name}({code}): HTTP错误 {response.status_code}")
                
        except Exception as e:
            print(f"❌ {name}({code}): {e}")
    
    print(f"\n📊 测试结果: {success_count}/{len(test_stocks)} 成功")
    return success_count > 0

def create_emergency_data_source():
    """创建应急数据源配置"""
    print("\n🚨 创建应急配置...")
    
    config_content = '''"""
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
'''
    
    with open('emergency_config.py', 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print("✅ 应急配置文件已创建: emergency_config.py")

def create_quick_test_script():
    """创建快速测试脚本"""
    
    test_script = '''#!/usr/bin/env python3
"""
快速数据测试脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_sources.sina_source import SinaDataSource

def main():
    print("🔍 快速数据源测试")
    print("=" * 30)
    
    # 创建新浪数据源
    sina = SinaDataSource()
    
    # 测试股票
    test_codes = ['600519', '000001', '300750']
    
    for code in test_codes:
        print(f"\\n📊 测试股票: {code}")
        data = sina.get_stock_realtime(code)
        
        if data:
            print(f"  ✅ {data.get('名称', 'N/A')}: {data.get('最新价', 'N/A')}")
            print(f"  📈 涨跌幅: {data.get('涨跌幅', 'N/A'):.2f}%")
        else:
            print(f"  ❌ 获取失败")

if __name__ == "__main__":
    main()
'''
    
    with open('quick_test.py', 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print("✅ 快速测试脚本已创建: quick_test.py")

def main():
    """主函数"""
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 测试新浪API
    sina_ok = test_sina_api()
    
    if sina_ok:
        print("\n✅ 新浪财经API可用，可以作为备用数据源")
        
        # 2. 创建应急配置
        create_emergency_data_source()
        
        # 3. 创建快速测试脚本
        create_quick_test_script()
        
        print("\n💡 使用建议:")
        print("  1. 运行 'python quick_test.py' 测试新浪数据源")
        print("  2. 在主程序中设置数据源类型为 'sina'")
        print("  3. 或者使用 'auto' 让系统自动选择可用源")
        print("  4. 等待AKShare官方修复网络问题")
        
    else:
        print("\n❌ 新浪财经API也无法访问")
        print("💡 建议检查网络连接或稍后重试")

if __name__ == "__main__":
    main()