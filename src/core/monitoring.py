"""
系统监控模块

提供系统状态监控、性能指标收集和告警功能。
适用于生产环境监控和运维。
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from threading import Thread, Event

# Optional dependency: psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from src.core.logger import get_logger

logger = get_logger("monitoring")


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    active_connections: int = 0
    database_size_mb: float = 0.0


@dataclass
class Alert:
    """告警信息"""
    level: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class SystemMonitor:
    """系统监控器"""
    
    def __init__(
        self,
        check_interval: float = 60.0,
        alert_thresholds: Optional[Dict[str, float]] = None
    ):
        """
        初始化系统监控器
        
        Args:
            check_interval: 检查间隔（秒）
            alert_thresholds: 告警阈值配置
        """
        self.check_interval = check_interval
        self.alert_thresholds = alert_thresholds or {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
        }
        
        self.metrics_history: List[SystemMetrics] = []
        self.alerts: List[Alert] = []
        self._running = False
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        
        # 数据库路径
        from src.core.defaults import PATHS
        self.db_path = PATHS.get("database", "./cache/market_data.db")
    
    def collect_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        timestamp = datetime.now()
        
        if not PSUTIL_AVAILABLE:
            # Fallback: 返回默认值
            logger.warning("psutil not available, using default metrics")
            return SystemMetrics(
                timestamp=timestamp,
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                active_connections=0,
                database_size_mb=0.0
            )
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / 1024 / 1024
        memory_available_mb = memory.available / 1024 / 1024
        
        # 磁盘使用
        try:
            disk = psutil.disk_usage("/")
        except Exception:
            # Windows可能使用不同路径
            disk = psutil.disk_usage(os.path.expanduser("~"))
        disk_usage_percent = disk.percent
        disk_free_gb = disk.free / 1024 / 1024 / 1024
        
        # 数据库大小
        database_size_mb = 0.0
        if os.path.exists(self.db_path):
            database_size_mb = os.path.getsize(self.db_path) / 1024 / 1024
        
        # 活跃连接数（简化实现）
        active_connections = 0
        
        return SystemMetrics(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            disk_free_gb=disk_free_gb,
            active_connections=active_connections,
            database_size_mb=database_size_mb
        )
    
    def check_thresholds(self, metrics: SystemMetrics) -> List[Alert]:
        """检查告警阈值"""
        alerts = []
        
        # CPU告警
        if metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
            alerts.append(Alert(
                level="WARNING" if metrics.cpu_percent < 95 else "CRITICAL",
                message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                timestamp=metrics.timestamp,
                details={"cpu_percent": metrics.cpu_percent}
            ))
        
        # 内存告警
        if metrics.memory_percent > self.alert_thresholds["memory_percent"]:
            alerts.append(Alert(
                level="WARNING" if metrics.memory_percent < 95 else "CRITICAL",
                message=f"High memory usage: {metrics.memory_percent:.1f}%",
                timestamp=metrics.timestamp,
                details={
                    "memory_percent": metrics.memory_percent,
                    "memory_used_mb": metrics.memory_used_mb
                }
            ))
        
        # 磁盘告警
        if metrics.disk_usage_percent > self.alert_thresholds["disk_percent"]:
            alerts.append(Alert(
                level="WARNING" if metrics.disk_usage_percent < 95 else "CRITICAL",
                message=f"Low disk space: {metrics.disk_usage_percent:.1f}% used, {metrics.disk_free_gb:.2f} GB free",
                timestamp=metrics.timestamp,
                details={
                    "disk_usage_percent": metrics.disk_usage_percent,
                    "disk_free_gb": metrics.disk_free_gb
                }
            ))
        
        return alerts
    
    def start(self):
        """启动监控"""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"System monitor started (interval: {self.check_interval}s)")
    
    def stop(self):
        """停止监控"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("System monitor stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 收集指标
                metrics = self.collect_metrics()
                self.metrics_history.append(metrics)
                
                # 保留最近100条记录
                if len(self.metrics_history) > 100:
                    self.metrics_history.pop(0)
                
                # 检查告警
                alerts = self.check_thresholds(metrics)
                for alert in alerts:
                    self.alerts.append(alert)
                    self._handle_alert(alert)
                
                # 等待下次检查
                self._stop_event.wait(self.check_interval)
            
            except Exception as e:
                logger.error(f"Monitor loop error: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def _handle_alert(self, alert: Alert):
        """处理告警"""
        if alert.level == "CRITICAL":
            logger.critical(f"🚨 {alert.message}", **alert.details)
        elif alert.level == "ERROR":
            logger.error(f"⚠️  {alert.message}", **alert.details)
        elif alert.level == "WARNING":
            logger.warning(f"⚠️  {alert.message}", **alert.details)
        else:
            logger.info(f"ℹ️  {alert.message}", **alert.details)
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """获取当前指标"""
        if not self.metrics_history:
            return None
        return self.metrics_history[-1]
    
    def get_recent_alerts(self, count: int = 10) -> List[Alert]:
        """获取最近的告警"""
        return self.alerts[-count:] if len(self.alerts) > count else self.alerts
    
    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest = self.metrics_history[-1]
        recent_alerts = [a for a in self.alerts if (latest.timestamp - a.timestamp).total_seconds() < 3600]
        
        return {
            "status": "healthy" if not recent_alerts else "warning",
            "latest_metrics": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "disk_usage_percent": latest.disk_usage_percent,
                "database_size_mb": latest.database_size_mb
            },
            "recent_alerts_count": len(recent_alerts),
            "monitoring_active": self._running
        }


# 全局监控实例
_global_monitor: Optional[SystemMonitor] = None


def get_monitor() -> SystemMonitor:
    """获取全局监控实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SystemMonitor()
    return _global_monitor


def start_monitoring(check_interval: float = 60.0):
    """启动系统监控"""
    monitor = get_monitor()
    monitor.check_interval = check_interval
    monitor.start()


def stop_monitoring():
    """停止系统监控"""
    monitor = get_monitor()
    monitor.stop()
