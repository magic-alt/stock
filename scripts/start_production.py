#!/usr/bin/env python3
"""
生产环境启动脚本

提供完整的生产环境启动流程，包括：
- 配置加载和验证
- 目录初始化
- 日志配置
- 健康检查
- 优雅关闭处理

用法:
    python scripts/start_production.py
    python scripts/start_production.py --config config.yaml
    python scripts/start_production.py --mode backtest
"""
from __future__ import annotations

import argparse
import signal
import sys
import os
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.logger import configure_logging, get_logger
from src.core.config import ConfigManager, get_config
from src.core.defaults import ensure_directories, PATHS
from scripts.health_check import HealthChecker

logger = None


def setup_signal_handlers():
    """设置信号处理器，实现优雅关闭"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)


def load_configuration(config_path: Optional[str] = None) -> ConfigManager:
    """加载配置"""
    if config_path and os.path.exists(config_path):
        logger.info(f"Loading configuration from {config_path}")
        return ConfigManager.load_from_file(config_path)
    else:
        logger.info("Using default configuration")
        return ConfigManager()


def initialize_directories():
    """初始化必要目录"""
    logger.info("Initializing directories...")
    ensure_directories()
    
    for name, path in PATHS.items():
        if name not in ["database", "config"]:
            logger.debug(f"  {name}: {path}")


def run_health_check() -> bool:
    """运行健康检查"""
    logger.info("Running health checks...")
    checker = HealthChecker()
    checker.run_all_checks()
    
    if checker.overall_status == "healthy":
        logger.info("✓ All health checks passed")
        return True
    else:
        logger.warning("✗ Some health checks failed")
        failed_checks = [c for c in checker.checks if c["status"] == "fail"]
        for check in failed_checks:
            logger.warning(f"  Failed: {check['name']} - {check['message']}")
        return False


def start_backtest_mode(config: ConfigManager):
    """启动回测模式"""
    logger.info("Starting in BACKTEST mode...")
    # 这里可以启动回测服务或CLI
    logger.info("Backtest mode ready. Use CLI commands to run backtests.")


def start_paper_trading_mode(config: ConfigManager):
    """启动模拟交易模式"""
    logger.info("Starting in PAPER TRADING mode...")
    # 这里可以启动模拟交易服务
    logger.info("Paper trading mode ready.")


def start_live_trading_mode(config: ConfigManager):
    """启动实盘交易模式"""
    logger.warning("Starting in LIVE TRADING mode...")
    logger.warning("⚠️  WARNING: This will execute real trades!")
    
    # 确认实盘模式
    if not os.getenv("CONFIRM_LIVE_TRADING"):
        logger.error("LIVE TRADING mode requires CONFIRM_LIVE_TRADING environment variable")
        sys.exit(1)
    
    # 这里可以启动实盘交易服务
    logger.info("Live trading mode ready.")


def main():
    global logger
    
    parser = argparse.ArgumentParser(description="生产环境启动脚本")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--mode", choices=["backtest", "paper", "live"], default="backtest",
                       help="运行模式")
    parser.add_argument("--skip-health-check", action="store_true",
                       help="跳过健康检查")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 初始化日志（早期，使用默认配置）
    configure_logging(level=args.log_level)
    logger = get_logger("startup")
    
    logger.info("=" * 60)
    logger.info("量化交易系统 - 生产环境启动")
    logger.info("=" * 60)
    
    try:
        # 加载配置
        config = load_configuration(args.config)
        
        # 重新配置日志（使用配置文件中的设置）
        log_config = config.logging
        configure_logging(
            level=log_config.level,
            json_format=log_config.format == "json",
            log_file=log_config.file
        )
        logger = get_logger("startup")
        
        # 初始化目录
        initialize_directories()
        
        # 健康检查
        if not args.skip_health_check:
            if not run_health_check():
                logger.error("Health checks failed. Exiting.")
                sys.exit(1)
        else:
            logger.warning("Skipping health checks (--skip-health-check)")
        
        # 设置信号处理
        setup_signal_handlers()
        
        # 根据模式启动
        if args.mode == "backtest":
            start_backtest_mode(config)
        elif args.mode == "paper":
            start_paper_trading_mode(config)
        elif args.mode == "live":
            start_live_trading_mode(config)
        
        logger.info("System started successfully")
        logger.info("Press Ctrl+C to stop")
        
        # 保持运行（实际应用中可能是事件循环）
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
    
    except Exception as e:
        logger.exception("Failed to start system")
        sys.exit(1)


if __name__ == "__main__":
    main()
