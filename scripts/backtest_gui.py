#!/usr/bin/env python3
"""
Backtest Analysis GUI V2.10.3
完整的回测分析图形界面，支持所有CLI功能

版本: V2.10.3.0
日期: 2025-10-26
更新: 
- 支持所有CLI命令 (run/grid/auto/list)
- 增加独立数据下载功能
- 现代化界面设计
- 完整的错误处理
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
import sys
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Sequence
from queue import Queue, Empty

# 设置 matplotlib 使用非 GUI 后端
import matplotlib
matplotlib.use('Agg')

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.backtest.strategy_modules import STRATEGY_REGISTRY
from src.data_sources.providers import PROVIDER_NAMES

# 与 CLI 保持一致的默认缓存目录
CACHE_DEFAULT = "./cache"


# ============================================================
# 命令构建器 (CLI 特性与 GUI 解耦，便于测试与维护)
# ============================================================

@dataclass
class RunConfig:
    strategy: str
    symbols: Sequence[str]
    start: str
    end: str
    source: str
    benchmark: Optional[str] = None
    benchmark_source: Optional[str] = None
    params_json: Optional[str] = None
    cash: str = "200000"
    commission: str = "0.0001"
    slippage: str = "0.0005"
    adj: Optional[str] = None
    out_dir: Optional[str] = None
    cache_dir: str = CACHE_DEFAULT
    plot: bool = False
    fee_config: Optional[str] = None
    fee_params: Optional[str] = None


@dataclass
class GridConfig:
    strategy: str
    symbols: Sequence[str]
    start: str
    end: str
    source: str
    benchmark: Optional[str] = None
    benchmark_source: Optional[str] = None
    grid_json: Optional[str] = None
    cash: str = "200000"
    commission: str = "0.0001"
    slippage: str = "0.0005"
    adj: Optional[str] = None
    cache_dir: str = CACHE_DEFAULT
    out_csv: Optional[str] = None
    workers: str = "1"
    fee_config: Optional[str] = None
    fee_params: Optional[str] = None


@dataclass
class AutoConfig:
    symbols: Sequence[str]
    start: str
    end: str
    source: str
    benchmark: str = "000300.SH"
    benchmark_source: Optional[str] = None
    strategies: Optional[Sequence[str]] = None
    top_n: str = "5"
    min_trades: str = "1"
    cash: str = "200000"
    commission: str = "0.0001"
    slippage: str = "0.001"
    adj: Optional[str] = None
    cache_dir: str = CACHE_DEFAULT
    out_dir: str = "./reports_auto"
    workers: str = "1"
    hot_only: bool = False
    use_benchmark_regime: bool = False
    regime_scope: str = "trend"


@dataclass
class ComboConfig:
    navs: Sequence[str]
    objective: str = "sharpe"
    step: str = "0.25"
    allow_short: bool = False
    max_weight: str = "1.0"
    risk_free: str = "0.0"
    out: Optional[str] = None


def _ensure_valid_json(text: Optional[str], label: str) -> Optional[str]:
    """Validate JSON string (if provided) and return trimmed text."""
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    try:
        json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} JSON 格式错误: {exc}") from exc
    return stripped


class CommandBuilder:
    """Build CLI commands compatible with unified_backtest_framework."""

    @staticmethod
    def build_run(config: RunConfig) -> List[str]:
        params_json = _ensure_valid_json(config.params_json, "策略参数") if config.params_json else None
        fee_params = _ensure_valid_json(config.fee_params, "手续费参数") if config.fee_params else None

        cmd = [
            sys.executable,
            "unified_backtest_framework.py",
            "run",
            "--strategy",
            config.strategy,
            "--symbols",
            *config.symbols,
            "--start",
            config.start,
            "--end",
            config.end,
            "--source",
            config.source,
            "--cash",
            config.cash,
            "--commission",
            config.commission,
            "--slippage",
            config.slippage,
            "--cache_dir",
            config.cache_dir,
        ]

        if config.benchmark:
            cmd.extend(["--benchmark", config.benchmark])
        if config.benchmark_source:
            cmd.extend(["--benchmark_source", config.benchmark_source])
        if config.adj:
            cmd.extend(["--adj", config.adj])
        if params_json:
            cmd.extend(["--params", params_json])
        if config.out_dir:
            cmd.extend(["--out_dir", config.out_dir])
        if config.plot:
            cmd.append("--plot")
        if config.fee_config:
            cmd.extend(["--fee-config", config.fee_config])
        if fee_params:
            cmd.extend(["--fee-params", fee_params])
        return cmd

    @staticmethod
    def build_grid(config: GridConfig) -> List[str]:
        grid_json = _ensure_valid_json(config.grid_json, "参数网格") if config.grid_json else None
        fee_params = _ensure_valid_json(config.fee_params, "手续费参数") if config.fee_params else None

        cmd = [
            sys.executable,
            "unified_backtest_framework.py",
            "grid",
            "--strategy",
            config.strategy,
            "--symbols",
            *config.symbols,
            "--start",
            config.start,
            "--end",
            config.end,
            "--source",
            config.source,
            "--cash",
            config.cash,
            "--commission",
            config.commission,
            "--slippage",
            config.slippage,
            "--cache_dir",
            config.cache_dir,
            "--workers",
            config.workers,
        ]

        if config.benchmark:
            cmd.extend(["--benchmark", config.benchmark])
        if config.benchmark_source:
            cmd.extend(["--benchmark_source", config.benchmark_source])
        if config.adj:
            cmd.extend(["--adj", config.adj])
        if grid_json:
            cmd.extend(["--grid", grid_json])
        if config.out_csv:
            cmd.extend(["--out_csv", config.out_csv])
        if config.fee_config:
            cmd.extend(["--fee-config", config.fee_config])
        if fee_params:
            cmd.extend(["--fee-params", fee_params])
        return cmd

    @staticmethod
    def build_auto(config: AutoConfig) -> List[str]:
        cmd = [
            sys.executable,
            "unified_backtest_framework.py",
            "auto",
            "--symbols",
            *config.symbols,
            "--start",
            config.start,
            "--end",
            config.end,
            "--source",
            config.source,
            "--benchmark",
            config.benchmark,
            "--cash",
            config.cash,
            "--commission",
            config.commission,
            "--slippage",
            config.slippage,
            "--cache_dir",
            config.cache_dir,
            "--workers",
            config.workers,
            "--top_n",
            config.top_n,
            "--min_trades",
            config.min_trades,
            "--out_dir",
            config.out_dir,
            "--regime_scope",
            config.regime_scope,
        ]

        if config.benchmark_source:
            cmd.extend(["--benchmark_source", config.benchmark_source])
        if config.strategies:
            cmd.extend(["--strategies", *config.strategies])
        if config.adj:
            cmd.extend(["--adj", config.adj])
        if config.hot_only:
            cmd.append("--hot_only")
        if config.use_benchmark_regime:
            cmd.append("--use_benchmark_regime")
        return cmd

    @staticmethod
    def build_combo(config: ComboConfig) -> List[str]:
        if not config.navs:
            raise ValueError("请至少选择一个 NAV CSV 文件")
        cmd = [
            sys.executable,
            "unified_backtest_framework.py",
            "combo",
            "--navs",
            *config.navs,
            "--objective",
            config.objective,
            "--step",
            str(config.step),
            "--max_weight",
            str(config.max_weight),
            "--risk_free",
            str(config.risk_free),
        ]
        if config.allow_short:
            cmd.append("--allow_short")
        if config.out:
            cmd.extend(["--out", config.out])
        return cmd


class BacktestGUI:
    """回测分析主界面 V2.10.3"""
    
    # 预设配置
    PRESET_CONFIGS = {
        "白酒股-趋势策略": {
            "symbols": ["600519.SH", "000858.SZ", "000568.SZ"],
            "strategies": ["ema", "macd", "adx_trend"],
            "start_date": "2022-01-01",
            "description": "白酒行业股票 + 趋势跟踪策略"
        },
        "银行股-震荡策略": {
            "symbols": ["600036.SH", "601318.SH", "600000.SH"],
            "strategies": ["bollinger", "rsi", "keltner"],
            "start_date": "2022-01-01",
            "description": "银行股票 + 震荡交易策略"
        },
        "科技股-全策略": {
            "symbols": ["000333.SZ", "002230.SZ", "600276.SH"],
            "strategies": ["ema", "macd", "bollinger", "rsi"],
            "start_date": "2022-01-01",
            "description": "科技股票 + 多种策略综合"
        },
    }
    
    def __init__(self, root):
        self.root = root
        self.root.title("量化回测分析系统 V2.10.3.0")
        self.root.geometry("1400x900")
        
        # 状态变量
        self.running = False
        self.process = None
        self.log_queue: "Queue[str]" = Queue()
        self.log_buffer: List[str] = []
        self.log_poll_ms = 120
        self.max_log_lines = 800
        self.strategy_choices = sorted(STRATEGY_REGISTRY.keys())
        
        # 样式配置
        self.setup_styles()
        
        # 创建主界面
        self.create_widgets()

        # 启动日志轮询，确保后台线程安全更新UI
        self.root.after(self.log_poll_ms, self._poll_log_queue)
        
        # 加载默认配置
        self.load_default_config()
    
    def setup_styles(self):
        """配置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置颜色
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Section.TLabel', font=('Arial', 10, 'bold'))
        style.configure('Run.TButton', background='#4CAF50')
        style.configure('Stop.TButton', background='#f44336')
    
    def create_widgets(self):
        """创建所有界面组件"""
        # 创建主容器
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧面板（配置区）
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=2)
        
        # 右侧面板（输出区）
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=3)
        
        # 创建标签页
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 标签页1: RUN - 单策略回测
        self.create_run_tab()
        
        # 标签页2: GRID - 参数网格搜索
        self.create_grid_tab()
        
        # 标签页3: AUTO - 多策略自动优化
        self.create_auto_tab()

        # 标签页4: COMBO - 组合权重优化
        self.create_combo_tab()
        
        # 标签页5: DATA - 数据下载
        self.create_data_download_tab()
        
        # 标签页5: LIST - 策略列表
        self.create_list_tab()
        
        # 右侧：输出区域
        self.create_output_area(right_frame)
        
        # 底部：控制按钮
        self.create_control_buttons(left_frame)
    
    def create_run_tab(self):
        """RUN命令标签页：单策略回测"""
        run_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(run_frame, text="🎯 单策略回测 (run)")
        
        # 使用滚动区域
        canvas = tk.Canvas(run_frame)
        scrollbar = ttk.Scrollbar(run_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        
        # 策略选择
        ttk.Label(scrollable_frame, text="策略选择:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.run_strategy_var = tk.StringVar(value="macd")
        strategy_frame = ttk.Frame(scrollable_frame)
        strategy_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Combobox(
            strategy_frame, 
            textvariable=self.run_strategy_var,
            values=self.strategy_choices,
            state="readonly",
            width=30
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            strategy_frame,
            text="策略说明",
            command=self.show_strategy_info
        ).pack(side=tk.LEFT)
        row += 1
        
        # 股票代码
        ttk.Label(scrollable_frame, text="股票代码 (多个用空格分隔):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.run_symbols_text = tk.Text(scrollable_frame, height=3, width=40)
        self.run_symbols_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.run_symbols_text.insert('1.0', '600519.SH 000858.SZ')
        row += 1
        
        # 日期范围
        ttk.Label(scrollable_frame, text="日期范围:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        date_frame = ttk.Frame(scrollable_frame)
        date_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(date_frame, text="开始:").pack(side=tk.LEFT)
        self.run_start_var = tk.StringVar(value="2023-01-01")
        ttk.Entry(date_frame, textvariable=self.run_start_var, width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(date_frame, text="结束:").pack(side=tk.LEFT)
        self.run_end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.run_end_var, width=12).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 数据源配置
        ttk.Label(scrollable_frame, text="数据源配置:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        source_frame = ttk.Frame(scrollable_frame)
        source_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(source_frame, text="数据源:").pack(side=tk.LEFT)
        self.run_source_var = tk.StringVar(value="akshare")
        ttk.Combobox(
            source_frame,
            textvariable=self.run_source_var,
            values=sorted(PROVIDER_NAMES),
            state="readonly",
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(source_frame, text="复权:").pack(side=tk.LEFT)
        self.run_adj_var = tk.StringVar(value="qfq")
        ttk.Combobox(
            source_frame,
            textvariable=self.run_adj_var,
            values=["qfq", "hfq", "noadj"],
            state="readonly",
            width=8
        ).pack(side=tk.LEFT, padx=5)
        row += 1

        # 数据源与缓存
        ttk.Label(scrollable_frame, text="基准数据源 / 缓存:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        benchmark_source_frame = ttk.Frame(scrollable_frame)
        benchmark_source_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(benchmark_source_frame, text="基准源(可选):").pack(side=tk.LEFT)
        self.run_benchmark_source_var = tk.StringVar(value="")
        ttk.Combobox(
            benchmark_source_frame,
            textvariable=self.run_benchmark_source_var,
            values=[""] + sorted(PROVIDER_NAMES),
            state="readonly",
            width=16
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(benchmark_source_frame, text="缓存目录:").pack(side=tk.LEFT)
        self.run_cache_dir_var = tk.StringVar(value=CACHE_DEFAULT)
        ttk.Entry(benchmark_source_frame, textvariable=self.run_cache_dir_var, width=24).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        row += 1
        
        # 基准配置
        ttk.Label(scrollable_frame, text="基准指数 (可选):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.run_benchmark_var = tk.StringVar(value="000300.SH")
        ttk.Entry(scrollable_frame, textvariable=self.run_benchmark_var, width=40).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1
        
        # 回测参数
        ttk.Label(scrollable_frame, text="回测参数:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        params_frame = ttk.Frame(scrollable_frame)
        params_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(params_frame, text="初始资金:").grid(row=0, column=0, sticky=tk.W)
        self.run_cash_var = tk.StringVar(value="200000")
        ttk.Entry(params_frame, textvariable=self.run_cash_var, width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(params_frame, text="佣金率:").grid(row=0, column=2, sticky=tk.W)
        self.run_commission_var = tk.StringVar(value="0.0001")
        ttk.Entry(params_frame, textvariable=self.run_commission_var, width=15).grid(row=0, column=3, padx=5)
        
        ttk.Label(params_frame, text="滑点:").grid(row=1, column=0, sticky=tk.W)
        self.run_slippage_var = tk.StringVar(value="0.0005")
        ttk.Entry(params_frame, textvariable=self.run_slippage_var, width=15).grid(row=1, column=1, padx=5)
        row += 1
        
        # 策略参数 (JSON)
        ttk.Label(scrollable_frame, text="策略参数 (JSON，可选):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.run_params_text = tk.Text(scrollable_frame, height=4, width=40)
        self.run_params_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.run_params_text.insert('1.0', '{\n  "fast": 12,\n  "slow": 26\n}')
        row += 1

        # 手续费插件
        ttk.Label(scrollable_frame, text="手续费插件 (fee-config，可选):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        fee_frame = ttk.Frame(scrollable_frame)
        fee_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.run_fee_config_var = tk.StringVar(value="")
        ttk.Entry(fee_frame, textvariable=self.run_fee_config_var, width=18).pack(side=tk.LEFT, padx=5)

        ttk.Label(fee_frame, text="fee-params (JSON):").pack(side=tk.LEFT)
        self.run_fee_params_var = tk.StringVar(value="")
        ttk.Entry(fee_frame, textvariable=self.run_fee_params_var, width=30).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 输出配置
        ttk.Label(scrollable_frame, text="输出配置:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.run_plot_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            scrollable_frame,
            text="生成回测图表和报告",
            variable=self.run_plot_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        row += 1
        
        ttk.Label(scrollable_frame, text="输出目录 (可选):").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        out_frame = ttk.Frame(scrollable_frame)
        out_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.run_out_dir_var = tk.StringVar(value="")
        ttk.Entry(out_frame, textvariable=self.run_out_dir_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_frame, text="浏览", command=self.browse_out_dir_run).pack(side=tk.LEFT, padx=5)
    
    def create_grid_tab(self):
        """GRID命令标签页：参数网格搜索"""
        grid_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(grid_frame, text="🔍 网格搜索 (grid)")
        
        # 使用滚动区域
        canvas = tk.Canvas(grid_frame)
        scrollbar = ttk.Scrollbar(grid_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        
        # 策略选择
        ttk.Label(scrollable_frame, text="策略选择:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.grid_strategy_var = tk.StringVar(value="macd")
        ttk.Combobox(
            scrollable_frame, 
            textvariable=self.grid_strategy_var,
            values=self.strategy_choices,
            state="readonly",
            width=40
        ).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 股票代码
        ttk.Label(scrollable_frame, text="股票代码:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.grid_symbols_text = tk.Text(scrollable_frame, height=3, width=40)
        self.grid_symbols_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.grid_symbols_text.insert('1.0', '600519.SH')
        row += 1
        
        # 日期范围
        ttk.Label(scrollable_frame, text="日期范围:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        date_frame = ttk.Frame(scrollable_frame)
        date_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(date_frame, text="开始:").pack(side=tk.LEFT)
        self.grid_start_var = tk.StringVar(value="2023-01-01")
        ttk.Entry(date_frame, textvariable=self.grid_start_var, width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(date_frame, text="结束:").pack(side=tk.LEFT)
        self.grid_end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.grid_end_var, width=12).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 参数网格定义
        ttk.Label(scrollable_frame, text="参数网格 (JSON):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        ttk.Label(scrollable_frame, text="例: {\"fast\": [10, 12, 15], \"slow\": [26, 30]}", 
                 font=('Arial', 8, 'italic')).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=2
        )
        row += 1
        
        self.grid_params_text = tk.Text(scrollable_frame, height=6, width=40)
        self.grid_params_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.grid_params_text.insert('1.0', '{\n  "fast": [10, 12, 15],\n  "slow": [26, 30]\n}')
        row += 1
        
        # 数据源和回测参数
        ttk.Label(scrollable_frame, text="数据源:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.grid_source_var = tk.StringVar(value="akshare")
        ttk.Combobox(
            scrollable_frame,
            textvariable=self.grid_source_var,
            values=sorted(PROVIDER_NAMES),
            state="readonly",
            width=40
        ).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1

        # 基准数据源与缓存
        ttk.Label(scrollable_frame, text="基准数据源 / 缓存目录:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        benchmark_source_frame = ttk.Frame(scrollable_frame)
        benchmark_source_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(benchmark_source_frame, text="基准源(可选):").pack(side=tk.LEFT)
        self.grid_benchmark_source_var = tk.StringVar(value="")
        ttk.Combobox(
            benchmark_source_frame,
            textvariable=self.grid_benchmark_source_var,
            values=[""] + sorted(PROVIDER_NAMES),
            state="readonly",
            width=16
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(benchmark_source_frame, text="缓存目录:").pack(side=tk.LEFT)
        self.grid_cache_dir_var = tk.StringVar(value=CACHE_DEFAULT)
        ttk.Entry(benchmark_source_frame, textvariable=self.grid_cache_dir_var, width=26).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        row += 1

        # 回测参数
        ttk.Label(scrollable_frame, text="回测参数:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        backtest_frame = ttk.Frame(scrollable_frame)
        backtest_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(backtest_frame, text="初始资金:").grid(row=0, column=0, sticky=tk.W)
        self.grid_cash_var = tk.StringVar(value="200000")
        ttk.Entry(backtest_frame, textvariable=self.grid_cash_var, width=14).grid(row=0, column=1, padx=5)

        ttk.Label(backtest_frame, text="佣金率:").grid(row=0, column=2, sticky=tk.W)
        self.grid_commission_var = tk.StringVar(value="0.0001")
        ttk.Entry(backtest_frame, textvariable=self.grid_commission_var, width=14).grid(row=0, column=3, padx=5)

        ttk.Label(backtest_frame, text="滑点:").grid(row=1, column=0, sticky=tk.W)
        self.grid_slippage_var = tk.StringVar(value="0.0005")
        ttk.Entry(backtest_frame, textvariable=self.grid_slippage_var, width=14).grid(row=1, column=1, padx=5)

        ttk.Label(backtest_frame, text="复权:").grid(row=1, column=2, sticky=tk.W)
        self.grid_adj_var = tk.StringVar(value="")
        ttk.Combobox(
            backtest_frame,
            textvariable=self.grid_adj_var,
            values=["", "qfq", "hfq", "noadj"],
            state="readonly",
            width=12
        ).grid(row=1, column=3, padx=5)

        ttk.Label(backtest_frame, text="基准(可选):").grid(row=2, column=0, sticky=tk.W)
        self.grid_benchmark_var = tk.StringVar(value="")
        ttk.Entry(backtest_frame, textvariable=self.grid_benchmark_var, width=20).grid(row=2, column=1, columnspan=3, padx=5, sticky=(tk.W, tk.E))
        row += 1
        
        # 并行workers
        ttk.Label(scrollable_frame, text="并行Workers:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.grid_workers_var = tk.StringVar(value="4")
        ttk.Spinbox(scrollable_frame, from_=1, to=16, textvariable=self.grid_workers_var, width=38).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1

        # 手续费插件
        ttk.Label(scrollable_frame, text="手续费插件 (可选):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        fee_frame = ttk.Frame(scrollable_frame)
        fee_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.grid_fee_config_var = tk.StringVar(value="")
        ttk.Entry(fee_frame, textvariable=self.grid_fee_config_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(fee_frame, text="fee-params (JSON):").pack(side=tk.LEFT)
        self.grid_fee_params_var = tk.StringVar(value="")
        ttk.Entry(fee_frame, textvariable=self.grid_fee_params_var, width=28).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 输出CSV
        ttk.Label(scrollable_frame, text="输出CSV文件:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        out_frame = ttk.Frame(scrollable_frame)
        out_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.grid_out_csv_var = tk.StringVar(value="grid_results.csv")
        ttk.Entry(out_frame, textvariable=self.grid_out_csv_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_frame, text="浏览", command=self.browse_out_csv_grid).pack(side=tk.LEFT, padx=5)
    
    def create_auto_tab(self):
        """AUTO命令标签页：多策略自动优化"""
        auto_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(auto_frame, text="🚀 自动优化 (auto)")
        
        # 使用滚动区域
        canvas = tk.Canvas(auto_frame)
        scrollbar = ttk.Scrollbar(auto_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        
        # 预设配置
        ttk.Label(scrollable_frame, text="预设配置 (快速启动):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        preset_frame = ttk.Frame(scrollable_frame)
        preset_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.auto_preset_var = tk.StringVar()
        preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.auto_preset_var,
            values=list(self.PRESET_CONFIGS.keys()),
            state="readonly",
            width=25
        )
        preset_combo.pack(side=tk.LEFT, padx=5)
        preset_combo.bind('<<ComboboxSelected>>', self.load_preset_auto)
        
        ttk.Button(preset_frame, text="加载预设", command=self.load_preset_auto).pack(side=tk.LEFT)
        row += 1
        
        # 股票代码
        ttk.Label(scrollable_frame, text="股票代码 (多个用空格分隔):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.auto_symbols_text = tk.Text(scrollable_frame, height=3, width=40)
        self.auto_symbols_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.auto_symbols_text.insert('1.0', '600519.SH 000858.SZ')
        row += 1
        
        # 策略选择
        ttk.Label(scrollable_frame, text="策略列表 (多选):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        # 创建策略多选列表
        strategy_list_frame = ttk.Frame(scrollable_frame)
        strategy_list_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        strategy_scrollbar = ttk.Scrollbar(strategy_list_frame)
        strategy_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.auto_strategies_listbox = tk.Listbox(
            strategy_list_frame,
            selectmode=tk.MULTIPLE,
            height=6,
            yscrollcommand=strategy_scrollbar.set
        )
        self.auto_strategies_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        strategy_scrollbar.config(command=self.auto_strategies_listbox.yview)
        
        # 填充策略列表
        for strategy in self.strategy_choices:
            self.auto_strategies_listbox.insert(tk.END, strategy)
        
        # 默认选择几个常用策略
        for idx, strategy in enumerate(self.strategy_choices):
            if strategy in ["ema", "macd", "bollinger", "rsi"]:
                self.auto_strategies_listbox.selection_set(idx)
        row += 1
        
        # 日期范围
        ttk.Label(scrollable_frame, text="日期范围:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        date_frame = ttk.Frame(scrollable_frame)
        date_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(date_frame, text="开始:").pack(side=tk.LEFT)
        self.auto_start_var = tk.StringVar(value="2022-01-01")
        ttk.Entry(date_frame, textvariable=self.auto_start_var, width=12).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(date_frame, text="结束:").pack(side=tk.LEFT)
        self.auto_end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.auto_end_var, width=12).pack(side=tk.LEFT, padx=5)
        row += 1

        # 数据源与复权
        ttk.Label(scrollable_frame, text="数据源 / 复权:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        source_frame = ttk.Frame(scrollable_frame)
        source_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(source_frame, text="数据源:").pack(side=tk.LEFT)
        self.auto_source_var = tk.StringVar(value="akshare")
        ttk.Combobox(
            source_frame,
            textvariable=self.auto_source_var,
            values=sorted(PROVIDER_NAMES),
            state="readonly",
            width=14
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(source_frame, text="复权:").pack(side=tk.LEFT)
        self.auto_adj_var = tk.StringVar(value="")
        ttk.Combobox(
            source_frame,
            textvariable=self.auto_adj_var,
            values=["", "qfq", "hfq", "noadj"],
            state="readonly",
            width=10
        ).pack(side=tk.LEFT, padx=5)
        row += 1

        # 数据源/缓存
        ttk.Label(scrollable_frame, text="基准数据源 / 缓存目录:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        benchmark_source_frame = ttk.Frame(scrollable_frame)
        benchmark_source_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(benchmark_source_frame, text="基准源(可选):").pack(side=tk.LEFT)
        self.auto_benchmark_source_var = tk.StringVar(value="")
        ttk.Combobox(
            benchmark_source_frame,
            textvariable=self.auto_benchmark_source_var,
            values=[""] + sorted(PROVIDER_NAMES),
            state="readonly",
            width=16
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(benchmark_source_frame, text="缓存目录:").pack(side=tk.LEFT)
        self.auto_cache_dir_var = tk.StringVar(value=CACHE_DEFAULT)
        ttk.Entry(benchmark_source_frame, textvariable=self.auto_cache_dir_var, width=26).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        row += 1

        # 回测参数
        ttk.Label(scrollable_frame, text="回测参数:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        params_frame = ttk.Frame(scrollable_frame)
        params_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(params_frame, text="初始资金:").grid(row=0, column=0, sticky=tk.W)
        self.auto_cash_var = tk.StringVar(value="200000")
        ttk.Entry(params_frame, textvariable=self.auto_cash_var, width=12).grid(row=0, column=1, padx=5)

        ttk.Label(params_frame, text="佣金率:").grid(row=0, column=2, sticky=tk.W)
        self.auto_commission_var = tk.StringVar(value="0.0001")
        ttk.Entry(params_frame, textvariable=self.auto_commission_var, width=12).grid(row=0, column=3, padx=5)

        ttk.Label(params_frame, text="滑点:").grid(row=1, column=0, sticky=tk.W)
        self.auto_slippage_var = tk.StringVar(value="0.001")
        ttk.Entry(params_frame, textvariable=self.auto_slippage_var, width=12).grid(row=1, column=1, padx=5)
        row += 1
        
        # 优化参数
        ttk.Label(scrollable_frame, text="优化参数:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        opt_frame = ttk.Frame(scrollable_frame)
        opt_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(opt_frame, text="Top N:").grid(row=0, column=0, sticky=tk.W)
        self.auto_top_n_var = tk.StringVar(value="5")
        ttk.Spinbox(opt_frame, from_=1, to=20, textvariable=self.auto_top_n_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(opt_frame, text="最小交易次数:").grid(row=0, column=2, sticky=tk.W)
        self.auto_min_trades_var = tk.StringVar(value="1")
        ttk.Spinbox(opt_frame, from_=0, to=100, textvariable=self.auto_min_trades_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(opt_frame, text="Workers:").grid(row=1, column=0, sticky=tk.W)
        self.auto_workers_var = tk.StringVar(value="4")
        ttk.Spinbox(opt_frame, from_=1, to=16, textvariable=self.auto_workers_var, width=10).grid(row=1, column=1, padx=5)
        row += 1
        
        # 高级选项
        ttk.Label(scrollable_frame, text="高级选项:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.auto_hot_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            scrollable_frame,
            text="仅使用热门参数区间 (加速搜索)",
            variable=self.auto_hot_only_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1
        
        self.auto_use_regime_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            scrollable_frame,
            text="使用基准市场态势过滤 (牛市过滤)",
            variable=self.auto_use_regime_var
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(scrollable_frame, text="市场态势范围 (regime_scope):").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        self.auto_regime_scope_var = tk.StringVar(value="trend")
        ttk.Combobox(
            scrollable_frame,
            textvariable=self.auto_regime_scope_var,
            values=["trend", "all", "none"],
            state="readonly",
            width=20
        ).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 基准指数
        ttk.Label(scrollable_frame, text="基准指数:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.auto_benchmark_var = tk.StringVar(value="000300.SH")
        ttk.Entry(scrollable_frame, textvariable=self.auto_benchmark_var, width=40).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )
        row += 1
        
        # 输出目录
        ttk.Label(scrollable_frame, text="输出目录:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        out_frame = ttk.Frame(scrollable_frame)
        out_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.auto_out_dir_var = tk.StringVar(value="./reports_auto")
        ttk.Entry(out_frame, textvariable=self.auto_out_dir_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_frame, text="浏览", command=self.browse_out_dir_auto).pack(side=tk.LEFT, padx=5)
    
    def create_combo_tab(self):
        """组合优化标签页"""
        combo_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(combo_frame, text="?? 策略组合优化 (combo)")

        row = 0
        ttk.Label(combo_frame, text="NAV文件（回测结果CSV，支持多选）", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        nav_frame = ttk.Frame(combo_frame)
        nav_frame.grid(row=row, column=0, sticky=(tk.W, tk.E))
        self.combo_navs_text = scrolledtext.ScrolledText(nav_frame, width=60, height=4)
        self.combo_navs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Button(nav_frame, text="选择文件", command=self._browse_nav_files).pack(side=tk.LEFT, padx=5)
        row += 1

        ttk.Label(combo_frame, text="优化目标 / 权重搜索", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1

        opts_frame = ttk.Frame(combo_frame)
        opts_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=5)
        self.combo_objective_var = tk.StringVar(value="sharpe")
        ttk.Label(opts_frame, text="目标:").pack(side=tk.LEFT)
        ttk.Combobox(
            opts_frame,
            textvariable=self.combo_objective_var,
            values=["sharpe", "return", "drawdown"],
            state="readonly",
            width=12,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Label(opts_frame, text="步长:").pack(side=tk.LEFT, padx=4)
        self.combo_step_var = tk.StringVar(value="0.25")
        ttk.Entry(opts_frame, textvariable=self.combo_step_var, width=8).pack(side=tk.LEFT)

        ttk.Label(opts_frame, text="最大权重:").pack(side=tk.LEFT, padx=4)
        self.combo_max_weight_var = tk.StringVar(value="1.0")
        ttk.Entry(opts_frame, textvariable=self.combo_max_weight_var, width=8).pack(side=tk.LEFT)

        self.combo_allow_short_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts_frame, text="允许空头", variable=self.combo_allow_short_var).pack(side=tk.LEFT, padx=6)

        ttk.Label(opts_frame, text="无风险利率(日):").pack(side=tk.LEFT, padx=4)
        self.combo_risk_free_var = tk.StringVar(value="0.0")
        ttk.Entry(opts_frame, textvariable=self.combo_risk_free_var, width=8).pack(side=tk.LEFT)
        row += 1

        ttk.Label(combo_frame, text="输出路径（可选，保存组合NAV）", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        out_frame_combo = ttk.Frame(combo_frame)
        out_frame_combo.grid(row=row, column=0, sticky=(tk.W, tk.E))
        self.combo_out_var = tk.StringVar(value="./combo_nav.csv")
        ttk.Entry(out_frame_combo, textvariable=self.combo_out_var, width=40).pack(side=tk.LEFT, padx=4)
        ttk.Button(out_frame_combo, text="选择路径", command=self._browse_combo_out).pack(side=tk.LEFT, padx=4)

    def create_data_download_tab(self):
        """数据下载标签页"""
        data_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(data_frame, text="📥 数据下载")
        
        row = 0
        
        ttk.Label(data_frame, text="批量下载股票数据", style='Title.TLabel').grid(
            row=row, column=0, columnspan=2, pady=10
        )
        row += 1
        
        # 股票代码
        ttk.Label(data_frame, text="股票代码 (多个用空格或换行分隔):", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.download_symbols_text = tk.Text(data_frame, height=8, width=50)
        self.download_symbols_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.download_symbols_text.insert('1.0', '600519.SH\n000858.SZ\n600036.SH\n000333.SZ')
        row += 1
        
        # 日期范围
        ttk.Label(data_frame, text="日期范围:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        date_frame = ttk.Frame(data_frame)
        date_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(date_frame, text="开始:").pack(side=tk.LEFT)
        self.download_start_var = tk.StringVar(value="2020-01-01")
        ttk.Entry(date_frame, textvariable=self.download_start_var, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(date_frame, text="结束:").pack(side=tk.LEFT)
        self.download_end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.download_end_var, width=15).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 数据源
        ttk.Label(data_frame, text="数据源:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.download_source_var = tk.StringVar(value="akshare")
        ttk.Combobox(
            data_frame,
            textvariable=self.download_source_var,
            values=sorted(PROVIDER_NAMES),
            state="readonly",
            width=48
        ).grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 复权方式
        ttk.Label(data_frame, text="复权方式:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        self.download_adj_var = tk.StringVar(value="qfq")
        adj_frame = ttk.Frame(data_frame)
        adj_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Radiobutton(adj_frame, text="前复权 (qfq)", variable=self.download_adj_var, value="qfq").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(adj_frame, text="后复权 (hfq)", variable=self.download_adj_var, value="hfq").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(adj_frame, text="不复权 (noadj)", variable=self.download_adj_var, value="noadj").pack(side=tk.LEFT, padx=10)
        row += 1
        
        # 缓存目录
        ttk.Label(data_frame, text="缓存目录:", style='Section.TLabel').grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        row += 1
        
        cache_frame = ttk.Frame(data_frame)
        cache_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.download_cache_var = tk.StringVar(value="./cache")
        ttk.Entry(cache_frame, textvariable=self.download_cache_var, width=38).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(cache_frame, text="浏览", command=self.browse_cache_dir).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 下载按钮
        ttk.Button(
            data_frame,
            text="🚀 开始下载",
            command=self.start_download,
            style='Run.TButton'
        ).grid(row=row, column=0, columnspan=2, pady=20)
    
    def create_list_tab(self):
        """LIST命令标签页：策略列表"""
        list_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(list_frame, text="📋 策略列表 (list)")
        
        ttk.Label(list_frame, text="可用策略列表", style='Title.TLabel').pack(pady=10)
        
        # 创建滚动文本区域显示策略列表
        strategies_text = scrolledtext.ScrolledText(
            list_frame,
            wrap=tk.WORD,
            width=60,
            height=30,
            font=('Consolas', 9)
        )
        strategies_text.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 填充策略信息
        strategies_text.insert('1.0', "策略注册表 (STRATEGY_REGISTRY)\n")
        strategies_text.insert('end', "=" * 60 + "\n\n")
        
        for name, module in sorted(STRATEGY_REGISTRY.items()):
            strategies_text.insert('end', f"策略名称: {name}\n")
            strategies_text.insert('end', f"描述: {module.description}\n")
            strategies_text.insert('end', f"参数: {list(module.grid_defaults.keys())}\n")
            strategies_text.insert('end', f"默认网格: {module.grid_defaults}\n")
            strategies_text.insert('end', "-" * 60 + "\n\n")
        
        strategies_text.config(state=tk.DISABLED)
        
        # 刷新按钮
        ttk.Button(
            list_frame,
            text="🔄 刷新策略列表",
            command=lambda: self.log_output("策略列表已是最新")
        ).pack(pady=5)
    
    def create_output_area(self, parent):
        """创建输出区域"""
        output_frame = ttk.LabelFrame(parent, text="执行输出", padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 输出文本区域
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            width=80,
            height=40,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#d4d4d4'
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # 清空按钮
        ttk.Button(
            output_frame,
            text="清空输出",
            command=self.clear_output
        ).pack(pady=5)
    
    def create_control_buttons(self, parent):
        """创建控制按钮"""
        button_frame = ttk.Frame(parent, padding=10)
        button_frame.pack(fill=tk.X, pady=5)
        
        # 运行按钮
        self.run_button = ttk.Button(
            button_frame,
            text="▶ 运行",
            command=self.run_backtest,
            style='Run.TButton'
        )
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        # 停止按钮
        self.stop_button = ttk.Button(
            button_frame,
            text="⬛ 停止",
            command=self.stop_backtest,
            style='Stop.TButton',
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 保存配置按钮
        ttk.Button(
            button_frame,
            text="💾 保存配置",
            command=self.save_config
        ).pack(side=tk.LEFT, padx=5)
        
        # 加载配置按钮
        ttk.Button(
            button_frame,
            text="📂 加载配置",
            command=self.load_config
        ).pack(side=tk.LEFT, padx=5)
    
    # ========== 辅助方法 ==========
    
    def load_default_config(self):
        """加载默认配置"""
        self.log_output("系统已就绪，请选择功能标签页开始回测")
        self.log_output(f"支持的CLI命令: run, grid, auto, list")
        self.log_output(f"可用数据源: {', '.join(sorted(PROVIDER_NAMES))}")
        self.log_output(f"可用策略数: {len(STRATEGY_REGISTRY)}\n")
    
    def log_output(self, message):
        """输出日志（写入队列，避免阻塞UI线程）"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def _poll_log_queue(self):
        """定时从队列刷新日志，避免跨线程直接操作Tk组件"""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_buffer.append(msg)
        except Empty:
            pass

        if self.log_buffer:
            batch = "\n".join(self.log_buffer) + "\n"
            self.log_buffer.clear()
            self.output_text.insert('end', batch)
            # 裁剪日志行数，防止 UI 卡顿
            lines = self.output_text.get('1.0', 'end').splitlines()
            if len(lines) > self.max_log_lines:
                keep = "\n".join(lines[-self.max_log_lines :]) + "\n"
                self.output_text.delete('1.0', 'end')
                self.output_text.insert('end', keep)
            self.output_text.see('end')

        self.root.after(self.log_poll_ms, self._poll_log_queue)
    
    def clear_output(self):
        """清空输出"""
        self.output_text.delete('1.0', 'end')
    
    def show_strategy_info(self):
        """显示策略信息"""
        strategy = self.run_strategy_var.get()
        if strategy in STRATEGY_REGISTRY:
            module = STRATEGY_REGISTRY[strategy]
            info = f"策略: {strategy}\n\n"
            info += f"描述: {module.description}\n\n"
            info += f"默认参数网格:\n{json.dumps(module.grid_defaults, indent=2, ensure_ascii=False)}"
            messagebox.showinfo("策略信息", info)
    
    def browse_out_dir_run(self):
        """浏览输出目录 (run)"""
        directory = filedialog.askdirectory()
        if directory:
            self.run_out_dir_var.set(directory)
    
    def browse_out_csv_grid(self):
        """浏览输出CSV (grid)"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.grid_out_csv_var.set(filename)
    
    def browse_out_dir_auto(self):
        """浏览输出目录 (auto)"""
        directory = filedialog.askdirectory()
        if directory:
            self.auto_out_dir_var.set(directory)

    def _browse_nav_files(self):
        """选择 NAV CSV 文件并填充文本框"""
        filenames = filedialog.askopenfilenames(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filenames:
            existing = self.combo_navs_text.get("1.0", "end").strip().split()
            merged = list(existing) + list(filenames)
            self.combo_navs_text.delete("1.0", "end")
            self.combo_navs_text.insert("1.0", "\n".join(merged))

    def _browse_combo_out(self):
        """选择组合NAV输出路径"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.combo_out_var.set(filename)
    
    def browse_cache_dir(self):
        """浏览缓存目录"""
        directory = filedialog.askdirectory()
        if directory:
            self.download_cache_var.set(directory)
    
    def load_preset_auto(self, event=None):
        """加载预设配置 (auto)"""
        preset_name = self.auto_preset_var.get()
        if preset_name and preset_name in self.PRESET_CONFIGS:
            config = self.PRESET_CONFIGS[preset_name]
            
            # 加载股票代码
            symbols = ' '.join(config.get('symbols', []))
            self.auto_symbols_text.delete('1.0', 'end')
            self.auto_symbols_text.insert('1.0', symbols)
            
            # 加载策略
            strategies = config.get('strategies', [])
            self.auto_strategies_listbox.selection_clear(0, tk.END)
            all_strategies = self.strategy_choices
            for strategy in strategies:
                if strategy in all_strategies:
                    idx = all_strategies.index(strategy)
                    self.auto_strategies_listbox.selection_set(idx)
            
            # 加载日期
            self.auto_start_var.set(config.get('start_date', '2022-01-01'))
            
            # 加载其他选项
            self.auto_hot_only_var.set(config.get('hot_only', True))
            self.auto_use_regime_var.set(config.get('use_benchmark_regime', False))
            
            self.log_output(f"已加载预设配置: {preset_name}")
            self.log_output(f"  {config.get('description', '')}")
    
    def save_config(self):
        """保存配置到JSON文件"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            # TODO: 实现配置保存
            self.log_output(f"配置已保存: {filename}")
    
    def load_config(self):
        """从JSON文件加载配置"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            # TODO: 实现配置加载
            self.log_output(f"配置已加载: {filename}")
    
    # ========== 主要功能方法 ==========
    
    def run_backtest(self):
        """运行回测（根据当前标签页）"""
        if self.running:
            messagebox.showwarning("警告", "已有任务在运行中")
            return
        
        current_tab = self.notebook.tab(self.notebook.select(), "text")
        
        if "单策略回测" in current_tab:
            self.run_command_run()
        elif "网格搜索" in current_tab:
            self.run_command_grid()
        elif "自动优化" in current_tab:
            self.run_command_auto()
        elif "组合优化" in current_tab:
            self.run_command_combo()
        else:
            messagebox.showinfo("提示", "请切换到对应的功能标签页")
    
    def run_command_run(self):
        """执行 RUN 命令"""
        try:
            symbols = self.run_symbols_text.get('1.0', 'end').strip().split()
            if not symbols:
                messagebox.showwarning("警告", "请输入至少一个股票代码")
                return
            run_cfg = RunConfig(
                strategy=self.run_strategy_var.get(),
                symbols=symbols,
                start=self.run_start_var.get(),
                end=self.run_end_var.get(),
                source=self.run_source_var.get(),
                benchmark=self.run_benchmark_var.get() or None,
                benchmark_source=self.run_benchmark_source_var.get() or None,
                params_json=self.run_params_text.get('1.0', 'end'),
                cash=self.run_cash_var.get(),
                commission=self.run_commission_var.get(),
                slippage=self.run_slippage_var.get(),
                adj=self.run_adj_var.get() or None,
                out_dir=self.run_out_dir_var.get() or None,
                cache_dir=self.run_cache_dir_var.get(),
                plot=self.run_plot_var.get(),
                fee_config=self.run_fee_config_var.get() or None,
                fee_params=self.run_fee_params_var.get() or None,
            )
            cmd = CommandBuilder.build_run(run_cfg)
            self.execute_command(cmd)
            
        except Exception as e:
            messagebox.showerror("错误", f"构建命令失败: {str(e)}")
    
    def run_command_grid(self):
        """执行 GRID 命令"""
        try:
            symbols = self.grid_symbols_text.get('1.0', 'end').strip().split()
            if not symbols:
                messagebox.showwarning("警告", "请输入至少一个股票代码")
                return

            grid_cfg = GridConfig(
                strategy=self.grid_strategy_var.get(),
                symbols=symbols,
                start=self.grid_start_var.get(),
                end=self.grid_end_var.get(),
                source=self.grid_source_var.get(),
                benchmark=self.grid_benchmark_var.get() or None,
                benchmark_source=self.grid_benchmark_source_var.get() or None,
                grid_json=self.grid_params_text.get('1.0', 'end'),
                cash=self.grid_cash_var.get(),
                commission=self.grid_commission_var.get(),
                slippage=self.grid_slippage_var.get(),
                adj=self.grid_adj_var.get() or None,
                cache_dir=self.grid_cache_dir_var.get(),
                out_csv=self.grid_out_csv_var.get() or None,
                workers=self.grid_workers_var.get(),
                fee_config=self.grid_fee_config_var.get() or None,
                fee_params=self.grid_fee_params_var.get() or None,
            )
            cmd = CommandBuilder.build_grid(grid_cfg)
            self.execute_command(cmd)
            
        except Exception as e:
            messagebox.showerror("错误", f"构建命令失败: {str(e)}")
    
    def run_command_auto(self):
        """执行 AUTO 命令"""
        try:
            symbols = self.auto_symbols_text.get('1.0', 'end').strip().split()
            if not symbols:
                messagebox.showwarning("警告", "请输入至少一个股票代码")
                return

            selected_indices = self.auto_strategies_listbox.curselection()
            strategies = [self.auto_strategies_listbox.get(i) for i in selected_indices] if selected_indices else None

            auto_cfg = AutoConfig(
                symbols=symbols,
                start=self.auto_start_var.get(),
                end=self.auto_end_var.get(),
                source=self.auto_source_var.get(),
                benchmark=self.auto_benchmark_var.get(),
                benchmark_source=self.auto_benchmark_source_var.get() or None,
                strategies=strategies,
                top_n=self.auto_top_n_var.get(),
                min_trades=self.auto_min_trades_var.get(),
                cash=self.auto_cash_var.get(),
                commission=self.auto_commission_var.get(),
                slippage=self.auto_slippage_var.get(),
                adj=self.auto_adj_var.get() or None,
                cache_dir=self.auto_cache_dir_var.get(),
                out_dir=self.auto_out_dir_var.get(),
                workers=self.auto_workers_var.get(),
                hot_only=self.auto_hot_only_var.get(),
                use_benchmark_regime=self.auto_use_regime_var.get(),
                regime_scope=self.auto_regime_scope_var.get(),
            )

            cmd = CommandBuilder.build_auto(auto_cfg)
            self.execute_command(cmd)
            
        except Exception as e:
            messagebox.showerror("错误", f"构建命令失败: {str(e)}")

    def run_command_combo(self):
        """执行 COMBO 命令"""
        try:
            navs = [s for s in self.combo_navs_text.get("1.0", "end").split() if s.strip()]
            if not navs:
                messagebox.showwarning("警告", "请至少选择一个NAV文件")
                return
            combo_cfg = ComboConfig(
                navs=navs,
                objective=self.combo_objective_var.get(),
                step=self.combo_step_var.get(),
                allow_short=self.combo_allow_short_var.get(),
                max_weight=self.combo_max_weight_var.get(),
                risk_free=self.combo_risk_free_var.get(),
                out=self.combo_out_var.get() or None,
            )
            cmd = CommandBuilder.build_combo(combo_cfg)
            self.execute_command(cmd)
        except Exception as e:
            messagebox.showerror("错误", f"组合优化命令失败: {str(e)}")
    
    def execute_command(self, cmd):
        """在后台线程执行命令"""
        self.running = True
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 显示命令
        self.log_output("\n" + "="*80)
        self.log_output(f"执行命令: {' '.join(cmd)}")
        self.log_output("="*80 + "\n")
        
        # 在后台线程执行
        thread = threading.Thread(target=self._run_subprocess, args=(cmd,))
        thread.daemon = True
        thread.start()
    
    def _run_subprocess(self, cmd):
        """运行子进程"""
        try:
            # 运行命令
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                cwd=project_root,
            )
            
            # 读取输出
            for line in self.process.stdout:
                self.log_output(line.rstrip())
            
            # 等待完成
            self.process.wait()
            
            if self.process.returncode == 0:
                self.log_output("\n✅ 任务完成！")
            else:
                self.log_output(f"\n❌ 任务失败，退出码: {self.process.returncode}")
            
        except Exception as e:
            self.log_output(f"\n❌ 执行出错: {str(e)}")
        
        finally:
            self.running = False
            self.process = None
            self.root.after(0, self._reset_buttons)
    
    def _reset_buttons(self):
        """重置按钮状态"""
        self.run_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def stop_backtest(self):
        """停止回测"""
        if self.process:
            self.process.terminate()
            self.log_output("\n⚠️ 用户中止任务")
            self.running = False
            self.process = None
            self._reset_buttons()
    
    def start_download(self):
        """开始数据下载"""
        if self.running:
            messagebox.showwarning("警告", "已有任务在运行中")
            return
        
        try:
            # 获取股票代码列表
            symbols_text = self.download_symbols_text.get('1.0', 'end').strip()
            symbols = [s.strip() for s in symbols_text.replace('\n', ' ').split() if s.strip()]
            
            if not symbols:
                messagebox.showwarning("警告", "请输入至少一个股票代码")
                return
            
            # 构建下载脚本命令（使用providers下载功能）
            cmd = [
                sys.executable, "-c",
                f"""
import sys
sys.path.insert(0, '{project_root}')
from src.data_sources.providers import get_provider

provider = get_provider(
    '{self.download_source_var.get()}',
    cache_dir='{self.download_cache_var.get()}'
)

symbols = {symbols}
start = '{self.download_start_var.get()}'
end = '{self.download_end_var.get()}'
adj = '{self.download_adj_var.get()}'

print(f"开始下载 {{len(symbols)}} 个股票的数据...")
for i, symbol in enumerate(symbols, 1):
    print(f"[{{i}}/{{len(symbols)}}] 下载 {{symbol}}...")
    try:
        df = provider.fetch(symbol, start, end, adj=adj)
        print(f"  ✓ 成功: {{len(df)}} 条记录")
    except Exception as e:
        print(f"  ✗ 失败: {{e}}")

print("\\n下载完成！")
"""
            ]
            
            # 执行命令
            self.execute_command(cmd)
            
        except Exception as e:
            messagebox.showerror("错误", f"启动下载失败: {str(e)}")


def main():
    """主函数"""
    root = tk.Tk()
    app = BacktestGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
