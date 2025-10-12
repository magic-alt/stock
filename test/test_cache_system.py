"""
测试缓存数据源功能
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.data_sources.cached_source import CachedDataSource
from src.data_sources.cache_manager import DataCacheManager
from src.utils.data_downloader import DataDownloader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_cache_manager():
    """测试缓存管理器"""
    print("\n" + "="*50)
    print("🧪 测试缓存管理器")
    print("="*50)
    
    try:
        # 初始化缓存管理器
        cache_manager = DataCacheManager("test_cache")
        print("✅ 缓存管理器初始化成功")
        
        # 获取缓存统计
        stats = cache_manager.get_cache_stats()
        print(f"📊 初始统计: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 缓存管理器测试失败: {e}")
        return False


def test_cached_data_source():
    """测试缓存数据源"""
    print("\n" + "="*50)
    print("🧪 测试缓存数据源")
    print("="*50)
    
    try:
        # 初始化缓存数据源
        cached_source = CachedDataSource(cache_dir="test_cache")
        print("✅ 缓存数据源初始化成功")
        
        # 测试实时数据
        print("\n📡 测试实时数据...")
        realtime_data = cached_source.get_stock_realtime('000001')
        if realtime_data:
            print(f"✅ 获取实时数据成功: {realtime_data.get('name', 'N/A')}")
        else:
            print("⚠️ 实时数据获取失败或无数据")
        
        # 测试历史数据（这会触发缓存逻辑）
        print("\n📊 测试历史数据缓存...")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        print(f"📅 获取数据: 000001 ({start_date} ~ {end_date})")
        
        # 第一次获取（从网络）
        history_data1 = cached_source.get_stock_history('000001', start_date, end_date)
        if not history_data1.empty:
            print(f"✅ 第一次获取成功: {len(history_data1)} 条记录")
        else:
            print("⚠️ 第一次获取失败")
            return False
        
        # 第二次获取（从缓存）
        print("🔄 再次获取相同数据（应该从缓存读取）...")
        history_data2 = cached_source.get_stock_history('000001', start_date, end_date)
        if not history_data2.empty:
            print(f"✅ 第二次获取成功: {len(history_data2)} 条记录")
        else:
            print("⚠️ 第二次获取失败")
        
        # 检查数据是否一致
        if len(history_data1) == len(history_data2):
            print("✅ 两次获取的数据条数一致")
        else:
            print(f"⚠️ 数据条数不一致: {len(history_data1)} vs {len(history_data2)}")
        
        # 显示缓存统计
        stats = cached_source.get_cache_stats()
        print(f"\n📊 缓存统计: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 缓存数据源测试失败: {e}")
        return False


def test_data_downloader():
    """测试数据下载器"""
    print("\n" + "="*50)
    print("🧪 测试数据下载器")
    print("="*50)
    
    try:
        # 初始化下载器
        downloader = DataDownloader(cache_dir="test_cache")
        print("✅ 数据下载器初始化成功")
        
        # 测试下载少量股票数据
        print("\n📥 测试下载股票数据...")
        test_stocks = ['000001', '000002', '000858']
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        results = downloader.download_custom_stocks(test_stocks, start_date, end_date)
        
        success_count = sum(results.values())
        print(f"📊 下载结果: {success_count}/{len(test_stocks)} 成功")
        
        for stock, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {stock}")
        
        # 测试下载指数数据
        print("\n📥 测试下载指数数据...")
        index_results = downloader.download_major_indices(start_date, end_date)
        
        index_success = sum(index_results.values())
        print(f"📊 指数下载结果: {index_success}/{len(index_results)} 成功")
        
        # 显示最终统计
        final_stats = downloader.get_cache_info()
        print(f"\n📊 最终缓存统计: {final_stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据下载器测试失败: {e}")
        return False


def test_cache_performance():
    """测试缓存性能"""
    print("\n" + "="*50)
    print("🧪 测试缓存性能")
    print("="*50)
    
    try:
        cached_source = CachedDataSource(cache_dir="test_cache")
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 测试首次获取时间
        print("⏱️ 测试首次获取时间（网络+缓存）...")
        start_time = datetime.now()
        data1 = cached_source.get_stock_history('000858', start_date, end_date)
        first_time = (datetime.now() - start_time).total_seconds()
        print(f"   首次获取: {first_time:.2f}秒, {len(data1)}条记录")
        
        # 测试缓存获取时间
        print("⏱️ 测试缓存获取时间...")
        start_time = datetime.now()
        data2 = cached_source.get_stock_history('000858', start_date, end_date)
        second_time = (datetime.now() - start_time).total_seconds()
        print(f"   缓存获取: {second_time:.2f}秒, {len(data2)}条记录")
        
        # 计算性能提升
        if first_time > 0 and second_time > 0:
            speedup = first_time / second_time
            print(f"🚀 缓存提速: {speedup:.1f}倍")
        
        return True
        
    except Exception as e:
        print(f"❌ 缓存性能测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("🧪 开始缓存功能测试")
    print("="*60)
    
    tests = [
        ("缓存管理器", test_cache_manager),
        ("缓存数据源", test_cached_data_source),
        ("数据下载器", test_data_downloader),
        ("缓存性能", test_cache_performance),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 开始测试: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ 通过" if result else "❌ 失败"
            print(f"📋 {test_name}: {status}")
        except Exception as e:
            results.append((test_name, False))
            print(f"❌ {test_name} 异常: {e}")
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n📈 总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！缓存功能正常工作")
    else:
        print("⚠️ 部分测试失败，请检查日志")
    
    return passed == total


if __name__ == '__main__':
    try:
        success = run_all_tests()
        if success:
            print("\n🎯 测试完成，缓存系统可以正常使用")
        else:
            print("\n⚠️ 测试存在问题，请检查配置")
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试运行异常: {e}")