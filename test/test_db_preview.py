"""
测试数据库预览功能
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sqlite3
from pathlib import Path


def test_database_content():
    """测试数据库内容"""
    print("🔍 检查数据库内容")
    print("="*60)
    
    db_path = Path("datacache") / "stock_data.db"
    
    if not db_path.exists():
        print("❌ 数据库文件不存在")
        return
    
    print(f"✅ 数据库路径: {db_path}")
    print(f"📦 数据库大小: {db_path.stat().st_size / 1024:.2f} KB")
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 检查表结构
        print("\n📋 表结构:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"   • {table[0]}")
        
        # 统计数据
        print("\n📊 数据统计:")
        
        cursor.execute("SELECT COUNT(*) FROM stock_history")
        stock_count = cursor.fetchone()[0]
        print(f"   股票历史数据: {stock_count:,} 条")
        
        cursor.execute("SELECT COUNT(DISTINCT stock_code) FROM stock_history")
        stock_symbols = cursor.fetchone()[0]
        print(f"   股票数量: {stock_symbols} 只")
        
        cursor.execute("SELECT COUNT(*) FROM index_history")
        index_count = cursor.fetchone()[0]
        print(f"   指数历史数据: {index_count:,} 条")
        
        cursor.execute("SELECT COUNT(DISTINCT index_code) FROM index_history")
        index_symbols = cursor.fetchone()[0]
        print(f"   指数数量: {index_symbols} 个")
        
        cursor.execute("SELECT COUNT(*) FROM data_updates")
        update_count = cursor.fetchone()[0]
        print(f"   更新记录: {update_count} 条")
        
        # 显示样例数据
        print("\n📈 股票数据样例（最近5条）:")
        cursor.execute("""
            SELECT stock_code, date, open, close, volume
            FROM stock_history
            ORDER BY date DESC, stock_code
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        if results:
            print(f"   {'代码':<10} {'日期':<12} {'开盘':<10} {'收盘':<10} {'成交量':<15}")
            print("   " + "-"*60)
            for row in results:
                volume_str = f"{int(row[4]):,}" if row[4] else "N/A"
                print(f"   {row[0]:<10} {row[1]:<12} {row[2]:<10.2f} {row[3]:<10.2f} {volume_str:<15}")
        
        # 检查数据完整性
        print("\n✅ 数据检查:")
        cursor.execute("""
            SELECT stock_code, COUNT(*) as count
            FROM stock_history
            GROUP BY stock_code
            HAVING COUNT(*) > 0
            ORDER BY count DESC
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        if results:
            print("   数据量最多的5只股票:")
            for row in results:
                print(f"   • {row[0]}: {row[1]} 条记录")


def test_command_line_preview():
    """测试命令行预览功能"""
    print("\n" + "="*60)
    print("🧪 测试命令行预览功能")
    print("="*60)
    
    print("\n可用命令:")
    print("# 查看数据库汇总")
    print("python data_manager.py preview")
    
    print("\n# 查看指定股票")
    print("python data_manager.py preview --type stock --symbol 000001")
    
    print("\n# 查看指定指数")
    print("python data_manager.py preview --type index --symbol 000001")


if __name__ == '__main__':
    try:
        test_database_content()
        test_command_line_preview()
        
        print("\n" + "="*60)
        print("✅ 数据库检查完成")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()