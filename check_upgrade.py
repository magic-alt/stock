"""
升级检查脚本
"""

import os
import sys

def check_files():
    """检查必要文件是否存在"""
    print("=" * 80)
    print("升级检查清单")
    print("=" * 80)
    
    required_files = {
        '核心程序': [
            'main.py',
            'launcher.py',
            'test_connection.py',
        ],
        '配置文件': [
            'src/config.py',
            'requirements.txt',
        ],
        '数据源模块': [
            'src/data_sources/__init__.py',
            'src/data_sources/base.py',
            'src/data_sources/akshare_source.py',
            'src/data_sources/factory.py',
        ],
        '指标模块': [
            'src/indicators/__init__.py',
            'src/indicators/technical.py',
        ],
        '策略模块': [
            'src/strategies/__init__.py',
            'src/strategies/base.py',
            'src/strategies/ma_strategies.py',
            'src/strategies/rsi_strategies.py',
            'src/strategies/macd_strategies.py',
        ],
        '回测模块': [
            'src/backtest/__init__.py',
            'src/backtest/simple_engine.py',
            'src/backtest/backtrader_adapter.py',
        ],
        '监控模块': [
            'src/monitors/__init__.py',
            'src/monitors/realtime_monitor.py',
        ],
        '工具模块': [
            'src/utils/__init__.py',
            'src/utils/helpers.py',
        ],
        '文档': [
            'README_V2.md',
            '项目总览_V2.md',
            '使用指南_V2.md',
            '升级说明.md',
            '升级完成总结.md',
        ],
    }
    
    all_ok = True
    
    for category, files in required_files.items():
        print(f"\n【{category}】")
        for file in files:
            exists = os.path.exists(file)
            status = "✅" if exists else "❌"
            print(f"  {status} {file}")
            if not exists:
                all_ok = False
    
    print("\n" + "=" * 80)
    
    if all_ok:
        print("✅ 所有文件检查通过！")
    else:
        print("❌ 部分文件缺失，请检查！")
    
    return all_ok


def check_modules():
    """检查Python模块导入"""
    print("\n" + "=" * 80)
    print("模块导入检查")
    print("=" * 80)
    
    modules = [
        ('akshare', 'AKShare数据源'),
        ('pandas', 'Pandas数据处理'),
        ('numpy', 'NumPy数值计算'),
    ]
    
    all_ok = True
    
    for module, desc in modules:
        try:
            __import__(module)
            print(f"  ✅ {desc} ({module})")
        except ImportError:
            print(f"  ❌ {desc} ({module}) - 未安装")
            all_ok = False
    
    print("\n" + "=" * 80)
    
    if all_ok:
        print("✅ 所有依赖模块正常！")
    else:
        print("❌ 部分模块缺失，请运行: pip install -r requirements.txt")
    
    return all_ok


def check_config():
    """检查配置文件"""
    print("\n" + "=" * 80)
    print("配置检查")
    print("=" * 80)
    
    try:
        sys.path.insert(0, 'src')
        from config import (
            DEFAULT_WATCHLIST,
            get_stock_groups,
            PRESET_PLANS,
            INDICES,
        )
        
        print(f"  ✅ 默认监控股票数: {len(DEFAULT_WATCHLIST)}")
        print(f"  ✅ 股票分组数: {len(get_stock_groups())}")
        print(f"  ✅ 预设方案数: {len(PRESET_PLANS)}")
        print(f"  ✅ 监控指数数: {len(INDICES)}")
        
        # 检查新增的重点股票
        important_stocks = {
            '002241': '歌尔股份',
            '600580': '卧龙电驱',
            '600547': '山东黄金',
            '688981': '中芯国际',
            '300750': '宁德时代',
        }
        
        print("\n  重点股票:")
        all_stocks = {}
        for group in get_stock_groups().values():
            all_stocks.update(group)
        
        for code, name in important_stocks.items():
            if code in all_stocks:
                print(f"    ✅ {name}({code})")
            else:
                print(f"    ⚠️  {name}({code}) - 未找到")
        
        print("\n" + "=" * 80)
        print("✅ 配置文件正常！")
        return True
        
    except Exception as e:
        print(f"\n❌ 配置检查失败: {e}")
        print("=" * 80)
        return False


def show_summary():
    """显示总结"""
    print("\n" + "=" * 80)
    print("升级完成")
    print("=" * 80)
    print("""
🎉 恭喜！A股监控与回测系统 V2.0 升级完成！

📊 升级亮点:
  ✅ 模块化架构重构
  ✅ 新增30+只热门股票
  ✅ 8大主题分组
  ✅ 6种回测策略
  ✅ 增强技术指标
  ✅ 预留backtrader接口
  ✅ 完善文档体系

🚀 快速开始:
  1. python test_connection.py  (测试连接)
  2. python main.py             (运行主程序)
  3. python launcher.py         (快速启动)
  
📚 查看文档:
  - README_V2.md       (项目说明)
  - 使用指南_V2.md     (详细教程)
  - 项目总览_V2.md     (架构文档)
  - 升级完成总结.md    (升级总结)

⭐ 重点新增股票:
  - 002241 歌尔股份 (AI音频、VR/AR)
  - 600580 卧龙电驱 (电机驱动龙头)
  - 600547 山东黄金 (黄金板块)
  - 688981 中芯国际 (芯片制造)
  - 300750 宁德时代 (新能源电池)
  - 601899 紫金矿业 (矿业龙头)

💡 使用建议:
  新手: 先运行 python test_connection.py
        然后运行 python main.py
        选择"默认方案"体验
  
  进阶: 修改 src/config.py 自定义配置
        尝试不同的回测策略
  
  专家: 开发自定义策略
        集成backtrader
        扩展数据源

⚠️ 注意事项:
  - 数据有15分钟延迟
  - 回测结果仅供参考
  - 投资有风险，入市需谨慎
  - 本工具仅供学习研究

📞 获取帮助:
  - 查看文档目录
  - 运行 python show_structure.py 查看项目结构
  - 检查 src/config.py 配置

祝你使用愉快！投资顺利！📈🚀
    """)
    print("=" * 80)


def main():
    """主函数"""
    print("\n" + "🔍 开始检查..." + "\n")
    
    # 检查文件
    files_ok = check_files()
    
    # 检查模块
    modules_ok = check_modules()
    
    # 检查配置
    config_ok = check_config()
    
    # 显示总结
    if files_ok and modules_ok and config_ok:
        show_summary()
    else:
        print("\n" + "=" * 80)
        print("⚠️  部分检查未通过，请根据上述提示修复问题")
        print("=" * 80)


if __name__ == "__main__":
    main()
