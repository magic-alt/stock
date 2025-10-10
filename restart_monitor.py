"""
清理缓存并重启监控系统
确保使用V2.2.3最新代码
"""

import os
import sys
import shutil
import subprocess

print("=" * 80)
print("A股实时监控系统 - V2.2.3 重启脚本")
print("=" * 80)

print("\n📋 更新内容 (V2.2.3):")
print("-" * 80)
print("  ✅ 错误去重机制（60秒内只显示一次）")
print("  ✅ 日志系统分层（控制台清爽，文件详细）")
print("  ✅ 用户友好提示（技术细节隐藏）")

print("\n🔧 执行清理...")
print("-" * 80)

# 1. 清理 Python 字节码缓存
cache_count = 0
for root, dirs, files in os.walk('src'):
    if '__pycache__' in dirs:
        cache_dir = os.path.join(root, '__pycache__')
        try:
            shutil.rmtree(cache_dir)
            cache_count += 1
            print(f"  ✓ 清理: {cache_dir}")
        except Exception as e:
            print(f"  ⚠ 跳过: {cache_dir} ({e})")

if cache_count == 0:
    print("  ✓ 无需清理（缓存已清空）")

# 2. 验证关键模块
print("\n🧪 验证模块更新...")
print("-" * 80)

try:
    # 清除已导入的模块
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('src.')]
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    # 重新导入
    from src.data_sources.akshare_source import AKShareDataSource
    
    # 检查是否有新属性
    ds = AKShareDataSource()
    has_error_time = hasattr(ds, '_last_error_time')
    
    if has_error_time:
        print("  ✅ 错误去重机制已加载")
    else:
        print("  ⚠ 错误去重机制未找到（可能需要手动重启终端）")
    
    # 检查日志配置
    import logging
    root_logger = logging.getLogger()
    has_file_handler = any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    
    if has_file_handler:
        print("  ✅ 日志文件配置已加载")
    else:
        print("  ℹ️  日志配置将在 main.py 启动时加载")
    
    print("\n✅ 模块验证通过")
    
except Exception as e:
    print(f"\n❌ 模块验证失败: {e}")
    print("   建议: 手动重启终端后运行")
    input("\n按回车键退出...")
    sys.exit(1)

# 3. 提示用户
print("\n" + "=" * 80)
print("准备启动监控系统")
print("=" * 80)

print("\n⚠️  重要提示:")
print("  如果您看到重复的 '保留旧缓存' 错误，说明需要:")
print("  1. 按 Ctrl+C 退出当前程序")
print("  2. 关闭此终端窗口")
print("  3. 打开新终端窗口")
print("  4. 重新运行: python main.py")
print()

choice = input("继续启动监控系统? (y/n, 默认y): ").strip().lower()

if choice in ['', 'y', 'yes']:
    print("\n🚀 启动监控系统...")
    print("=" * 80)
    print()
    
    # 启动 main.py
    try:
        subprocess.run([sys.executable, 'main.py'])
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        print(f"\n启动失败: {e}")
else:
    print("\n已取消启动")
    print("\n建议:")
    print("  1. 关闭当前终端")
    print("  2. 打开新终端")
    print("  3. 运行: python main.py")
