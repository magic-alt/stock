#!/usr/bin/env python3
"""
Backtest Analysis GUI
完整的回测分析图形界面，包含所有 CLI 功能

版本: V2.8.2
日期: 2025-10-25
更新: 添加单只股票选择、下载数据功能、确认图表保存
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 设置 matplotlib 使用非 GUI 后端（必须在导入 matplotlib 之前）
import matplotlib
matplotlib.use('Agg')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backtest.engine import BacktestEngine
from src.backtest.strategy_modules import STRATEGY_REGISTRY
from src.data_sources.providers import PROVIDER_NAMES


class BacktestGUI:
    """回测分析主界面"""
    
    # 内置配置方案
    PRESET_CONFIGS = {
        "白酒股-趋势策略": {
            "symbols": ["600519.SH", "000858.SZ", "000568.SZ", "600809.SH"],
            "strategies": ["ema", "macd", "adx_trend", "triple_ma"],
            "start_date": "2022-01-01",
            "mode": "auto",
            "hot_only": True,
            "use_benchmark_regime": True,
            "regime_scope": "trend",
            "description": "白酒行业股票 + 趋势跟踪策略组合"
        },
        "银行股-震荡策略": {
            "symbols": ["600036.SH", "601318.SH", "600000.SH", "601288.SH"],
            "strategies": ["bollinger", "rsi", "keltner", "zscore"],
            "start_date": "2022-01-01",
            "mode": "auto",
            "hot_only": True,
            "description": "银行股票 + 震荡交易策略组合"
        },
        "科技股-全策略": {
            "symbols": ["000333.SZ", "002230.SZ", "600276.SH", "002475.SZ"],
            "strategies": ["ema", "macd", "bollinger", "rsi", "adx_trend"],
            "start_date": "2022-01-01",
            "mode": "auto",
            "hot_only": True,
            "description": "科技股票 + 多种策略综合分析"
        },
        "单股深度分析": {
            "symbols": ["600519.SH"],
            "strategies": ["ema", "macd", "bollinger", "rsi", "triple_ma", "donchian", "keltner", "zscore"],
            "start_date": "2020-01-01",
            "mode": "auto",
            "hot_only": False,
            "top_n": 10,
            "description": "单一股票的全面策略测试"
        },
        "快速测试-3月": {
            "symbols": ["600519.SH", "000333.SZ"],
            "strategies": ["ema", "macd"],
            "start_date": "2024-07-01",
            "end_date": "2024-10-01",
            "mode": "auto",
            "hot_only": True,
            "top_n": 3,
            "workers": 2,
            "description": "快速测试配置（3个月数据）"
        }
    }
    
    def __init__(self, root):
        self.root = root
        self.root.title("量化回测分析系统 V2.8.1")
        self.root.geometry("1200x800")
        
        # 状态变量
        self.running = False
        self.engine = None
        
        # 创建主界面
        self.create_widgets()
        
        # 加载默认配置
        self.load_default_config()
    
    def create_widgets(self):
        """创建所有界面组件"""
        # 创建主容器
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧面板（配置区）
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=1)
        
        # 右侧面板（输出区）
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=1)
        
        # 左侧：创建标签页
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 标签页1: 数据配置
        self.create_data_tab()
        
        # 标签页2: 策略配置
        self.create_strategy_tab()
        
        # 标签页3: 回测配置
        self.create_backtest_tab()
        
        # 标签页4: 优化配置
        self.create_optimization_tab()
        
        # 右侧：输出区域
        self.create_output_area(right_frame)
        
        # 底部：控制按钮
        self.create_control_buttons(left_frame)
    
    def create_data_tab(self):
        """数据配置标签页"""
        data_frame = ttk.Frame(self.notebook)
        self.notebook.add(data_frame, text="📊 数据配置")
        
        # 数据源选择
        ttk.Label(data_frame, text="数据源:", font=("", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.provider_var = tk.StringVar(value="akshare")
        provider_combo = ttk.Combobox(
            data_frame, 
            textvariable=self.provider_var,
            values=sorted(PROVIDER_NAMES),
            state="readonly",
            width=25
        )
        provider_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 股票代码输入
        ttk.Label(data_frame, text="股票代码:", font=("", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        symbol_frame = ttk.Frame(data_frame)
        symbol_frame.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
        self.symbols_text = scrolledtext.ScrolledText(
            symbol_frame, 
            height=6, 
            width=40,
            wrap=tk.WORD
        )
        self.symbols_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.symbols_text.insert("1.0", "600519.SH\n000333.SZ\n600036.SH")
        
        # 添加提示标签
        ttk.Label(
            data_frame, 
            text="提示: 每行一个股票代码",
            foreground="gray"
        ).grid(row=2, column=1, sticky=tk.W, padx=10, pady=(0, 5))
        
        # 快速选择按钮
        quick_select_frame = ttk.LabelFrame(data_frame, text="快速选择")
        quick_select_frame.grid(row=3, column=0, columnspan=3, sticky=tk.EW, padx=10, pady=5)
        
        # 第一行：单只股票
        row1 = ttk.Frame(quick_select_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(row1, text="单股:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            row1,
            text="茅台",
            command=lambda: self.load_stock_list("maotai"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            row1,
            text="平安",
            command=lambda: self.load_stock_list("pingan"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            row1,
            text="招行",
            command=lambda: self.load_stock_list("zhaohang"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            row1,
            text="五粮液",
            command=lambda: self.load_stock_list("wuliangye"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        # 第二行：行业组合
        row2 = ttk.Frame(quick_select_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(row2, text="组合:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            row2,
            text="白酒股",
            command=lambda: self.load_stock_list("liquor"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            row2,
            text="银行股",
            command=lambda: self.load_stock_list("bank"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            row2,
            text="科技股",
            command=lambda: self.load_stock_list("tech"),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            row2,
            text="清空",
            command=lambda: self.symbols_text.delete("1.0", tk.END),
            width=8
        ).pack(side=tk.LEFT, padx=2)
        
        # 日期范围
        ttk.Label(data_frame, text="开始日期:", font=("", 10, "bold")).grid(
            row=4, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.start_date_var = tk.StringVar(
            value=(datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        )
        ttk.Entry(data_frame, textvariable=self.start_date_var, width=28).grid(
            row=4, column=1, sticky=tk.W, padx=10, pady=5
        )
        
        ttk.Label(data_frame, text="结束日期:", font=("", 10, "bold")).grid(
            row=5, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(data_frame, textvariable=self.end_date_var, width=28).grid(
            row=5, column=1, sticky=tk.W, padx=10, pady=5
        )
        
        # 基准指数
        ttk.Label(data_frame, text="基准指数:", font=("", 10, "bold")).grid(
            row=6, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.benchmark_var = tk.StringVar(value="000300.SH")
        benchmark_entry = ttk.Entry(data_frame, textvariable=self.benchmark_var, width=28)
        benchmark_entry.grid(row=6, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(
            data_frame, 
            text="(留空则不使用基准)",
            foreground="gray"
        ).grid(row=7, column=1, sticky=tk.W, padx=10, pady=(0, 5))
        
        # 数据操作按钮框架
        data_actions_frame = ttk.Frame(data_frame)
        data_actions_frame.grid(row=8, column=0, columnspan=2, pady=10)
        
        ttk.Button(
            data_actions_frame,
            text="� 下载数据",
            command=self.download_data
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            data_actions_frame,
            text="📋 预览数据",
            command=self.preview_data
        ).pack(side=tk.LEFT, padx=5)
        
        # 缓存目录
        ttk.Label(data_frame, text="缓存目录:", font=("", 10, "bold")).grid(
            row=9, column=0, sticky=tk.W, padx=10, pady=5
        )
        cache_frame = ttk.Frame(data_frame)
        cache_frame.grid(row=9, column=1, columnspan=2, sticky=tk.EW, padx=10, pady=5)
        
        self.cache_dir_var = tk.StringVar(value="./cache")
        ttk.Entry(cache_frame, textvariable=self.cache_dir_var, width=20).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            cache_frame,
            text="浏览...",
            command=self.browse_cache_dir
        ).pack(side=tk.LEFT, padx=(5, 0))
    
    def create_strategy_tab(self):
        """策略配置标签页"""
        strategy_frame = ttk.Frame(self.notebook)
        self.notebook.add(strategy_frame, text="🎯 策略配置")
        
        # 策略选择列表
        ttk.Label(
            strategy_frame, 
            text="选择策略:", 
            font=("", 10, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 创建策略列表框和滚动条
        list_frame = ttk.Frame(strategy_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.strategy_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            yscrollcommand=scrollbar.set,
            height=12
        )
        self.strategy_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.strategy_listbox.yview)
        
        # 填充策略列表
        for name, module in sorted(STRATEGY_REGISTRY.items()):
            display_text = f"{name} - {module.description}"
            self.strategy_listbox.insert(tk.END, display_text)
        
        # 默认选中第一个
        self.strategy_listbox.selection_set(0)
        
        # 快速选择按钮
        quick_frame = ttk.Frame(strategy_frame)
        quick_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(
            quick_frame,
            text="全选",
            command=lambda: self.strategy_listbox.selection_set(0, tk.END)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            quick_frame,
            text="清空",
            command=lambda: self.strategy_listbox.selection_clear(0, tk.END)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            quick_frame,
            text="趋势策略",
            command=lambda: self.select_strategy_type("trend")
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            quick_frame,
            text="震荡策略",
            command=lambda: self.select_strategy_type("range")
        ).pack(side=tk.LEFT, padx=5)
        
        # 策略参数配置
        param_frame = ttk.LabelFrame(strategy_frame, text="策略参数")
        param_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        ttk.Label(
            param_frame,
            text="JSON格式参数 (留空使用默认):",
            foreground="gray"
        ).pack(anchor=tk.W, padx=5, pady=5)
        
        self.strategy_params_text = scrolledtext.ScrolledText(
            param_frame,
            height=6,
            width=50,
            wrap=tk.WORD
        )
        self.strategy_params_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 留空，让用户根据需要填写或使用策略默认参数
        
        # 策略信息显示
        info_button = ttk.Button(
            strategy_frame,
            text="📖 查看策略详情",
            command=self.show_strategy_info
        )
        info_button.pack(pady=10)
    
    def create_backtest_tab(self):
        """回测配置标签页"""
        backtest_frame = ttk.Frame(self.notebook)
        self.notebook.add(backtest_frame, text="⚙️ 回测配置")
        
        # 初始资金
        ttk.Label(backtest_frame, text="初始资金:", font=("", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.cash_var = tk.StringVar(value="200000")
        ttk.Entry(backtest_frame, textvariable=self.cash_var, width=28).grid(
            row=0, column=1, sticky=tk.W, padx=10, pady=5
        )
        
        # 手续费率
        ttk.Label(backtest_frame, text="手续费率:", font=("", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.commission_var = tk.StringVar(value="0.0001")
        ttk.Entry(backtest_frame, textvariable=self.commission_var, width=28).grid(
            row=1, column=1, sticky=tk.W, padx=10, pady=5
        )
        ttk.Label(
            backtest_frame,
            text="(0.0001 = 0.01%)",
            foreground="gray"
        ).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # 滑点
        ttk.Label(backtest_frame, text="滑点:", font=("", 10, "bold")).grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.slippage_var = tk.StringVar(value="0.001")
        ttk.Entry(backtest_frame, textvariable=self.slippage_var, width=28).grid(
            row=2, column=1, sticky=tk.W, padx=10, pady=5
        )
        
        # 复权方式
        ttk.Label(backtest_frame, text="复权方式:", font=("", 10, "bold")).grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.adj_var = tk.StringVar(value="")
        adj_combo = ttk.Combobox(
            backtest_frame,
            textvariable=self.adj_var,
            values=["", "qfq", "hfq"],
            state="readonly",
            width=25
        )
        adj_combo.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(
            backtest_frame,
            text="空=不复权 qfq=前复权 hfq=后复权",
            foreground="gray"
        ).grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=10, pady=(0, 5))
        
        # 输出目录
        ttk.Label(backtest_frame, text="输出目录:", font=("", 10, "bold")).grid(
            row=5, column=0, sticky=tk.W, padx=10, pady=5
        )
        output_frame = ttk.Frame(backtest_frame)
        output_frame.grid(row=5, column=1, columnspan=2, sticky=tk.EW, padx=10, pady=5)
        
        self.output_dir_var = tk.StringVar(value="./reports_gui")
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=20).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            output_frame,
            text="浏览...",
            command=self.browse_output_dir
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # 绘图选项
        self.plot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            backtest_frame,
            text="生成图表",
            variable=self.plot_var
        ).grid(row=6, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 进度追踪选项
        self.verbose_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            backtest_frame,
            text="显示详细日志",
            variable=self.verbose_var
        ).grid(row=7, column=1, sticky=tk.W, padx=10, pady=5)
    
    def create_optimization_tab(self):
        """优化配置标签页"""
        opt_frame = ttk.Frame(self.notebook)
        self.notebook.add(opt_frame, text="🔍 优化配置")
        
        # 运行模式选择
        ttk.Label(opt_frame, text="运行模式:", font=("", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.mode_var = tk.StringVar(value="single")
        modes = [
            ("单次回测", "single"),
            ("网格搜索", "grid"),
            ("自动化流程", "auto")
        ]
        for i, (text, value) in enumerate(modes):
            ttk.Radiobutton(
                opt_frame,
                text=text,
                variable=self.mode_var,
                value=value
            ).grid(row=0, column=i+1, sticky=tk.W, padx=5, pady=5)
        
        # 并行进程数
        ttk.Label(opt_frame, text="并行进程数:", font=("", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.workers_var = tk.StringVar(value="4")
        ttk.Spinbox(
            opt_frame,
            from_=1,
            to=16,
            textvariable=self.workers_var,
            width=26
        ).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Top N 配置
        ttk.Label(opt_frame, text="Top N:", font=("", 10, "bold")).grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.top_n_var = tk.StringVar(value="5")
        ttk.Spinbox(
            opt_frame,
            from_=1,
            to=20,
            textvariable=self.top_n_var,
            width=26
        ).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 最小交易次数
        ttk.Label(opt_frame, text="最小交易次数:", font=("", 10, "bold")).grid(
            row=3, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.min_trades_var = tk.StringVar(value="1")
        ttk.Spinbox(
            opt_frame,
            from_=0,
            to=100,
            textvariable=self.min_trades_var,
            width=26
        ).grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Hot-only 模式
        self.hot_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_frame,
            text="使用 Hot-Only 模式 (缩小参数范围)",
            variable=self.hot_only_var
        ).grid(row=4, column=0, columnspan=3, sticky=tk.W, padx=10, pady=5)
        
        # 基准趋势过滤
        self.use_benchmark_regime_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_frame,
            text="使用基准趋势过滤",
            variable=self.use_benchmark_regime_var
        ).grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=10, pady=5)
        
        # Regime scope
        ttk.Label(opt_frame, text="趋势过滤范围:", font=("", 10, "bold")).grid(
            row=6, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.regime_scope_var = tk.StringVar(value="trend")
        regime_combo = ttk.Combobox(
            opt_frame,
            textvariable=self.regime_scope_var,
            values=["trend", "all", "none"],
            state="readonly",
            width=25
        )
        regime_combo.grid(row=6, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 网格参数配置
        grid_frame = ttk.LabelFrame(opt_frame, text="网格搜索参数 (仅grid模式)")
        grid_frame.grid(row=7, column=0, columnspan=4, sticky=tk.EW, padx=10, pady=10)
        
        ttk.Label(
            grid_frame,
            text="JSON格式 (留空使用策略默认网格):",
            foreground="gray"
        ).pack(anchor=tk.W, padx=5, pady=5)
        
        self.grid_params_text = scrolledtext.ScrolledText(
            grid_frame,
            height=6,
            width=50,
            wrap=tk.WORD
        )
        self.grid_params_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 留空，使用策略默认网格
    
    def create_output_area(self, parent):
        """创建输出区域"""
        output_frame = ttk.LabelFrame(parent, text="📋 输出日志")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 输出文本框
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=("Courier New", 9),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 配置颜色标签
        self.output_text.tag_config("info", foreground="#4ec9b0")
        self.output_text.tag_config("success", foreground="#4ec9b0")
        self.output_text.tag_config("warning", foreground="#dcdcaa")
        self.output_text.tag_config("error", foreground="#f48771")
        self.output_text.tag_config("header", foreground="#569cd6", font=("Courier New", 10, "bold"))
        
        # 清空按钮
        ttk.Button(
            output_frame,
            text="清空日志",
            command=lambda: self.output_text.delete("1.0", tk.END)
        ).pack(pady=5)
    
    def create_control_buttons(self, parent):
        """创建控制按钮"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 第一行：主要控制按钮
        main_button_frame = ttk.Frame(button_frame)
        main_button_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 开始回测按钮
        self.run_button = ttk.Button(
            main_button_frame,
            text="▶️ 开始回测",
            command=self.run_backtest,
            style="Accent.TButton"
        )
        self.run_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 停止按钮
        self.stop_button = ttk.Button(
            main_button_frame,
            text="⏹️ 停止",
            command=self.stop_backtest,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 第二行：配置管理按钮
        config_button_frame = ttk.Frame(button_frame)
        config_button_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 保存配置按钮
        ttk.Button(
            config_button_frame,
            text="💾 保存配置",
            command=self.save_config
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 加载配置按钮
        ttk.Button(
            config_button_frame,
            text="📂 加载配置",
            command=self.load_config
        ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 第三行：快速配置方案按钮
        preset_button_frame = ttk.Frame(button_frame)
        preset_button_frame.pack(fill=tk.X)
        
        ttk.Label(
            preset_button_frame,
            text="📋 快速配置:",
            font=("", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)
        
        # 快速配置下拉菜单
        self.preset_var = tk.StringVar()
        preset_names = ["选择方案..."] + list(self.PRESET_CONFIGS.keys())
        self.preset_combo = ttk.Combobox(
            preset_button_frame,
            textvariable=self.preset_var,
            values=preset_names,
            state="readonly",
            width=20
        )
        self.preset_combo.set("选择方案...")
        self.preset_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.preset_combo.bind("<<ComboboxSelected>>", self.load_preset_config)
        
        # 查看方案详情按钮
        ttk.Button(
            preset_button_frame,
            text="ℹ️ 详情",
            command=self.show_preset_details,
            width=8
        ).pack(side=tk.LEFT, padx=5)
    
    def load_default_config(self):
        """加载默认配置"""
        self.log("欢迎使用量化回测分析系统 V2.7.1", "header")
        self.log("=" * 60, "info")
        self.log("提示: 请在左侧配置回测参数，然后点击 '开始回测' 按钮", "info")
        self.log("=" * 60, "info")
    
    def log(self, message, tag="info"):
        """输出日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.output_text.see(tk.END)
        self.root.update()
    
    def get_symbols(self):
        """获取股票代码列表"""
        text = self.symbols_text.get("1.0", tk.END).strip()
        symbols = [line.strip() for line in text.split("\n") if line.strip()]
        return symbols
    
    def get_selected_strategies(self):
        """获取选中的策略列表"""
        selected_indices = self.strategy_listbox.curselection()
        strategy_names = []
        for idx in selected_indices:
            text = self.strategy_listbox.get(idx)
            name = text.split(" - ")[0]
            strategy_names.append(name)
        return strategy_names
    
    def load_stock_list(self, category):
        """加载预设股票列表"""
        stock_lists = {
            # 单只股票
            "maotai": ["600519.SH"],
            "pingan": ["601318.SH"],
            "zhaohang": ["600036.SH"],
            "wuliangye": ["000858.SZ"],
            # 行业组合
            "liquor": ["600519.SH", "000858.SZ", "000568.SZ", "600809.SH", "000799.SZ"],
            "bank": ["600036.SH", "601318.SH", "600000.SH", "600016.SH", "601288.SH"],
            "tech": ["000333.SZ", "002230.SZ", "600276.SH", "000063.SZ", "002475.SZ"]
        }
        
        if category in stock_lists:
            self.symbols_text.delete("1.0", tk.END)
            self.symbols_text.insert("1.0", "\n".join(stock_lists[category]))
            stock_count = len(stock_lists[category])
            self.log(f"✓ 已加载 {stock_count} 只股票", "success")
    
    def select_strategy_type(self, strategy_type):
        """选择特定类型的策略"""
        self.strategy_listbox.selection_clear(0, tk.END)
        
        trend_strategies = ["ema", "macd", "adx_trend", "triple_ma", "donchian"]
        range_strategies = ["bollinger", "rsi", "keltner", "zscore"]
        
        target_list = trend_strategies if strategy_type == "trend" else range_strategies
        
        for i in range(self.strategy_listbox.size()):
            text = self.strategy_listbox.get(i)
            name = text.split(" - ")[0]
            if name in target_list:
                self.strategy_listbox.selection_set(i)
        
        self.log(f"已选择 {strategy_type} 策略", "success")
    
    def browse_cache_dir(self):
        """浏览缓存目录"""
        directory = filedialog.askdirectory(initialdir=self.cache_dir_var.get())
        if directory:
            self.cache_dir_var.set(directory)
    
    def browse_output_dir(self):
        """浏览输出目录"""
        directory = filedialog.askdirectory(initialdir=self.output_dir_var.get())
        if directory:
            self.output_dir_var.set(directory)
    
    def download_data(self):
        """下载数据到缓存"""
        self.log("=" * 60, "info")
        self.log("开始下载数据...", "header")
        
        symbols = self.get_symbols()
        if not symbols:
            messagebox.showwarning("警告", "请至少输入一个股票代码")
            return
        
        try:
            self.log(f"📥 数据源: {self.provider_var.get()}", "info")
            self.log(f"📊 股票代码: {', '.join(symbols)}", "info")
            self.log(f"📅 日期范围: {self.start_date_var.get()} ~ {self.end_date_var.get()}", "info")
            self.log(f"💾 缓存目录: {self.cache_dir_var.get()}", "info")
            self.log("", "info")
            
            engine = BacktestEngine(
                source=self.provider_var.get(),
                cache_dir=self.cache_dir_var.get()
            )
            
            # 下载股票数据
            success_count = 0
            fail_count = 0
            
            for i, symbol in enumerate(symbols, 1):
                try:
                    self.log(f"[{i}/{len(symbols)}] 下载 {symbol}...", "info")
                    data_map = engine._load_data(
                        [symbol],
                        self.start_date_var.get(),
                        self.end_date_var.get()
                    )
                    
                    if symbol in data_map and data_map[symbol] is not None and not data_map[symbol].empty:
                        records = len(data_map[symbol])
                        start_date = data_map[symbol].index[0].strftime('%Y-%m-%d')
                        end_date = data_map[symbol].index[-1].strftime('%Y-%m-%d')
                        self.log(f"  ✓ 成功: {records} 条记录 ({start_date} ~ {end_date})", "success")
                        success_count += 1
                    else:
                        self.log(f"  ✗ 失败: 数据为空", "warning")
                        fail_count += 1
                except Exception as e:
                    self.log(f"  ✗ 失败: {str(e)}", "error")
                    fail_count += 1
            
            # 下载基准指数
            benchmark = self.benchmark_var.get()
            if benchmark:
                self.log(f"\n下载基准指数: {benchmark}...", "info")
                try:
                    bench_data = engine._load_data(
                        [benchmark],
                        self.start_date_var.get(),
                        self.end_date_var.get()
                    )
                    if benchmark in bench_data and not bench_data[benchmark].empty:
                        records = len(bench_data[benchmark])
                        self.log(f"  ✓ 基准指数下载成功: {records} 条记录", "success")
                    else:
                        self.log(f"  ⚠ 基准指数数据为空", "warning")
                except Exception as e:
                    self.log(f"  ✗ 基准指数下载失败: {str(e)}", "error")
            
            self.log("", "info")
            self.log("=" * 60, "success")
            self.log(f"✓ 下载完成! 成功: {success_count}, 失败: {fail_count}", "success")
            
            if success_count > 0:
                messagebox.showinfo(
                    "下载完成", 
                    f"数据下载完成！\n\n成功: {success_count} 只\n失败: {fail_count} 只\n\n数据已缓存到: {self.cache_dir_var.get()}"
                )
            else:
                messagebox.showerror("下载失败", "所有股票数据下载失败，请检查股票代码和网络连接")
            
        except Exception as e:
            import traceback
            self.log(f"✗ 下载失败: {str(e)}", "error")
            self.log(f"详细错误:\n{traceback.format_exc()}", "error")
            messagebox.showerror("错误", f"数据下载失败:\n{str(e)}")
    
    def preview_data(self):
        """预览数据"""
        self.log("=" * 60, "info")
        self.log("开始预览数据...", "header")
        
        symbols = self.get_symbols()
        if not symbols:
            messagebox.showwarning("警告", "请至少输入一个股票代码")
            return
        
        try:
            self.log(f"数据源: {self.provider_var.get()}", "info")
            self.log(f"股票代码: {', '.join(symbols)}", "info")
            self.log(f"日期范围: {self.start_date_var.get()} ~ {self.end_date_var.get()}", "info")
            
            engine = BacktestEngine(
                source=self.provider_var.get(),
                cache_dir=self.cache_dir_var.get()
            )
            
            data_map = engine._load_data(
                symbols,
                self.start_date_var.get(),
                self.end_date_var.get()
            )
            
            if not data_map:
                self.log("✗ 未加载到任何数据", "error")
                messagebox.showerror("错误", "未加载到任何数据，请检查股票代码和日期范围")
                return
            
            self.log(f"✓ 成功加载 {len(data_map)} 只股票的数据:", "success")
            for symbol, df in data_map.items():
                if df is not None and not df.empty:
                    self.log(f"  - {symbol}: {len(df)} 条记录 (从 {df.index[0].strftime('%Y-%m-%d')} 到 {df.index[-1].strftime('%Y-%m-%d')})", "info")
                else:
                    self.log(f"  - {symbol}: 数据为空", "warning")
            
            # 预览基准指数
            benchmark = self.benchmark_var.get()
            if benchmark:
                self.log(f"\n检查基准指数: {benchmark}", "info")
                try:
                    # Try to load benchmark
                    bench_engine = BacktestEngine(
                        source=self.provider_var.get(),
                        cache_dir=self.cache_dir_var.get()
                    )
                    bench_data = bench_engine._load_data(
                        [benchmark],
                        self.start_date_var.get(),
                        self.end_date_var.get()
                    )
                    if benchmark in bench_data and not bench_data[benchmark].empty:
                        self.log(f"✓ 基准指数加载成功: {len(bench_data[benchmark])} 条记录", "success")
                    else:
                        self.log(f"⚠ 基准指数数据为空", "warning")
                except Exception as e:
                    self.log(f"⚠ 基准指数加载失败: {str(e)}", "warning")
            
            self.log("=" * 60, "success")
            messagebox.showinfo("成功", f"数据预览完成！\n成功加载 {len(data_map)} 只股票的数据")
            
        except Exception as e:
            import traceback
            self.log(f"✗ 数据预览失败: {str(e)}", "error")
            self.log(f"详细错误:\n{traceback.format_exc()}", "error")
            messagebox.showerror("错误", f"数据预览失败:\n{str(e)}")
    
    def show_strategy_info(self):
        """显示策略详情"""
        strategies = self.get_selected_strategies()
        if not strategies:
            messagebox.showinfo("提示", "请先选择至少一个策略")
            return
        
        info_window = tk.Toplevel(self.root)
        info_window.title("策略详情")
        info_window.geometry("600x400")
        
        text = scrolledtext.ScrolledText(info_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for name in strategies:
            if name in STRATEGY_REGISTRY:
                module = STRATEGY_REGISTRY[name]
                text.insert(tk.END, f"策略: {name}\n", "bold")
                text.insert(tk.END, f"描述: {module.description}\n")
                text.insert(tk.END, f"默认参数: {module.defaults}\n")
                text.insert(tk.END, f"参数网格: {module.grid_defaults}\n")
                text.insert(tk.END, "\n" + "=" * 60 + "\n\n")
        
        text.config(state=tk.DISABLED)
    
    def save_config(self):
        """保存配置到文件"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        config = {
            "provider": self.provider_var.get(),
            "symbols": self.get_symbols(),
            "start_date": self.start_date_var.get(),
            "end_date": self.end_date_var.get(),
            "benchmark": self.benchmark_var.get(),
            "strategies": self.get_selected_strategies(),
            "cash": self.cash_var.get(),
            "commission": self.commission_var.get(),
            "slippage": self.slippage_var.get(),
            "adj": self.adj_var.get(),
            "output_dir": self.output_dir_var.get(),
            "cache_dir": self.cache_dir_var.get(),
            "mode": self.mode_var.get(),
            "workers": self.workers_var.get(),
            "top_n": self.top_n_var.get(),
            "min_trades": self.min_trades_var.get(),
            "hot_only": self.hot_only_var.get(),
            "use_benchmark_regime": self.use_benchmark_regime_var.get(),
            "regime_scope": self.regime_scope_var.get(),
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.log(f"✓ 配置已保存到: {filename}", "success")
            messagebox.showinfo("成功", "配置保存成功")
        except Exception as e:
            self.log(f"✗ 配置保存失败: {str(e)}", "error")
            messagebox.showerror("错误", f"配置保存失败:\n{str(e)}")
    
    def load_config(self):
        """从文件加载配置"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 恢复配置
            self.provider_var.set(config.get("provider", "akshare"))
            self.symbols_text.delete("1.0", tk.END)
            self.symbols_text.insert("1.0", "\n".join(config.get("symbols", [])))
            self.start_date_var.set(config.get("start_date", ""))
            self.end_date_var.set(config.get("end_date", ""))
            self.benchmark_var.set(config.get("benchmark", ""))
            self.cash_var.set(config.get("cash", "200000"))
            self.commission_var.set(config.get("commission", "0.0001"))
            self.slippage_var.set(config.get("slippage", "0.001"))
            self.adj_var.set(config.get("adj", ""))
            self.output_dir_var.set(config.get("output_dir", "./reports_gui"))
            self.cache_dir_var.set(config.get("cache_dir", "./cache"))
            self.mode_var.set(config.get("mode", "single"))
            self.workers_var.set(config.get("workers", "4"))
            self.top_n_var.set(config.get("top_n", "5"))
            self.min_trades_var.set(config.get("min_trades", "1"))
            self.hot_only_var.set(config.get("hot_only", False))
            self.use_benchmark_regime_var.set(config.get("use_benchmark_regime", False))
            self.regime_scope_var.set(config.get("regime_scope", "trend"))
            
            self.log(f"✓ 配置已从 {filename} 加载", "success")
            messagebox.showinfo("成功", "配置加载成功")
        except Exception as e:
            self.log(f"✗ 配置加载失败: {str(e)}", "error")
            messagebox.showerror("错误", f"配置加载失败:\n{str(e)}")
    
    def run_backtest(self):
        """运行回测（在新线程中）"""
        if self.running:
            messagebox.showwarning("警告", "回测正在运行中...")
            return
        
        # 验证输入
        symbols = self.get_symbols()
        strategies = self.get_selected_strategies()
        
        if not symbols:
            messagebox.showwarning("警告", "请至少输入一个股票代码")
            return
        
        if not strategies:
            messagebox.showwarning("警告", "请至少选择一个策略")
            return
        
        # 更新UI状态
        self.running = True
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 在新线程中运行
        thread = threading.Thread(target=self._run_backtest_thread, daemon=True)
        thread.start()
    
    def _run_backtest_thread(self):
        """回测线程"""
        try:
            self.log("=" * 60, "header")
            self.log("开始回测分析...", "header")
            self.log("=" * 60, "header")
            
            # 创建引擎
            engine = BacktestEngine(
                source=self.provider_var.get(),
                benchmark_source=self.provider_var.get(),
                cache_dir=self.cache_dir_var.get()
            )
            
            symbols = self.get_symbols()
            strategies = self.get_selected_strategies()
            mode = self.mode_var.get()
            
            self.log(f"运行模式: {mode}", "info")
            self.log(f"股票数量: {len(symbols)}", "info")
            self.log(f"策略数量: {len(strategies)}", "info")
            
            if mode == "single":
                self._run_single_backtest(engine, symbols, strategies)
            elif mode == "grid":
                self._run_grid_search(engine, symbols, strategies)
            elif mode == "auto":
                self._run_auto_pipeline(engine, symbols, strategies)
            
            self.log("=" * 60, "success")
            self.log("✓ 回测完成!", "success")
            self.log("=" * 60, "success")
            
            messagebox.showinfo("成功", "回测完成！请查看输出目录中的结果。")
            
        except Exception as e:
            self.log(f"✗ 回测失败: {str(e)}", "error")
            messagebox.showerror("错误", f"回测失败:\n{str(e)}")
        finally:
            self.running = False
            self.root.after(0, self._reset_buttons)
    
    def _run_single_backtest(self, engine, symbols, strategies):
        """单次回测"""
        # 解析策略参数
        params_text = self.strategy_params_text.get("1.0", tk.END).strip()
        try:
            params = json.loads(params_text) if params_text else None
        except json.JSONDecodeError as e:
            self.log(f"⚠ 策略参数 JSON 格式错误，使用默认参数: {str(e)}", "warning")
            params = None
        
        for strategy in strategies:
            self.log(f"\n{'='*60}", "header")
            self.log(f"运行策略: {strategy}", "header")
            self.log(f"{'='*60}", "header")
            
            result = engine.run_strategy(
                strategy=strategy,
                symbols=symbols,
                start=self.start_date_var.get(),
                end=self.end_date_var.get(),
                params=params,
                cash=float(self.cash_var.get()),
                commission=float(self.commission_var.get()),
                slippage=float(self.slippage_var.get()),
                benchmark=self.benchmark_var.get() or None,
                adj=self.adj_var.get() or None,
                out_dir=self.output_dir_var.get(),
                enable_plot=self.plot_var.get()
            )
            
            # 格式化输出（与 CLI 一致）
            self.log(f"\n📊 回测结果:", "success")
            self.log(f"{'─'*60}", "info")
            
            # 基本信息
            self.log(f"策略名称: {strategy}", "info")
            self.log(f"股票代码: {', '.join(symbols)}", "info")
            self.log(f"回测区间: {self.start_date_var.get()} ~ {self.end_date_var.get()}", "info")
            self.log(f"初始资金: ¥{float(self.cash_var.get()):,.2f}", "info")
            
            self.log(f"\n💰 收益指标:", "success")
            self.log(f"{'─'*60}", "info")
            self.log(f"  累计收益率:     {result.get('cum_return', 0):>10.2%}", "info")
            self.log(f"  年化收益率:     {result.get('ann_return', 0):>10.2%}", "info")
            self.log(f"  最终市值:       {result.get('final_value', 0):>10,.2f}", "info")
            
            if result.get('bench_return') is not None:
                self.log(f"  基准收益率:     {result.get('bench_return', 0):>10.2%}", "info")
                self.log(f"  超额收益:       {result.get('cum_return', 0) - result.get('bench_return', 0):>10.2%}", "success")
            
            self.log(f"\n📈 风险指标:", "success")
            self.log(f"{'─'*60}", "info")
            self.log(f"  夏普比率:       {result.get('sharpe', float('nan')):>10.4f}", "info")
            self.log(f"  最大回撤:       {result.get('mdd', 0):>10.2%}", "info")
            self.log(f"  年化波动率:     {result.get('ann_vol', 0):>10.2%}", "info")
            self.log(f"  卡尔玛比率:     {result.get('calmar', float('nan')):>10.4f}", "info")
            
            self.log(f"\n🔄 交易指标:", "success")
            self.log(f"{'─'*60}", "info")
            self.log(f"  总交易次数:     {result.get('trades', 0):>10d}", "info")
            self.log(f"  胜率:           {result.get('win_rate', 0):>10.2%}", "info")
            self.log(f"  盈亏比:         {result.get('profit_factor', float('nan')):>10.4f}", "info")
            self.log(f"  平均持仓周期:   {result.get('avg_hold_bars', 0):>10.1f} 天", "info")
            self.log(f"  交易频率:       {result.get('trade_freq', 0):>10.4f} 次/日", "info")
            
            if result.get('avg_win') is not None and result.get('avg_loss') is not None:
                self.log(f"  平均盈利:       {result.get('avg_win', 0):>10.2%}", "info")
                self.log(f"  平均亏损:       {result.get('avg_loss', 0):>10.2%}", "info")
                self.log(f"  盈亏比率:       {result.get('payoff_ratio', float('nan')):>10.4f}", "info")
            
            self.log(f"\n📂 输出文件:", "success")
            self.log(f"{'─'*60}", "info")
            out_dir = self.output_dir_var.get()
            self.log(f"  报告目录: {out_dir}", "info")
            self.log(f"  净值文件: {strategy}_nav.csv", "info")
            if self.plot_var.get():
                self.log(f"  图表文件: {strategy}_chart.png", "info")
            
            self.log(f"\n{'='*60}", "success")
    
    def _run_grid_search(self, engine, symbols, strategies):
        """网格搜索"""
        # 解析网格参数
        grid_text = self.grid_params_text.get("1.0", tk.END).strip()
        try:
            grid = json.loads(grid_text)
        except json.JSONDecodeError as e:
            self.log(f"❌ 网格参数 JSON 格式错误: {str(e)}", "error")
            return
        
        for strategy in strategies:
            self.log(f"\n{'='*60}", "header")
            self.log(f"网格搜索策略: {strategy}", "header")
            self.log(f"{'='*60}", "header")
            
            # 计算参数组合总数
            import itertools
            param_names = list(grid.keys())
            param_values = [grid[k] if isinstance(grid[k], list) else [grid[k]] for k in param_names]
            total_combinations = 1
            for values in param_values:
                total_combinations *= len(values)
            
            self.log(f"📊 参数搜索空间:", "info")
            for name in param_names:
                values = grid[name] if isinstance(grid[name], list) else [grid[name]]
                self.log(f"  {name}: {values}", "info")
            self.log(f"  总计组合数: {total_combinations}", "success")
            
            results = engine.run_grid_search(
                strategy=strategy,
                symbols=symbols,
                start=self.start_date_var.get(),
                end=self.end_date_var.get(),
                param_grid=grid,
                cash=float(self.cash_var.get()),
                commission=float(self.commission_var.get()),
                slippage=float(self.slippage_var.get()),
                benchmark=self.benchmark_var.get() or None,
                adj=self.adj_var.get() or None,
                out_dir=self.output_dir_var.get(),
                enable_plot=self.plot_var.get(),
                metric=self.metric_var.get(),
                max_workers=int(self.max_workers_var.get())
            )
            
            # 显示结果（与 CLI 一致）
            if results:
                self.log(f"\n📈 网格搜索完成! 共测试 {len(results)} 组参数", "success")
                self.log(f"{'─'*60}", "info")
                
                # 排序并显示 Top 5
                metric = self.metric_var.get()
                sorted_results = sorted(results, key=lambda x: x.get(metric, float('-inf')), reverse=True)
                
                self.log(f"\n🏆 Top 5 参数组合 (按 {metric} 排序):", "success")
                self.log(f"{'─'*60}", "info")
                
                for i, res in enumerate(sorted_results[:5], 1):
                    self.log(f"\n#{i} 排名", "header")
                    self.log(f"  参数: {res.get('params', {})}", "info")
                    self.log(f"  {metric}:        {res.get(metric, float('nan')):>10.4f}", "success")
                    self.log(f"  累计收益率:    {res.get('cum_return', 0):>10.2%}", "info")
                    self.log(f"  夏普比率:      {res.get('sharpe', float('nan')):>10.4f}", "info")
                    self.log(f"  最大回撤:      {res.get('mdd', 0):>10.2%}", "info")
                    self.log(f"  交易次数:      {res.get('trades', 0):>10d}", "info")
                
                # 输出文件信息
                self.log(f"\n📂 输出文件:", "success")
                self.log(f"{'─'*60}", "info")
                out_dir = self.output_dir_var.get()
                self.log(f"  报告目录: {out_dir}", "info")
                self.log(f"  结果文件: {strategy}_grid_results.csv", "info")
                self.log(f"  最优参数: {strategy}_best_params.json", "info")
            else:
                self.log(f"⚠ 网格搜索未返回结果", "warning")
            
            self.log(f"\n{'='*60}", "success")
    
    def _run_auto_pipeline(self, engine, symbols, strategies):
        """自动化流程"""
        self.log(f"\n{'='*60}", "header")
        self.log(f"运行自动化流程", "header")
        self.log(f"{'='*60}", "header")
        
        self.log(f"\n📋 任务配置:", "info")
        self.log(f"  股票数量: {len(symbols)}", "info")
        self.log(f"  策略数量: {len(strategies)}", "info")
        self.log(f"  回测区间: {self.start_date_var.get()} ~ {self.end_date_var.get()}", "info")
        self.log(f"  基准指数: {self.benchmark_var.get() or '000300.SH'}", "info")
        self.log(f"  筛选条件: Top {self.top_n_var.get()}, 最少 {self.min_trades_var.get()} 笔交易", "info")
        self.log(f"  并行线程: {self.workers_var.get()}", "info")
        
        if self.hot_only_var.get():
            self.log(f"  热门策略: 仅使用热门参数", "info")
        if self.use_benchmark_regime_var.get():
            self.log(f"  市场环境: 使用基准识别 ({self.regime_scope_var.get()})", "info")
        
        self.log(f"\n🚀 开始自动化分析...", "success")
        
        engine.auto_pipeline(
            symbols=symbols,
            start=self.start_date_var.get(),
            end=self.end_date_var.get(),
            strategies=strategies,
            benchmark=self.benchmark_var.get() or "000300.SH",
            top_n=int(self.top_n_var.get()),
            min_trades=int(self.min_trades_var.get()),
            cash=float(self.cash_var.get()),
            commission=float(self.commission_var.get()),
            slippage=float(self.slippage_var.get()),
            adj=self.adj_var.get() or None,
            out_dir=self.output_dir_var.get(),
            workers=int(self.workers_var.get()),
            hot_only=self.hot_only_var.get(),
            use_benchmark_regime=self.use_benchmark_regime_var.get(),
            regime_scope=self.regime_scope_var.get()
        )
        
        self.log(f"\n📂 输出文件:", "success")
        self.log(f"{'─'*60}", "info")
        out_dir = self.output_dir_var.get()
        self.log(f"  报告目录: {out_dir}", "info")
        self.log(f"  综合报告: auto_pipeline_summary.csv", "info")
        self.log(f"  最优策略: top_strategies.json", "info")
        self.log(f"  详细日志: auto_pipeline.log", "info")
        
        self.log(f"\n{'='*60}", "success")
    
    def stop_backtest(self):
        """停止回测"""
        if messagebox.askyesno("确认", "确定要停止回测吗？"):
            self.running = False
            self.log("用户取消回测", "warning")
    
    def _reset_buttons(self):
        """重置按钮状态"""
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def load_preset_config(self, event=None):
        """加载预设配置方案"""
        preset_name = self.preset_var.get()
        
        if preset_name == "选择方案..." or preset_name not in self.PRESET_CONFIGS:
            return
        
        config = self.PRESET_CONFIGS[preset_name]
        
        try:
            # 加载股票列表
            self.symbols_text.delete("1.0", tk.END)
            self.symbols_text.insert("1.0", "\n".join(config.get("symbols", [])))
            
            # 加载日期
            self.start_date_var.set(config.get("start_date", "2022-01-01"))
            if "end_date" in config:
                self.end_date_var.set(config["end_date"])
            else:
                self.end_date_var.set(datetime.now().strftime("%Y-%m-%d"))
            
            # 选择策略
            self.strategy_listbox.selection_clear(0, tk.END)
            strategies = config.get("strategies", [])
            for i in range(self.strategy_listbox.size()):
                text = self.strategy_listbox.get(i)
                name = text.split(" - ")[0]
                if name in strategies:
                    self.strategy_listbox.selection_set(i)
            
            # 设置运行模式
            self.mode_var.set(config.get("mode", "auto"))
            
            # 设置其他选项
            self.hot_only_var.set(config.get("hot_only", False))
            self.use_benchmark_regime_var.set(config.get("use_benchmark_regime", False))
            self.regime_scope_var.set(config.get("regime_scope", "trend"))
            
            if "top_n" in config:
                self.top_n_var.set(str(config["top_n"]))
            if "workers" in config:
                self.workers_var.set(str(config["workers"]))
            
            self.log(f"✓ 已加载配置方案: {preset_name}", "success")
            self.log(f"  {config.get('description', '')}", "info")
            
            messagebox.showinfo(
                "配置已加载",
                f"已加载配置方案: {preset_name}\n\n{config.get('description', '')}\n\n请检查配置后点击'开始回测'"
            )
            
        except Exception as e:
            self.log(f"✗ 加载配置方案失败: {str(e)}", "error")
            messagebox.showerror("错误", f"加载配置方案失败:\n{str(e)}")
    
    def show_preset_details(self):
        """显示所有预设方案的详情"""
        details_window = tk.Toplevel(self.root)
        details_window.title("快速配置方案详情")
        details_window.geometry("700x500")
        
        text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, font=("Courier New", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text.insert(tk.END, "=" * 70 + "\n")
        text.insert(tk.END, "快速配置方案详情\n")
        text.insert(tk.END, "=" * 70 + "\n\n")
        
        for i, (name, config) in enumerate(self.PRESET_CONFIGS.items(), 1):
            text.insert(tk.END, f"{i}. {name}\n", "bold")
            text.insert(tk.END, "-" * 70 + "\n")
            text.insert(tk.END, f"说明: {config.get('description', 'N/A')}\n")
            text.insert(tk.END, f"股票: {', '.join(config.get('symbols', []))}\n")
            text.insert(tk.END, f"策略: {', '.join(config.get('strategies', []))}\n")
            text.insert(tk.END, f"起始日期: {config.get('start_date', 'N/A')}\n")
            text.insert(tk.END, f"运行模式: {config.get('mode', 'auto')}\n")
            text.insert(tk.END, f"Hot-Only: {'是' if config.get('hot_only', False) else '否'}\n")
            if "top_n" in config:
                text.insert(tk.END, f"Top N: {config['top_n']}\n")
            text.insert(tk.END, "\n")
        
        text.config(state=tk.DISABLED)
        
        # 添加关闭按钮
        ttk.Button(
            details_window,
            text="关闭",
            command=details_window.destroy
        ).pack(pady=10)


def main():
    """主函数"""
    root = tk.Tk()
    
    # 设置样式
    style = ttk.Style()
    style.theme_use('clam')
    
    # 创建应用
    app = BacktestGUI(root)
    
    # 运行
    root.mainloop()


if __name__ == "__main__":
    main()
