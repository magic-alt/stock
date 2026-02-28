"""
系统监控模块

提供系统状态监控、性能指标收集和告警功能。
适用于生产环境监控和运维。
"""
from __future__ import annotations

import os
import time
import inspect
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from threading import Thread, Event as ThreadEvent

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
        self._stop_event = ThreadEvent()

        # External alert dispatcher (configure via set_alert_dispatcher)
        self._alert_dispatcher: Optional[AlertDispatcher] = None
        
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
    
    def set_alert_dispatcher(self, dispatcher: "AlertDispatcher") -> None:
        """Attach external alert dispatcher for email/webhook delivery."""
        self._alert_dispatcher = dispatcher

    def _handle_alert(self, alert: Alert):
        """处理告警 — log locally and dispatch to external channels."""
        if alert.level == "CRITICAL":
            logger.critical(f"{alert.message}", **alert.details)
        elif alert.level == "ERROR":
            logger.error(f"{alert.message}", **alert.details)
        elif alert.level == "WARNING":
            logger.warning(f"{alert.message}", **alert.details)
        else:
            logger.info(f"{alert.message}", **alert.details)

        if self._alert_dispatcher:
            self._alert_dispatcher.dispatch(alert)
    
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


# ---------------------------------------------------------------------------
# External alert channels (email / WeCom / DingTalk webhook)
# ---------------------------------------------------------------------------

class AlertChannel:
    """Base class for external alert delivery."""

    def send(self, alert: Alert) -> bool:
        raise NotImplementedError


