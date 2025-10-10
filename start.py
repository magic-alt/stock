"""
A股工具集启动器
"""

import os
import sys

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_menu():
    clear_screen()
    print("=" * 80)
    print(f"{'A股监控与回测工具集':^70}")
    print("=" * 80)
    print("\n请选择功能:\n")
    print("  1. 快速监控 - 立即开始实时监控（推荐新手）")
    print("  2. 完整监控 - 包含技术指标的详细监控")
    print("  3. 快速回测 - 测试交易策略效果")
    print("  4. 测试连接 - 检查数据源连接状态")
    print("  0. 退出程序")
    print("\n" + "=" * 80)

def main():
    while True:
        print_menu()
        choice = input("\n请输入选项 (0-4): ").strip()
        
        if choice == '1':
            print("\n启动快速监控...")
            os.system('python quick_monitor.py')
            
        elif choice == '2':
            print("\n启动完整监控...")
            os.system('python stock_monitor.py')
            
        elif choice == '3':
            print("\n启动快速回测...")
            os.system('python quick_backtest.py')
            
        elif choice == '4':
            print("\n测试数据连接...")
            os.system('python test_connection.py')
            input("\n按回车键继续...")
            
        elif choice == '0':
            print("\n感谢使用，再见！")
            sys.exit(0)
            
        else:
            print("\n无效选项，请重新选择。")
            input("按回车键继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已退出。")
