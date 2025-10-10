"""
快速启动脚本 - V2.0
"""

import os
import sys

def show_menu():
    print("=" * 80)
    print("A股监控与回测系统 V2.0 - 快速启动")
    print("=" * 80)
    print("\n选择启动方式:\n")
    print("  1. 主程序（新版，推荐）")
    print("  2. 快速监控（旧版兼容）")
    print("  3. 测试数据连接")
    print("  4. 查看帮助文档")
    print("  0. 退出")
    print("\n" + "=" * 80)

def main():
    while True:
        show_menu()
        choice = input("\n请选择 (0-4): ").strip()
        
        if choice == '1':
            print("\n启动主程序...")
            os.system('python main.py')
        elif choice == '2':
            print("\n启动快速监控...")
            os.system('python quick_monitor.py')
        elif choice == '3':
            print("\n测试数据连接...")
            os.system('python test_connection.py')
            input("\n按回车继续...")
        elif choice == '4':
            print("\n文档列表:")
            print("  - README_V2.md      (项目说明)")
            print("  - 项目总览_V2.md    (架构文档)")
            print("  - 使用指南_V2.md    (详细教程)")
            input("\n请打开对应文件查看，按回车继续...")
        elif choice == '0':
            print("\n再见！")
            break
        else:
            print("\n无效选项")
            input("按回车继续...")

if __name__ == "__main__":
    main()
