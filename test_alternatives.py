#!/usr/bin/env python3
"""
尝试备用数据获取方法
"""

import requests
import json
import time
from datetime import datetime

def test_alternative_eastmoney_api():
    """测试备用的东方财富API"""
    print("🔄 尝试备用东方财富API...")
    
    # 备用API地址
    alternative_urls = [
        "http://push2.eastmoney.com/api/qt/clist/get",
        "http://push2his.eastmoney.com/api/qt/stock/kline/get", 
        "http://datacenter-web.eastmoney.com/api/data/v1/get"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'http://quote.eastmoney.com/',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    for url in alternative_urls:
        try:
            print(f"  📡 测试: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            print(f"    状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"    ✅ 成功连接备用API")
                return True
        except Exception as e:
            print(f"    ❌ 失败: {e}")
    
    return False

def test_sina_finance_api():
    """测试新浪财经API作为备用"""
    print("\n🔄 尝试新浪财经API...")
    
    # 新浪财经实时数据API
    test_stocks = ["sh000001", "sz399001", "sh600519"]  # 上证指数、深证成指、茅台
    
    for stock in test_stocks:
        try:
            url = f"http://hq.sinajs.cn/list={stock}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://finance.sina.com.cn/'
            }
            
            print(f"  📊 测试股票: {stock}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200 and len(response.text) > 50:
                print(f"    ✅ 成功获取数据: {response.text[:100]}...")
                return True
            else:
                print(f"    ⚠ 响应异常: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ 失败: {e}")
    
    return False

def test_tencent_finance_api():
    """测试腾讯财经API"""
    print("\n🔄 尝试腾讯财经API...")
    
    try:
        # 腾讯财经接口
        url = "http://qt.gtimg.cn/q=sh000001,sz399001"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://finance.qq.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200 and len(response.text) > 20:
            print(f"    ✅ 成功获取数据: {response.text[:100]}...")
            return True
        else:
            print(f"    ❌ 响应异常: {response.status_code}")
            
    except Exception as e:
        print(f"    ❌ 失败: {e}")
    
    return False

def check_akshare_version_and_update():
    """检查并更新AKShare版本"""
    print("\n🔄 检查AKShare版本...")
    
    try:
        import akshare as ak
        current_version = ak.__version__
        print(f"    当前版本: {current_version}")
        
        # 检查最新版本（通过PyPI API）
        try:
            response = requests.get("https://pypi.org/pypi/akshare/json", timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest_version = data['info']['version']
                print(f"    最新版本: {latest_version}")
                
                if current_version != latest_version:
                    print(f"    💡 发现新版本，建议更新: pip install akshare=={latest_version}")
                    return False
                else:
                    print(f"    ✅ 已是最新版本")
        except:
            print(f"    ⚠ 无法检查最新版本")
            
    except Exception as e:
        print(f"    ❌ 检查失败: {e}")
        return False
    
    return True

def main():
    """主测试函数"""
    print("🔍 备用数据源测试")
    print("=" * 40)
    
    results = {
        "eastmoney_backup": test_alternative_eastmoney_api(),
        "sina_finance": test_sina_finance_api(), 
        "tencent_finance": test_tencent_finance_api(),
        "akshare_updated": check_akshare_version_and_update()
    }
    
    print("\n" + "=" * 40)
    print("📊 测试结果总结")
    print("=" * 40)
    
    working_sources = []
    for source, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {source}: {status}")
        if status:
            working_sources.append(source)
    
    print(f"\n💡 解决方案建议:")
    
    if len(working_sources) > 0:
        print(f"✅ 可用数据源: {', '.join(working_sources)}")
        if "sina_finance" in working_sources:
            print("📈 建议临时切换到新浪财经数据源")
        if "tencent_finance" in working_sources:
            print("📈 可以使用腾讯财经作为备用")
    else:
        print("❌ 所有测试的数据源都无法访问")
        print("🔧 可能的解决方案:")
        print("   1. 等待10-30分钟后重试（服务器可能临时限制）")
        print("   2. 更换网络环境（如移动热点）") 
        print("   3. 使用VPN更换IP地址")
        print("   4. 联系网络管理员检查防火墙设置")
    
    if not results["akshare_updated"]:
        print("📦 建议更新AKShare到最新版本")

if __name__ == "__main__":
    main()