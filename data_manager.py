"""
数据管理命令行工具
用于下载、更新和管理本地股票数据缓存
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timedelta

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.data_downloader import DataDownloader
from src.data_sources.cached_source import CachedDataSource
from src.config import STOCK_GROUPS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_results(results: dict, title: str = "下载结果"):
    """格式化显示结果"""
    print(f"\n{'='*50}")
    print(f"📊 {title}")
    print(f"{'='*50}")
    
    if isinstance(results, dict):
        for key, value in results.items():
            if isinstance(value, dict):
                success_count = sum(1 for v in value.values() if v)
                total_count = len(value)
                print(f"📂 {key}: {success_count}/{total_count} 成功")
                
                # 显示失败的项目
                failed_items = [k for k, v in value.items() if not v]
                if failed_items:
                    print(f"   ❌ 失败: {', '.join(failed_items[:5])}")
                    if len(failed_items) > 5:
                        print(f"   ... 还有 {len(failed_items) - 5} 项失败")
            else:
                status = "✅" if value else "❌"
                print(f"{status} {key}")


def cmd_download_recent(args):
    """下载最近数据"""
    downloader = DataDownloader()
    
    days = args.days or 365
    groups = args.groups.split(',') if args.groups else None
    
    print(f"📥 开始下载最近 {days} 天的数据...")
    if groups:
        print(f"📂 目标股票组: {groups}")
    
    results = downloader.download_recent_data(days, groups)
    format_results(results, f"最近 {days} 天数据下载结果")


def cmd_download_stocks(args):
    """下载指定股票"""
    downloader = DataDownloader()
    
    stock_codes = args.stocks.split(',')
    start_date = args.start_date
    end_date = args.end_date or datetime.now().strftime('%Y-%m-%d')
    
    print(f"📥 下载股票数据: {len(stock_codes)} 只")
    print(f"📅 日期范围: {start_date} ~ {end_date}")
    
    results = downloader.download_custom_stocks(stock_codes, start_date, end_date)
    format_results(results, "自定义股票下载结果")


def cmd_download_indices(args):
    """下载指数数据"""
    downloader = DataDownloader()
    
    start_date = args.start_date
    end_date = args.end_date or datetime.now().strftime('%Y-%m-%d')
    
    print(f"📥 下载主要指数数据")
    print(f"📅 日期范围: {start_date} ~ {end_date}")
    
    results = downloader.download_major_indices(start_date, end_date)
    format_results(results, "指数数据下载结果")


def cmd_update_data(args):
    """更新数据"""
    downloader = DataDownloader()
    
    days_back = args.days or 7
    
    print(f"🔄 增量更新最近 {days_back} 天的数据...")
    
    results = downloader.update_data(days_back)
    format_results(results, f"数据更新结果（最近{days_back}天）")


def cmd_cache_info(args):
    """显示缓存信息"""
    cached_source = CachedDataSource()
    stats = cached_source.get_cache_stats()
    
    print(f"\n{'='*50}")
    print("📦 缓存信息")
    print(f"{'='*50}")
    print(f"📁 数据库路径: {stats.get('db_path', 'N/A')}")
    print(f"💾 数据库大小: {stats.get('db_size_mb', 0):.2f} MB")
    print(f"📈 股票数量: {stats.get('stock_symbols', 0)}")
    print(f"📊 股票记录数: {stats.get('stock_records', 0):,}")
    print(f"📉 指数数量: {stats.get('index_symbols', 0)}")
    print(f"📋 指数记录数: {stats.get('index_records', 0):,}")
    
    # 显示下载建议
    downloader = DataDownloader()
    suggestions = downloader.get_download_suggestions()
    
    if suggestions.get('recommendations'):
        print(f"\n💡 建议:")
        for rec in suggestions['recommendations']:
            print(f"   • {rec['message']}")


def cmd_preview_data(args):
    """预览数据库内容"""
    import sqlite3
    from pathlib import Path
    
    db_path = Path("datacache") / "stock_data.db"
    
    if not db_path.exists():
        print("❌ 数据库文件不存在")
        return
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        preview_type = args.type or 'summary'
        
        if preview_type == 'summary':
            # 显示汇总信息
            print(f"\n{'='*80}")
            print("📊 数据库内容预览")
            print(f"{'='*80}")
            
            # 股票数据
            cursor.execute('''
                SELECT stock_code, COUNT(*) as count, MIN(date) as start_date, MAX(date) as end_date
                FROM stock_history
                GROUP BY stock_code
                ORDER BY stock_code
                LIMIT 20
            ''')
            
            stock_results = cursor.fetchall()
            
            if stock_results:
                print(f"\n📈 股票数据（显示前20只）:")
                print(f"{'股票代码':<12} {'记录数':<10} {'开始日期':<15} {'结束日期':<15}")
                print("-" * 60)
                for row in stock_results:
                    print(f"{row[0]:<12} {row[1]:<10} {row[2]:<15} {row[3]:<15}")
            
            # 指数数据
            cursor.execute('''
                SELECT index_code, COUNT(*) as count, MIN(date) as start_date, MAX(date) as end_date
                FROM index_history
                GROUP BY index_code
                ORDER BY index_code
            ''')
            
            index_results = cursor.fetchall()
            
            if index_results:
                print(f"\n📉 指数数据:")
                print(f"{'指数代码':<12} {'记录数':<10} {'开始日期':<15} {'结束日期':<15}")
                print("-" * 60)
                for row in index_results:
                    print(f"{row[0]:<12} {row[1]:<10} {row[2]:<15} {row[3]:<15}")
        
        elif preview_type == 'stock' and args.symbol:
            # 显示指定股票的数据
            cursor.execute('''
                SELECT date, open, high, low, close, volume
                FROM stock_history
                WHERE stock_code = ?
                ORDER BY date DESC
                LIMIT 20
            ''', (args.symbol,))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\n📊 股票 {args.symbol} 最近20条数据:")
                print(f"{'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<15}")
                print("-" * 80)
                for row in results:
                    volume_str = f"{int(row[5]):,}" if row[5] else "N/A"
                    print(f"{row[0]:<12} {row[1]:<10.2f} {row[2]:<10.2f} {row[3]:<10.2f} {row[4]:<10.2f} {volume_str:<15}")
            else:
                print(f"❌ 未找到股票 {args.symbol} 的数据")
        
        elif preview_type == 'index' and args.symbol:
            # 显示指定指数的数据
            cursor.execute('''
                SELECT date, open, high, low, close, volume
                FROM index_history
                WHERE index_code = ?
                ORDER BY date DESC
                LIMIT 20
            ''', (args.symbol,))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\n📉 指数 {args.symbol} 最近20条数据:")
                print(f"{'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<15}")
                print("-" * 80)
                for row in results:
                    volume_str = f"{int(row[5]):,}" if row[5] else "N/A"
                    print(f"{row[0]:<12} {row[1]:<10.2f} {row[2]:<10.2f} {row[3]:<10.2f} {row[4]:<10.2f} {volume_str:<15}")
            else:
                print(f"❌ 未找到指数 {args.symbol} 的数据")


def cmd_clear_cache(args):
    """清空缓存"""
    cached_source = CachedDataSource()
    
    if args.symbol and args.type:
        print(f"🗑️ 清空缓存: {args.type} {args.symbol}")
        cached_source.clear_cache(args.symbol, args.type)
    else:
        confirm = input("⚠️ 确定要清空所有缓存数据吗？(y/N): ")
        if confirm.lower() == 'y':
            print("🗑️ 清空所有缓存数据...")
            cached_source.clear_cache()
            print("✅ 缓存清空完成")
        else:
            print("❌ 操作已取消")


def cmd_list_groups(args):
    """显示股票组"""
    print(f"\n{'='*50}")
    print("📂 预定义股票组")
    print(f"{'='*50}")
    
    for group_name, stocks in STOCK_GROUPS.items():
        print(f"\n📋 {group_name} ({len(stocks)}只):")
        # 显示前10只股票
        display_stocks = stocks[:10]
        for i in range(0, len(display_stocks), 5):
            print(f"   {' '.join(display_stocks[i:i+5])}")
        
        if len(stocks) > 10:
            print(f"   ... 还有 {len(stocks) - 10} 只股票")


def cmd_test_source(args):
    """测试数据源"""
    print("🧪 测试缓存数据源...")
    
    try:
        cached_source = CachedDataSource()
        
        # 测试获取实时数据
        print("📡 测试实时数据接口...")
        realtime_data = cached_source.get_stock_realtime('000001')
        if realtime_data:
            print("✅ 实时数据接口正常")
        else:
            print("⚠️ 实时数据接口异常")
        
        # 测试历史数据
        print("📊 测试历史数据接口...")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        history_data = cached_source.get_stock_history('000001', start_date, end_date)
        if not history_data.empty:
            print(f"✅ 历史数据接口正常，获取到 {len(history_data)} 条记录")
        else:
            print("⚠️ 历史数据接口异常或无数据")
        
        print("✅ 数据源测试完成")
        
    except Exception as e:
        print(f"❌ 数据源测试失败: {e}")


def main():
    parser = argparse.ArgumentParser(description='股票数据管理工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 下载最近数据
    parser_recent = subparsers.add_parser('download-recent', help='下载最近N天的数据')
    parser_recent.add_argument('--days', type=int, help='天数 (默认365)')
    parser_recent.add_argument('--groups', help='股票组，逗号分隔 (默认全部)')
    parser_recent.set_defaults(func=cmd_download_recent)
    
    # 下载指定股票
    parser_stocks = subparsers.add_parser('download-stocks', help='下载指定股票数据')
    parser_stocks.add_argument('stocks', help='股票代码，逗号分隔')
    parser_stocks.add_argument('start_date', help='开始日期 YYYY-MM-DD')
    parser_stocks.add_argument('--end-date', help='结束日期 (默认今天)')
    parser_stocks.set_defaults(func=cmd_download_stocks)
    
    # 下载指数数据
    parser_indices = subparsers.add_parser('download-indices', help='下载主要指数数据')
    parser_indices.add_argument('start_date', help='开始日期 YYYY-MM-DD')
    parser_indices.add_argument('--end-date', help='结束日期 (默认今天)')
    parser_indices.set_defaults(func=cmd_download_indices)
    
    # 更新数据
    parser_update = subparsers.add_parser('update', help='增量更新数据')
    parser_update.add_argument('--days', type=int, help='往前多少天 (默认7)')
    parser_update.set_defaults(func=cmd_update_data)
    
    # 缓存信息
    parser_info = subparsers.add_parser('cache-info', help='显示缓存信息')
    parser_info.set_defaults(func=cmd_cache_info)
    
    # 预览数据
    parser_preview = subparsers.add_parser('preview', help='预览数据库内容')
    parser_preview.add_argument('--type', choices=['summary', 'stock', 'index'], 
                               default='summary', help='预览类型')
    parser_preview.add_argument('--symbol', help='股票或指数代码')
    parser_preview.set_defaults(func=cmd_preview_data)
    
    # 清空缓存
    parser_clear = subparsers.add_parser('clear-cache', help='清空缓存')
    parser_clear.add_argument('--symbol', help='指定符号')
    parser_clear.add_argument('--type', choices=['stock', 'index'], help='符号类型')
    parser_clear.set_defaults(func=cmd_clear_cache)
    
    # 列出股票组
    parser_groups = subparsers.add_parser('list-groups', help='显示预定义股票组')
    parser_groups.set_defaults(func=cmd_list_groups)
    
    # 测试数据源
    parser_test = subparsers.add_parser('test', help='测试数据源连接')
    parser_test.set_defaults(func=cmd_test_source)
    
    args = parser.parse_args()
    
    if args.command:
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\n❌ 操作被用户中断")
        except Exception as e:
            logger.error(f"❌ 命令执行失败: {e}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()