class WebhookAlertChannel(AlertChannel):
    """Send alerts to a generic JSON webhook (WeCom / DingTalk / custom)."""

    def __init__(self, url: str, *, secret: Optional[str] = None, platform: str = "generic"):
        self.url = url
        self.secret = secret
        self.platform = platform

    def _build_payload(self, alert: Alert) -> Dict[str, Any]:
        text = f"[{alert.level}] {alert.message}"
        if self.platform == "wecom":
            return {"msgtype": "text", "text": {"content": text}}
        if self.platform == "dingtalk":
            return {"msgtype": "text", "text": {"content": text}}
        return {"level": alert.level, "message": alert.message, "timestamp": alert.timestamp.isoformat(), "details": alert.details}

    def send(self, alert: Alert) -> bool:
        import json
        try:
            import urllib.request
            payload = json.dumps(self._build_payload(alert), ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception as exc:
            logger.error("webhook_alert_failed", url=self.url, error=str(exc))
            return False


class EmailAlertChannel(AlertChannel):
    """Send alerts via SMTP email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 465,
        username: str = "",
        password: str = "",
        sender: str = "",
        recipients: Optional[List[str]] = None,
        use_ssl: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender or username
        self.recipients = recipients or []
        self.use_ssl = use_ssl

    def send(self, alert: Alert) -> bool:
        import smtplib
        from email.mime.text import MIMEText
        try:
            subject = f"[{alert.level}] Platform Alert"
            body = f"{alert.message}\n\nTimestamp: {alert.timestamp.isoformat()}\nDetails: {alert.details}"
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)

            if self.use_ssl:
                smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15)
            else:
                smtp = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.sendmail(self.sender, self.recipients, msg.as_string())
            smtp.quit()
            return True
        except Exception as exc:
            logger.error("email_alert_failed", host=self.smtp_host, error=str(exc))
            return False


class AlertDispatcher:
    """Dispatch alerts to multiple external channels based on level filter."""

    def __init__(self) -> None:
        self._channels: List[tuple[AlertChannel, Optional[set]]] = []

    def add_channel(self, channel: AlertChannel, levels: Optional[set] = None) -> None:
        """Register a channel. ``levels`` filters which alert levels are sent (None = all)."""
        self._channels.append((channel, levels))

    def dispatch(self, alert: Alert) -> int:
        """Send alert to all matching channels. Returns number of successful deliveries."""
        sent = 0
        for ch, levels in self._channels:
            if levels and alert.level not in levels:
                continue
            try:
                if ch.send(alert):
                    sent += 1
            except Exception as exc:
                logger.error("alert_dispatch_error", channel=type(ch).__name__, error=str(exc))
        return sent


# ---------------------------------------------------------------------------
# Heartbeat monitoring
# ---------------------------------------------------------------------------


class HeartbeatEmitter:
    """Emit periodic heartbeat events via EventEngine."""

    def __init__(
        self,
        events,
        *,
        interval: float = 5.0,
        source: str = "system",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.events = events
        self.interval = max(interval, 0.1)
        self.source = source
        self.meta = meta or {}
        self._stop_event = ThreadEvent()
        self._thread: Optional[Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._loop,
            daemon=True,
            name=f"HeartbeatEmitter[{self.source}]",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        from src.core.events import Event as CoreEvent, EventType
        next_tick = time.time()
        while not self._stop_event.is_set():
            now = time.time()
            if now >= next_tick:
                payload = {
                    "ts": now,
                    "source": self.source,
                    "meta": self.meta,
                }
                self.events.put(CoreEvent(EventType.HEARTBEAT, payload))
                next_tick = now + self.interval
            self._stop_event.wait(min(self.interval, 0.5))


class HeartbeatMonitor:
    """Monitor heartbeat events and trigger callbacks on timeout."""

    def __init__(
        self,
        events,
        *,
        timeout: float = 30.0,
        check_interval: float = 5.0,
        sources: Optional[List[str]] = None,
        on_timeout: Optional[Callable[[str, float], None]] = None,
        on_recover: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.events = events
        self.timeout = max(timeout, 0.1)
        self.check_interval = max(check_interval, 0.1)
        self.sources = set(sources) if sources else None
        self.on_timeout = on_timeout
        self.on_recover = on_recover
        self._last_seen: Dict[str, float] = {}
        self._timed_out: set[str] = set()
        self._stop_event = ThreadEvent()
        self._thread: Optional[Thread] = None
        self._handler = self._on_heartbeat

        if self.sources:
            now = time.time()
            for source in self.sources:
                self._last_seen[source] = now

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        from src.core.events import EventType
        self.events.register(EventType.HEARTBEAT, self._handler)
        self._stop_event.clear()
        self._thread = Thread(
            target=self._loop,
            daemon=True,
            name="HeartbeatMonitor",
        )
        self._thread.start()

    def stop(self) -> None:
        from src.core.events import EventType
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            self.events.unregister(EventType.HEARTBEAT, self._handler)
        except Exception:
            pass

    def _on_heartbeat(self, event) -> None:
        payload = event.data or {}
        source = payload.get("source", "unknown")
        if self.sources and source not in self.sources:
            return
        self._last_seen[source] = time.time()
        if source in self._timed_out:
            self._timed_out.remove(source)
            if self.on_recover:
                self.on_recover(source)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            for source, last_seen in list(self._last_seen.items()):
                age = now - last_seen
                if age > self.timeout and source not in self._timed_out:
                    self._timed_out.add(source)
                    if self.on_timeout:
                        self.on_timeout(source, age)
            self._stop_event.wait(self.check_interval)


def run_with_heartbeat_monitor(
    runner: Callable[..., Any],
    *,
    events,
    heartbeat_timeout: float = 30.0,
    check_interval: float = 5.0,
    max_restarts: int = 1,
    sources: Optional[List[str]] = None,
    runner_args: Optional[List[Any]] = None,
    runner_kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Run a callable with heartbeat monitoring and auto-restart.

    The runner may accept a `stop_event` keyword argument for cooperative shutdown.
    """
    attempts = 0
    runner_args = runner_args or []
    runner_kwargs = runner_kwargs or {}

    while attempts <= max_restarts:
        stop_event = ThreadEvent()
        timed_out = {"value": False}

        def on_timeout(source: str, age: float) -> None:
            timed_out["value"] = True
            logger.error(
                "heartbeat.timeout",
                source=source,
                age=round(age, 2),
                timeout=heartbeat_timeout,
                attempt=attempts + 1,
            )
            stop_event.set()

        monitor = HeartbeatMonitor(
            events,
            timeout=heartbeat_timeout,
            check_interval=check_interval,
            sources=sources,
            on_timeout=on_timeout,
        )
        monitor.start()

        try:
            kwargs = dict(runner_kwargs)
            try:
                if "stop_event" in inspect.signature(runner).parameters:
                    kwargs["stop_event"] = stop_event
            except (TypeError, ValueError):
                pass
            result = runner(*runner_args, **kwargs)
            monitor.stop()
            if timed_out["value"]:
                raise RuntimeError("heartbeat timeout")
            return result
        except Exception as exc:
            monitor.stop()
            attempts += 1
            if attempts > max_restarts:
                logger.error("heartbeat.supervisor.failed", retries=max_restarts, error=str(exc))
                raise
            logger.warning("heartbeat.supervisor.restart", attempt=attempts, error=str(exc))
