# Scripts - 辅助脚本

本目录包含GUI界面和其他辅助工具脚本。

## 📁 文件列表

### 1. backtest_gui.py - 图形界面
**推荐新手使用** | 可视化操作

启动GUI界面：
```bash
python scripts/backtest_gui.py
```

或使用快捷脚本（仅Windows）：
```bash
.\启动GUI.bat
```

**功能特性**:
- ✅ 可视化参数配置
- ✅ 内置配置方案（白酒股、银行股等）
- ✅ 实时回测进度显示
- ✅ 策略性能对比
- ✅ 自动生成图表报告

### 2. gui_config_example.json - GUI配置示例
GUI界面的配置文件模板，包含：
- 预设策略组合
- 常用股票代码
- 默认参数设置

## 🚀 快速开始

### 方式1: GUI界面（推荐新手）
```bash
python scripts/backtest_gui.py
```

### 方式2: 命令行（推荐专业用户）
```bash
python unified_backtest_framework.py run --strategy macd --symbols 600519.SH
```

## 🎯 GUI使用指南

### 1. 基础回测
1. 选择数据源（推荐 AKShare）
2. 输入股票代码
3. 选择策略
4. 设置时间范围
5. 点击"开始回测"

### 2. 批量测试
1. 使用快速选择按钮（白酒股、银行股等）
2. 勾选多个策略
3. 开启"多进程加速"
4. 点击"开始回测"

### 3. 参数优化
1. 切换到"优化配置"标签页
2. 设置参数搜索范围
3. 选择优化目标
4. 运行网格搜索

## 📊 输出结果

回测完成后，结果保存在：
- **图表**: `report/` 目录
- **数据**: `output/` 目录
- **日志**: `logs/` 目录

## 🔧 自定义GUI

### 添加预设配置
编辑 `scripts/backtest_gui.py` 中的 `PRESET_CONFIGS`:
```python
PRESET_CONFIGS = {
    "我的配置": {
        "symbols": ["your_symbol"],
        "strategies": ["your_strategy"],
        "start_date": "2023-01-01",
        # ...
    }
}
```

### 修改界面样式
在 `scripts/backtest_gui.py` 的 `main()` 函数中：
```python
style = ttk.Style()
style.theme_use('your_theme')  # clam, alt, default, classic
```

## 🐛 故障排除

### GUI无法启动
```bash
# 安装GUI依赖
pip install tkinter matplotlib
```

### 中文显示乱码
```python
# 在GUI代码中已配置：
matplotlib.rcParams['font.sans-serif'] = ['SimHei']
```

### 数据下载失败
1. 检查网络连接
2. 切换数据源（AKShare → YFinance）
3. 查看 `logs/` 日志文件

## 📚 相关文档

- **CLI使用**: `unified_backtest_framework.py --help`
- **示例代码**: `examples/`
- **完整文档**: `docs/`

---

**提示**: GUI基于tkinter开发，跨平台兼容 (Windows/Linux/Mac)
