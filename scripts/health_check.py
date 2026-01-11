#!/usr/bin/env python3
"""
系统健康检查脚本

用于监控系统运行状态，检查关键组件是否正常。
适用于生产环境监控和自动化运维。

用法:
    python scripts/health_check.py
    python scripts/health_check.py --json  # JSON格式输出
    python scripts/health_check.py --exit-code  # 返回退出码（0=健康，1=不健康）
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.logger import get_logger
from src.core.defaults import PATHS
from src.data_sources.db_manager import SQLiteDataManager

logger = get_logger("health_check")


class HealthChecker:
    """系统健康检查器"""
    
    def __init__(self):
        self.checks: List[Dict[str, Any]] = []
        self.overall_status = "healthy"
    
    def check(self, name: str, status: bool, message: str = "", details: Dict[str, Any] = None):
        """记录检查结果"""
        check_result = {
            "name": name,
            "status": "pass" if status else "fail",
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.checks.append(check_result)
        
        if not status:
            self.overall_status = "unhealthy"
        
        return status
    
    def check_directories(self) -> bool:
        """检查必要目录是否存在"""
        required_dirs = [
            ("cache", PATHS["cache"]),
            ("logs", PATHS["logs"]),
            ("reports", PATHS["reports"]),
        ]
        
        all_exist = True
        missing = []
        
        for name, path in required_dirs:
            exists = os.path.exists(path)
            if not exists:
                missing.append(name)
                all_exist = False
        
        return self.check(
            "directories",
            all_exist,
            f"Required directories exist" if all_exist else f"Missing directories: {', '.join(missing)}",
            {"missing": missing}
        )
    
    def check_database(self) -> bool:
        """检查数据库连接和完整性"""
        try:
            db_path = PATHS["database"]
            
            # 检查数据库文件是否存在
            if not os.path.exists(db_path):
                return self.check(
                    "database",
                    False,
                    f"Database file not found: {db_path}",
                    {"path": db_path}
                )
            
            # 检查数据库连接
            db = SQLiteDataManager(db_path)
            
            # 检查元数据表
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM metadata")
                count = cursor.fetchone()[0]
            
            return self.check(
                "database",
                True,
                f"Database accessible with {count} symbols",
                {
                    "path": db_path,
                    "size_mb": round(os.path.getsize(db_path) / 1024 / 1024, 2),
                    "symbol_count": count
                }
            )
        except Exception as e:
            return self.check(
                "database",
                False,
                f"Database check failed: {str(e)}",
                {"error": str(e)}
            )
    
    def check_dependencies(self) -> bool:
        """检查关键依赖包"""
        required_packages = [
            "pandas",
            "numpy",
            "backtrader",
            "akshare",
            "matplotlib",
        ]
        
        missing = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        return self.check(
            "dependencies",
            len(missing) == 0,
            f"All dependencies available" if len(missing) == 0 else f"Missing packages: {', '.join(missing)}",
            {"missing": missing}
        )
    
    def check_data_providers(self) -> bool:
        """检查数据源可用性"""
        try:
            from src.data_sources.providers import get_provider
            
            providers_status = {}
            all_available = True
            
            for provider_name in ["akshare", "yfinance"]:
                try:
                    provider = get_provider(provider_name)
                    providers_status[provider_name] = "available"
                except Exception as e:
                    providers_status[provider_name] = f"unavailable: {str(e)}"
                    all_available = False
            
            return self.check(
                "data_providers",
                all_available,
                "Data providers available" if all_available else "Some data providers unavailable",
                providers_status
            )
        except Exception as e:
            return self.check(
                "data_providers",
                False,
                f"Failed to check data providers: {str(e)}",
                {"error": str(e)}
            )
    
    def check_disk_space(self) -> bool:
        """检查磁盘空间"""
        try:
            import shutil
            
            cache_dir = PATHS["cache"]
            if os.path.exists(cache_dir):
                stat = shutil.disk_usage(cache_dir)
                free_gb = stat.free / (1024 ** 3)
                total_gb = stat.total / (1024 ** 3)
                free_pct = (stat.free / stat.total) * 100
                
                # 警告阈值：小于1GB或小于10%
                healthy = free_gb >= 1.0 and free_pct >= 10.0
                
                return self.check(
                    "disk_space",
                    healthy,
                    f"Free space: {free_gb:.2f} GB ({free_pct:.1f}%)" if healthy else f"Low disk space: {free_gb:.2f} GB ({free_pct:.1f}%)",
                    {
                        "free_gb": round(free_gb, 2),
                        "total_gb": round(total_gb, 2),
                        "free_percent": round(free_pct, 1)
                    }
                )
            else:
                return self.check(
                    "disk_space",
                    True,
                    "Cache directory not found, skipping disk space check",
                    {}
                )
        except Exception as e:
            return self.check(
                "disk_space",
                False,
                f"Failed to check disk space: {str(e)}",
                {"error": str(e)}
            )
    
    def check_log_files(self) -> bool:
        """检查日志文件可写性"""
        try:
            log_dir = PATHS["logs"]
            os.makedirs(log_dir, exist_ok=True)
            
            test_file = os.path.join(log_dir, ".health_check_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                writable = True
            except Exception:
                writable = False
            
            return self.check(
                "log_files",
                writable,
                "Log directory writable" if writable else "Log directory not writable",
                {"log_dir": log_dir}
            )
        except Exception as e:
            return self.check(
                "log_files",
                False,
                f"Failed to check log files: {str(e)}",
                {"error": str(e)}
            )
    
    def run_all_checks(self):
        """运行所有检查"""
        logger.info("Starting health checks...")
        
        self.check_directories()
        self.check_database()
        self.check_dependencies()
        self.check_data_providers()
        self.check_disk_space()
        self.check_log_files()
        
        logger.info(f"Health checks completed. Status: {self.overall_status}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "status": self.overall_status,
            "timestamp": datetime.now().isoformat(),
            "checks": self.checks,
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for c in self.checks if c["status"] == "pass"),
                "failed": sum(1 for c in self.checks if c["status"] == "fail")
            }
        }
    
    def print_report(self, json_format: bool = False):
        """打印检查报告"""
        if json_format:
            print(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("\n" + "=" * 60)
            print("系统健康检查报告")
            print("=" * 60)
            print(f"总体状态: {self.overall_status.upper()}")
            print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            for check in self.checks:
                status_icon = "✓" if check["status"] == "pass" else "✗"
                status_text = "通过" if check["status"] == "pass" else "失败"
                print(f"{status_icon} [{status_text}] {check['name']}")
                if check["message"]:
                    print(f"    {check['message']}")
                if check["details"]:
                    for key, value in check["details"].items():
                        print(f"    {key}: {value}")
                print()
            
            summary = self.to_dict()["summary"]
            print(f"总计: {summary['total']} | 通过: {summary['passed']} | 失败: {summary['failed']}")
            print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="系统健康检查")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    parser.add_argument("--exit-code", action="store_true", help="返回退出码（0=健康，1=不健康）")
    
    args = parser.parse_args()
    
    checker = HealthChecker()
    checker.run_all_checks()
    checker.print_report(json_format=args.json)
    
    if args.exit_code:
        sys.exit(0 if checker.overall_status == "healthy" else 1)


if __name__ == "__main__":
    main()
