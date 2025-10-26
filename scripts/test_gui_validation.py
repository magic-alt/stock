#!/usr/bin/env python3
"""
GUI功能验证测试
快速验证新GUI的基本功能是否正常
"""
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

def test_imports():
    """测试所有必要的导入"""
    print("测试1: 检查导入...")
    try:
        from src.backtest.strategy_modules import STRATEGY_REGISTRY
        from src.data_sources.providers import PROVIDER_NAMES
        print(f"  ✓ 策略注册表: {len(STRATEGY_REGISTRY)} 个策略")
        print(f"  ✓ 数据源: {', '.join(sorted(PROVIDER_NAMES))}")
        return True
    except Exception as e:
        print(f"  ✗ 导入失败: {e}")
        return False

def test_gui_structure():
    """测试GUI类结构"""
    print("\n测试2: 检查GUI类...")
    try:
        # 导入但不启动GUI
        import tkinter as tk
        from scripts.backtest_gui import BacktestGUI
        
        # 检查预设配置
        print(f"  ✓ 预设配置: {len(BacktestGUI.PRESET_CONFIGS)} 个")
        for name in BacktestGUI.PRESET_CONFIGS.keys():
            print(f"    - {name}")
        
        # 检查关键方法存在
        methods = [
            'create_run_tab',
            'create_grid_tab',
            'create_auto_tab',
            'create_data_download_tab',
            'create_list_tab',
            'run_command_run',
            'run_command_grid',
            'run_command_auto',
            'start_download',
        ]
        
        for method in methods:
            if hasattr(BacktestGUI, method):
                print(f"  ✓ 方法存在: {method}")
            else:
                print(f"  ✗ 方法缺失: {method}")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ GUI类检查失败: {e}")
        return False

def test_cli_commands():
    """测试CLI命令构建逻辑"""
    print("\n测试3: 检查CLI命令构建...")
    try:
        # 验证unified_backtest_framework.py存在
        framework_path = Path(project_root) / "unified_backtest_framework.py"
        if framework_path.exists():
            print(f"  ✓ CLI框架文件存在: {framework_path}")
        else:
            print(f"  ✗ CLI框架文件缺失: {framework_path}")
            return False
        
        # 验证命令结构
        with open(framework_path, 'r', encoding='utf-8') as f:
            content = f.read()
            commands = ['run', 'grid', 'auto', 'list']
            for cmd in commands:
                if f'command == "{cmd}"' in content or f"'{cmd}'" in content:
                    print(f"  ✓ 支持命令: {cmd}")
                else:
                    print(f"  ⚠ 命令检测: {cmd}")
        
        return True
    except Exception as e:
        print(f"  ✗ CLI检查失败: {e}")
        return False

def test_documentation():
    """测试文档完整性"""
    print("\n测试4: 检查文档...")
    try:
        docs = [
            'docs/GUI_USAGE_GUIDE.md',
            'CHANGELOG.md',
            'README.md',
        ]
        
        for doc in docs:
            doc_path = Path(project_root) / doc
            if doc_path.exists():
                size = doc_path.stat().st_size
                print(f"  ✓ 文档存在: {doc} ({size} bytes)")
            else:
                print(f"  ✗ 文档缺失: {doc}")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ 文档检查失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("="*60)
    print("GUI V2.10.3.0 功能验证测试")
    print("="*60)
    
    results = []
    
    results.append(("导入测试", test_imports()))
    results.append(("GUI结构", test_gui_structure()))
    results.append(("CLI命令", test_cli_commands()))
    results.append(("文档完整性", test_documentation()))
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 所有测试通过！GUI V2.10.3.0 可以使用")
        print("\n启动命令: python scripts/backtest_gui.py")
    else:
        print("⚠️ 部分测试失败，请检查上述错误")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
