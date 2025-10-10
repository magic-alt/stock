"""
启动脚本：确保使用最新代码
清理缓存并启动实时监控
"""

import sys
import os
import subprocess

print("=" * 80)
print("A股实时监控系统 - 启动器")
print("=" * 80)

print("\n1. 清理 Python 字节码缓存...")

# 清理 __pycache__ 目录
cache_dirs = []
for root, dirs, files in os.walk('src'):
    if '__pycache__' in dirs:
        cache_dir = os.path.join(root, '__pycache__')
        cache_dirs.append(cache_dir)

for cache_dir in cache_dirs:
    try:
        import shutil
        shutil.rmtree(cache_dir)
        print(f"   ✓ 清理: {cache_dir}")
    except Exception as e:
        print(f"   ⚠ 无法清理 {cache_dir}: {e}")

if not cache_dirs:
    print("   ✓ 没有需要清理的缓存")

print("\n2. 验证关键模块...")

# 快速验证
try:
    from src.data_sources.akshare_source import _to_yuan, AMOUNT_UNIT_STOCK
    from src.utils.formatters import format_amount
    
    # 测试转换
    test_amount = _to_yuan(119819.25, AMOUNT_UNIT_STOCK)
    test_display = format_amount(test_amount)
    
    if test_display == "11.98亿":
        print(f"   ✓ 成交额单位修复已生效")
        print(f"     测试: 119819.25万元 → {test_display}")
    else:
        print(f"   ⚠ 格式化异常: {test_display}")
except Exception as e:
    print(f"   ❌ 模块加载失败: {e}")
    sys.exit(1)

print("\n3. 启动监控系统...")
print("-" * 80)
print()

# 启动 main.py（在新进程中）
try:
    subprocess.run([sys.executable, 'main.py'])
except KeyboardInterrupt:
    print("\n\n程序已退出")
except Exception as e:
    print(f"\n启动失败: {e}")
