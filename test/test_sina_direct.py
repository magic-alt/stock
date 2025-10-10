#!/usr/bin/env python3
"""
简化的新浪财经数据源测试
直接使用新浪API，不依赖AKShare
"""

import requests
import pandas as pd
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.safe_cast import safe_float, safe_int


class SimpleSinaDataSource:
    """简化的新浪数据源"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
        })
    
    def get_stock_data(self, stock_codes):
        """获取股票数据"""
        try:
            # 构建新浪API查询
            sina_codes = []
            for code in stock_codes:
                if code.startswith('0') or code.startswith('3'):
                    sina_codes.append(f'sz{code}')
                else:
                    sina_codes.append(f'sh{code}')
            
            codes_str = ','.join(sina_codes)
            url = f"http://hq.sinajs.cn/list={codes_str}"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            data = []
            lines = response.text.strip().split('\n')
            
            for line in lines:
                if 'hq_str_' in line and '=' in line:
                    stock_data = self._parse_stock_line(line)
                    if stock_data:
                        data.append(stock_data)
            
            return pd.DataFrame(data) if data else None
            
        except Exception as e:
            print(f"获取股票数据失败: {e}")
            return None
    
    def get_index_data(self, index_codes):
        """获取指数数据"""
        try:
            # 构建新浪指数查询
            sina_codes = []
            for code in index_codes:
                if code.startswith('000'):
                    sina_codes.append(f'sh{code}')
                elif code.startswith('399'):
                    sina_codes.append(f'sz{code}')
                else:
                    sina_codes.append(f'sh{code}')
            
            codes_str = ','.join(sina_codes)
            url = f"http://hq.sinajs.cn/list={codes_str}"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None
            
            data = []
            lines = response.text.strip().split('\n')
            
            for line in lines:
                if 'hq_str_' in line and '=' in line:
                    index_data = self._parse_index_line(line)
                    if index_data:
                        data.append(index_data)
            
            return pd.DataFrame(data) if data else None
            
        except Exception as e:
            print(f"获取指数数据失败: {e}")
            return None
    
    def _parse_stock_line(self, line):
        """解析股票数据行"""
        try:
            # 提取股票代码
            code_part = line.split('hq_str_')[1].split('=')[0]
            stock_code = code_part[2:]  # 去掉sh/sz前缀
            
            # 提取数据部分
            data_part = line.split('="')[1].split('";')[0]
            fields = data_part.split(',')
            
            if len(fields) < 10:
                return None
            
            current_price = safe_float(fields[3])
            prev_close = safe_float(fields[2])
            
            return {
                '代码': stock_code,
                '名称': fields[0],
                '最新价': current_price,
                '今开': safe_float(fields[1]),
                '昨收': prev_close,
                '最高': safe_float(fields[4]),
                '最低': safe_float(fields[5]),
                '涨跌额': current_price - prev_close if current_price and prev_close else 0,
                '涨跌幅': ((current_price - prev_close) / prev_close * 100) if current_price and prev_close and prev_close > 0 else 0,
                '成交量': safe_int(fields[8]),
                '成交额': safe_float(fields[9]),
                '更新时间': datetime.now().strftime('%H:%M:%S'),
            }
        except Exception as e:
            print(f"解析股票数据失败: {e}")
            return None
    
    def _parse_index_line(self, line):
        """解析指数数据行"""
        try:
            # 提取指数代码
            code_part = line.split('hq_str_')[1].split('=')[0]
            index_code = code_part[2:]  # 去掉sh/sz前缀
            
            # 提取数据部分
            data_part = line.split('="')[1].split('";')[0]
            fields = data_part.split(',')
            
            if len(fields) < 10:
                return None
            
            current_price = safe_float(fields[3])
            prev_close = safe_float(fields[2])
            
            return {
                '代码': index_code,
                '名称': fields[0],
                '最新价': current_price,
                '今开': safe_float(fields[1]),
                '昨收': prev_close,
                '最高': safe_float(fields[4]),
                '最低': safe_float(fields[5]),
                '涨跌额': current_price - prev_close if current_price and prev_close else 0,
                '涨跌幅': ((current_price - prev_close) / prev_close * 100) if current_price and prev_close and prev_close > 0 else 0,
                '成交量': safe_int(fields[8]),
                '成交额': safe_float(fields[9]),
                '更新时间': datetime.now().strftime('%H:%M:%S'),
            }
        except Exception as e:
            print(f"解析指数数据失败: {e}")
            return None


def test_sina_direct():
    """测试直接新浪API"""
    print("=" * 60)
    print("🔗 直接新浪API测试")
    print("=" * 60)
    
    sina = SimpleSinaDataSource()
    
    # 测试股票数据
    print("\n📈 测试股票数据:")
    print("-" * 40)
    test_stocks = ['000001', '000002', '600519', '300750']
    
    stock_df = sina.get_stock_data(test_stocks)
    if stock_df is not None and not stock_df.empty:
        print(f"✅ 成功获取 {len(stock_df)} 只股票数据")
        for _, row in stock_df.iterrows():
            print(f"  {row['代码']} {row['名称']}: {row['最新价']} ({row['涨跌幅']:.2f}%)")
    else:
        print("❌ 获取股票数据失败")
    
    # 测试指数数据
    print(f"\n📊 测试指数数据:")
    print("-" * 40)
    test_indices = ['000001', '399001', '399006']
    
    index_df = sina.get_index_data(test_indices)
    if index_df is not None and not index_df.empty:
        print(f"✅ 成功获取 {len(index_df)} 个指数数据")
        for _, row in index_df.iterrows():
            print(f"  {row['代码']} {row['名称']}: {row['最新价']} ({row['涨跌幅']:.2f}%)")
    else:
        print("❌ 获取指数数据失败")
    
    print("\n" + "=" * 60)
    print("🎉 新浪API测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_sina_direct()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断测试")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()