"""
测试使用AKShare数据源进行缓存
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.data_sources.cached_source import CachedDataSource
from src.data_sources.akshare_source import AKShareDataSource

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_akshare_cache():
    """测试AKShare与缓存的集成"""
    print("🧪 测试AKShare数据源缓存集成")
    print("="*50)
    
    try:
        # 创建AKShare数据源
        akshare_source = AKShareDataSource()
        
        # 创建缓存数据源，使用AKShare作为底层数据源
        cached_source = CachedDataSource(underlying_source=akshare_source, cache_dir="akshare_cache")
        
        print("✅ 缓存数据源初始化成功")
        
        # 测试获取历史数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        
        print(f"\n📊 测试获取股票历史数据: 000001 ({start_date} ~ {end_date})")
        
        # 第一次获取（从网络）
        print("🌐 第一次获取（从网络）...")
        start_time = datetime.now()
        data1 = cached_source.get_stock_history('000001', start_date, end_date)
        time1 = (datetime.now() - start_time).total_seconds()
        
        if not data1.empty:
            print(f"✅ 获取成功: {len(data1)} 条记录, 耗时: {time1:.2f}秒")
            print(f"📅 数据范围: {data1.index.min()} ~ {data1.index.max()}")
        else:
            print("❌ 获取失败")
            return False
        
        # 第二次获取（从缓存）
        print("\n📋 第二次获取（从缓存）...")
        start_time = datetime.now()
        data2 = cached_source.get_stock_history('000001', start_date, end_date)
        time2 = (datetime.now() - start_time).total_seconds()
        
        if not data2.empty:
            print(f"✅ 获取成功: {len(data2)} 条记录, 耗时: {time2:.2f}秒")
            print(f"📅 数据范围: {data2.index.min()} ~ {data2.index.max()}")
        else:
            print("❌ 获取失败")
            return False
        
        # 比较性能
        if time1 > 0 and time2 > 0:
            speedup = time1 / time2
            print(f"\n🚀 缓存提速: {speedup:.1f}倍")
        
        # 验证数据一致性
        if len(data1) == len(data2):
            print("✅ 数据一致性验证通过")
        else:
            print(f"⚠️ 数据不一致: {len(data1)} vs {len(data2)}")
        
        # 显示缓存统计
        stats = cached_source.get_cache_stats()
        print(f"\n📊 缓存统计:")
        print(f"   股票数量: {stats.get('stock_symbols', 0)}")
        print(f"   记录数: {stats.get('stock_records', 0)}")
        print(f"   数据库大小: {stats.get('db_size_mb', 0):.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_performance():
    """测试缓存性能"""
    print("\n🏁 缓存性能测试")
    print("="*50)
    
    try:
        cached_source = CachedDataSource(cache_dir="akshare_cache")
        
        # 测试多个股票的批量获取
        stock_codes = ['000001', '000002', '600000', '600036', '000858']
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        print(f"📊 批量获取 {len(stock_codes)} 只股票的历史数据")
        
        total_records = 0
        success_count = 0
        
        start_time = datetime.now()
        
        for i, stock_code in enumerate(stock_codes, 1):
            print(f"   [{i}/{len(stock_codes)}] {stock_code}...", end="")
            try:
                data = cached_source.get_stock_history(stock_code, start_date, end_date)
                if not data.empty:
                    total_records += len(data)
                    success_count += 1
                    print(f" ✅ {len(data)}条")
                else:
                    print(" ❌ 无数据")
            except Exception as e:
                print(f" ❌ 异常: {e}")
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n📈 批量获取结果:")
        print(f"   成功: {success_count}/{len(stock_codes)}")
        print(f"   总记录数: {total_records}")
        print(f"   总耗时: {total_time:.2f}秒")
        print(f"   平均每只股票: {total_time/len(stock_codes):.2f}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False


if __name__ == '__main__':
    try:
        print("🚀 开始AKShare缓存测试")
        
        # 基础功能测试
        test1_result = test_akshare_cache()
        
        # 性能测试
        test2_result = test_cache_performance()
        
        print("\n" + "="*60)
        print("📊 测试结果汇总")
        print("="*60)
        print(f"{'✅' if test1_result else '❌'} 基础缓存功能")
        print(f"{'✅' if test2_result else '❌'} 性能测试")
        
        if test1_result and test2_result:
            print("\n🎉 所有测试通过！AKShare缓存系统工作正常")
        else:
            print("\n⚠️ 部分测试失败，请检查配置")
            
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试运行异常: {e}")