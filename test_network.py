#!/usr/bin/env python3
"""
网络连接诊断工具
"""

import requests
import time
import akshare as ak
from datetime import datetime

def test_basic_connection():
    """测试基本网络连接"""
    print("=" * 50)
    print("🔍 网络连接诊断开始")
    print("=" * 50)
    
    # 测试基本HTTP连接
    test_urls = [
        "https://www.baidu.com",
        "https://www.eastmoney.com", 
        "http://data.eastmoney.com",
        "https://finance.sina.com.cn"
    ]
    
    for url in test_urls:
        try:
            print(f"\n📡 测试连接: {url}")
            start_time = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start_time
            print(f"  ✅ 状态码: {response.status_code}, 耗时: {elapsed:.2f}秒")
        except Exception as e:
            print(f"  ❌ 连接失败: {e}")

def test_akshare_with_different_configs():
    """测试不同配置下的AKShare连接"""
    print("\n" + "=" * 50)
    print("🔧 测试AKShare不同配置")
    print("=" * 50)
    
    configs = [
        {
            "name": "默认配置",
            "headers": {}
        },
        {
            "name": "标准浏览器头",
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        },
        {
            "name": "Chrome浏览器头",
            "headers": {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        }
    ]
    
    for config in configs:
        print(f"\n🔄 测试配置: {config['name']}")
        try:
            # 模拟设置headers (akshare内部使用requests)
            if config['headers']:
                import requests
                original_get = requests.get
                def patched_get(*args, **kwargs):
                    if 'headers' not in kwargs:
                        kwargs['headers'] = {}
                    kwargs['headers'].update(config['headers'])
                    return original_get(*args, **kwargs)
                requests.get = patched_get
            
            # 测试获取少量数据
            print("  📊 尝试获取股票数据...")
            start_time = time.time()
            
            # 直接测试核心API
            df = ak.stock_zh_a_spot_em()
            elapsed = time.time() - start_time
            
            if df is not None and len(df) > 0:
                print(f"  ✅ 成功获取 {len(df)} 条股票数据，耗时: {elapsed:.2f}秒")
                print(f"  📈 示例数据: {df.iloc[0]['名称']} ({df.iloc[0]['代码']})")
                return True
            else:
                print(f"  ⚠ 返回空数据，耗时: {elapsed:.2f}秒")
                
        except Exception as e:
            elapsed = time.time() - start_time
            error_str = str(e)
            print(f"  ❌ 失败，耗时: {elapsed:.2f}秒")
            
            if 'connection aborted' in error_str.lower():
                print(f"    🔍 连接中断错误: {e}")
            elif 'timeout' in error_str.lower():
                print(f"    ⏰ 超时错误: {e}")
            elif 'ssl' in error_str.lower():
                print(f"    🔒 SSL错误: {e}")
            else:
                print(f"    ❓ 其他错误: {e}")
        finally:
            # 恢复原始requests.get
            if config['headers']:
                requests.get = original_get
    
    return False

def test_manual_request():
    """手动测试东方财富API"""
    print("\n" + "=" * 50)
    print("🚀 手动测试东方财富API")
    print("=" * 50)
    
    # 这是akshare实际使用的URL之一
    test_url = "http://82.push2.eastmoney.com/api/qt/clist/get"
    params = {
        'pn': '1',
        'pz': '20',
        'po': '1',
        'np': '1',
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': '2',
        'invt': '2',
        'fid': 'f3',
        'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
        'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'http://quote.eastmoney.com/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    try:
        print(f"📡 请求URL: {test_url}")
        print(f"📋 参数: {params}")
        
        start_time = time.time()
        response = requests.get(test_url, params=params, headers=headers, timeout=15)
        elapsed = time.time() - start_time
        
        print(f"✅ 状态码: {response.status_code}")
        print(f"⏱ 耗时: {elapsed:.2f}秒")
        print(f"📏 响应长度: {len(response.text)} 字符")
        
        if response.status_code == 200:
            # 检查响应内容
            content = response.text[:200]
            print(f"📄 响应内容预览: {content}...")
            return True
        else:
            print(f"❌ HTTP错误状态码: {response.status_code}")
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ 请求失败，耗时: {elapsed:.2f}秒")
        print(f"🔍 错误详情: {e}")
        
    return False

def main():
    """主函数"""
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 测试基本网络连接
    test_basic_connection()
    
    # 2. 测试手动请求
    manual_success = test_manual_request()
    
    # 3. 测试AKShare不同配置
    akshare_success = test_akshare_with_different_configs()
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 诊断总结")
    print("=" * 50)
    print(f"🌐 手动API请求: {'✅ 成功' if manual_success else '❌ 失败'}")
    print(f"📚 AKShare库调用: {'✅ 成功' if akshare_success else '❌ 失败'}")
    
    if not manual_success:
        print("\n💡 建议：")
        print("  1. 检查网络连接是否正常")
        print("  2. 检查防火墙设置")
        print("  3. 尝试使用VPN或代理")
        print("  4. 稍后重试（可能是服务器临时限制）")
    elif not akshare_success:
        print("\n💡 建议：")
        print("  1. 更新AKShare到最新版本: pip install akshare --upgrade")
        print("  2. 东方财富可能更新了反爬虫策略")
        print("  3. 尝试降低请求频率")
        print("  4. 考虑使用备用数据源")

if __name__ == "__main__":
    main()