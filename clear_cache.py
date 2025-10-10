"""清理缓存并重新测试"""
import os
import shutil
import sys

print("=" * 80)
print("清理 Python 缓存文件")
print("=" * 80)

# 清理所有 __pycache__ 目录
count = 0
for root, dirs, files in os.walk('.'):
    if '__pycache__' in dirs:
        pycache_path = os.path.join(root, '__pycache__')
        print(f"删除: {pycache_path}")
        try:
            shutil.rmtree(pycache_path)
            count += 1
        except Exception as e:
            print(f"  警告: 无法删除 {pycache_path}: {e}")

print(f"\n✅ 清理完成! 共删除 {count} 个缓存目录")
print("\n现在请重新运行: python main.py")
