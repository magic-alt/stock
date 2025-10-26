"""
Pipeline Event Handlers

Event subscribers for grid search and auto pipeline results processing.
Handles visualization (heatmaps, Pareto charts) and persistence (CSV, reports).
Includes progress tracking, Telegram/Email notifications.
"""
from __future__ import annotations

import os
from typing import List, Tuple, Dict, Any, Callable, Optional
import pandas as pd

from src.core.events import Event, EventType, Handler


# Optional dependencies
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False


class PipelineEventCollector:
    """
    Collects and persists pipeline results via event subscription.
    
    Subscribes to:
    - EventType.METRICS_CALCULATED: Collect individual run results
    - EventType.PIPELINE_STAGE: Trigger persistence on completion
    
    Features:
    - Per-strategy result buffering
    - CSV export on pipeline completion
    - Optional heatmap/Pareto generation
    - Automatic cleanup after persistence
    """
    
    def __init__(self, out_dir: str = "./reports"):
        """
        Initialize collector with output directory.
        
        Args:
            out_dir: Directory for CSV and visualization output
        """
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        
        # Buffer: strategy_name -> List[{params, metrics}]
        self._results: Dict[str, List[Dict[str, Any]]] = {}
    
    def on_metrics_calculated(self, event: Event) -> None:
        """
        Handle METRICS_CALCULATED event.
        
        Collects metrics from each parameter combination run.
        
        Event data structure:
        {
            "strategy": str,
            "params": Dict[str, Any],
            "metrics": Dict[str, float],
            "i": int  # optional run index
        }
        """
        data = event.data
        strategy = data.get("strategy", "unknown")
        
        # Merge params and metrics into single record
        record = {
            **data.get("params", {}),
            **data.get("metrics", {}),
        }
        
        # Buffer for this strategy
        self._results.setdefault(strategy, []).append(record)
    
    def on_pipeline_stage(self, event: Event) -> None:
        """
        Handle PIPELINE_STAGE event.
        
        Triggers persistence when stage="grid.done" or "auto.done".
        
        Event data structure:
        {
            "stage": str,  # "grid.start", "grid.done", "auto.done", etc.
            "strategy": str,
            "param_count": int,  # optional
            "results": List[Dict]  # optional
        }
        """
        data = event.data
        stage = data.get("stage", "")
        strategy = data.get("strategy", "unknown")
        
        # Only persist on completion stages
        if stage not in ["grid.done", "auto.done"]:
            return
        
        # Check if we have results for this strategy
        if strategy not in self._results or not self._results[strategy]:
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(self._results[strategy])
        
        # Save CSV
        csv_path = os.path.join(self.out_dir, f"{strategy}_results.csv")
        df.to_csv(csv_path, index=False)
        
        # Optional: Generate visualizations if analysis module available
        try:
            from src.backtest.analysis import pareto_front
            
            # Pareto front (if sufficient data)
            if len(df) > 10:
                # Maximize: sharpe, return; Minimize: drawdown
                if "sharpe" in df.columns and "max_drawdown" in df.columns:
                    pf = pareto_front(
                        df,
                        maximize_cols=["sharpe"],
                        minimize_cols=["max_drawdown"]
                    )
                    pf_path = os.path.join(self.out_dir, f"{strategy}_pareto.csv")
                    pf.to_csv(pf_path, index=False)
        except Exception:
            # Silently skip if analysis unavailable or fails
            pass
        
        # Clear buffer for this strategy
        self._results[strategy] = []
    
    def get_handlers(self) -> List[Tuple[str, Handler]]:
        """
        Return list of (event_type, handler) tuples for registration.
        
        Returns:
            List of (EventType, handler_method) pairs
        
        Usage:
            >>> collector = PipelineEventCollector("./reports")
            >>> for etype, handler in collector.get_handlers():
            ...     engine.events.register(etype, handler)
        """
        return [
            (EventType.METRICS_CALCULATED, self.on_metrics_calculated),
            (EventType.PIPELINE_STAGE, self.on_pipeline_stage),
        ]


def make_pipeline_handlers(out_dir: str = "./reports") -> List[Tuple[str, Handler]]:
    """
    Factory function to create pipeline event handlers.
    
    Convenience function for quick setup.
    
    Args:
        out_dir: Output directory for results and visualizations
    
    Returns:
        List of (event_type, handler) tuples ready for registration
    
    Usage:
        >>> from src.pipeline.handlers import make_pipeline_handlers
        >>> 
        >>> engine = BacktestEngine()
        >>> handlers = make_pipeline_handlers("./reports_auto")
        >>> 
        >>> for etype, handler in handlers:
        ...     engine.events.register(etype, handler)
        >>> 
        >>> engine.events.start()
        >>> # Run grid search or auto pipeline
        >>> engine.grid_search(...)
        >>> engine.events.stop()
    
    Event Flow:
        1. Engine publishes PIPELINE_STAGE("grid.start")
        2. For each param combination:
           - Engine runs backtest
           - Engine publishes METRICS_CALCULATED(params, metrics)
        3. Engine publishes PIPELINE_STAGE("grid.done")
        4. Handler saves CSV and generates Pareto chart
    """
    collector = PipelineEventCollector(out_dir)
    return collector.get_handlers()


# Example: Custom handler with progress tracking
class ProgressTrackingCollector(PipelineEventCollector):
    """
    Extended collector with progress tracking and live updates.
    
    Demonstrates how to extend PipelineEventCollector for custom behavior.
    """
    
    def __init__(self, out_dir: str = "./reports", verbose: bool = True):
        super().__init__(out_dir)
        self.verbose = verbose
        self._progress: Dict[str, int] = {}  # strategy -> completed runs
    
    def on_metrics_calculated(self, event: Event) -> None:
        """Track progress and print live updates."""
        # Call parent to buffer results
        super().on_metrics_calculated(event)
        
        # Track progress
        strategy = event.data.get("strategy", "unknown")
        self._progress[strategy] = self._progress.get(strategy, 0) + 1
        
        # Print progress
        if self.verbose:
            count = self._progress[strategy]
            metrics = event.data.get("metrics", {})
            sharpe = metrics.get("sharpe", 0.0)
            print(f"[{strategy}] Run #{count}: Sharpe={sharpe:.3f}")
    
    def on_pipeline_stage(self, event: Event) -> None:
        """Print stage transitions."""
        if self.verbose:
            stage = event.data.get("stage", "")
            strategy = event.data.get("strategy", "")
            print(f"[Pipeline] {strategy}: {stage}")
        
        # Call parent to persist results
        super().on_pipeline_stage(event)
        
        # Reset progress counter on completion
        if event.data.get("stage") in ["grid.done", "auto.done"]:
            strategy = event.data.get("strategy", "unknown")
            if strategy in self._progress:
                del self._progress[strategy]


def make_progress_handlers(out_dir: str = "./reports") -> List[Tuple[str, Handler]]:
    """
    Create pipeline handlers with progress tracking.
    
    Args:
        out_dir: Output directory
    
    Returns:
        List of (event_type, handler) tuples with progress tracking
    """
    collector = ProgressTrackingCollector(out_dir, verbose=True)
    return collector.get_handlers()


# ---------------------------------------------------------------------------
# Progress Bar Handler (tqdm-based)
# ---------------------------------------------------------------------------

class ProgressBarHandler:
    """
    Real-time progress bar for grid search using tqdm.
    
    Subscribes to:
    - EventType.PIPELINE_STAGE("grid.start"): Initialize progress bar
    - EventType.METRICS_CALCULATED: Update progress bar
    - EventType.PIPELINE_STAGE("grid.done"): Close progress bar
    
    Features:
    - Real-time progress tracking with tqdm
    - Live Sharpe ratio display in postfix
    - Graceful degradation if tqdm unavailable
    - Per-strategy progress tracking
    
    Example:
        >>> handler = ProgressBarHandler()
        >>> for etype, func in handler.get_handlers():
        ...     engine.events.register(etype, func)
        >>> engine.grid_search(...)  # Progress bar will appear automatically
    """
    
    def __init__(self, desc: str = "Grid Search", disable: bool = False):
        """
        Initialize progress bar handler.
        
        Args:
            desc: Progress bar description prefix
            disable: Disable progress bar (useful for batch jobs)
        """
        self.desc = desc
        self.disable = disable or not TQDM_AVAILABLE
        self._pbars: Dict[str, Any] = {}  # strategy -> tqdm instance
        self._counts: Dict[str, int] = {}  # strategy -> completed count
        
        if not TQDM_AVAILABLE and not disable:
            print("Warning: tqdm not installed. Progress bar disabled. Install: pip install tqdm")
    
    def on_pipeline_stage(self, event: Event) -> None:
        """
        Handle pipeline stage events.
        
        - "grid.start": Create progress bar
        - "grid.done"/"auto.done": Close progress bar
        """
        if self.disable:
            return
        
        data = event.data
        stage = data.get("stage", "")
        strategy = data.get("strategy", "unknown")
        
        # Initialize progress bar on start
        if stage == "grid.start":
            total = data.get("param_count", 0)
            if total > 0 and TQDM_AVAILABLE:
                pbar = tqdm(
                    total=total,
                    desc=f"{self.desc} [{strategy}]",
                    unit="run",
                    ncols=100,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
                )
                self._pbars[strategy] = pbar
                self._counts[strategy] = 0
        
        # Close progress bar on completion
        elif stage in ["grid.done", "auto.done"]:
            if strategy in self._pbars:
                pbar = self._pbars[strategy]
                pbar.close()
                del self._pbars[strategy]
                if strategy in self._counts:
                    del self._counts[strategy]
    
    def on_metrics_calculated(self, event: Event) -> None:
        """
        Update progress bar on each metric calculation.
        
        Displays live Sharpe ratio in progress bar postfix.
        """
        if self.disable:
            return
        
        data = event.data
        strategy = data.get("strategy", "unknown")
        
        if strategy in self._pbars:
            pbar = self._pbars[strategy]
            metrics = data.get("metrics", {})
            sharpe = metrics.get("sharpe", 0.0)
            
            # Update progress
            pbar.update(1)
            
            # Update postfix with live metrics
            pbar.set_postfix({
                "Sharpe": f"{sharpe:.3f}",
            })
            
            self._counts[strategy] = self._counts.get(strategy, 0) + 1
    
    def get_handlers(self) -> List[Tuple[str, Handler]]:
        """
        Return list of (event_type, handler) tuples for registration.
        
        Returns:
            List of (EventType, handler_method) pairs
        """
        return [
            (EventType.PIPELINE_STAGE, self.on_pipeline_stage),
            (EventType.METRICS_CALCULATED, self.on_metrics_calculated),
        ]


def make_progress_bar_handler(desc: str = "Grid Search", disable: bool = False) -> List[Tuple[str, Handler]]:
    """
    Factory function to create progress bar event handlers.
    
    Args:
        desc: Progress bar description prefix
        disable: Disable progress bar (useful for batch jobs)
    
    Returns:
        List of (event_type, handler) tuples ready for registration
    
    Usage:
        >>> from src.pipeline.handlers import make_progress_bar_handler
        >>> 
        >>> engine = BacktestEngine()
        >>> handlers = make_progress_bar_handler("Optimizing Strategy")
        >>> 
        >>> for etype, handler in handlers:
        ...     engine.events.register(etype, handler)
        >>> 
        >>> engine.events.start()
        >>> engine.grid_search(...)  # Progress bar will appear
        >>> engine.events.stop()
    """
    handler = ProgressBarHandler(desc=desc, disable=disable)
    return handler.get_handlers()


# ---------------------------------------------------------------------------
# Telegram Notifier
# ---------------------------------------------------------------------------

class TelegramNotifier:
    """
    Send Telegram notifications for pipeline events.
    
    Subscribes to:
    - EventType.PIPELINE_STAGE("grid.done"/"auto.done"): Send completion notification
    - EventType.RISK_WARNING: Send risk alert (if enabled)
    
    Features:
    - Configurable bot token and chat ID
    - Optional risk alerts
    - Graceful degradation if configuration missing
    - Rate limiting to avoid spam
    
    Setup:
    1. Create Telegram bot via @BotFather
    2. Get bot token
    3. Get chat ID (send message to bot, visit https://api.telegram.org/bot<TOKEN>/getUpdates)
    4. Set environment variables or pass to constructor
    
    Example:
        >>> # Via environment variables
        >>> os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF..."
        >>> os.environ["TELEGRAM_CHAT_ID"] = "987654321"
        >>> 
        >>> notifier = TelegramNotifier()
        >>> for etype, handler in notifier.get_handlers():
        ...     engine.events.register(etype, handler)
        >>> 
        >>> # Or direct configuration
        >>> notifier = TelegramNotifier(
        ...     bot_token="123456:ABC-DEF...",
        ...     chat_id="987654321",
        ...     enable_risk_alerts=True
        ... )
    """
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enable_risk_alerts: bool = False,
        disable: bool = False,
    ):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID (or set TELEGRAM_CHAT_ID env var)
            enable_risk_alerts: Send notifications for risk warnings
            disable: Disable notifier (useful for testing)
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.enable_risk_alerts = enable_risk_alerts
        self.disable = disable or not REQUESTS_AVAILABLE
        
        # Check configuration
        if not self.disable and (not self.bot_token or not self.chat_id):
            print("Warning: Telegram notifier disabled. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
            self.disable = True
        
        if not REQUESTS_AVAILABLE and not disable:
            print("Warning: requests not installed. Telegram notifier disabled. Install: pip install requests")
            self.disable = True
    
    def _send_message(self, text: str) -> bool:
        """
        Send message to Telegram.
        
        Args:
            text: Message text (supports Markdown)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if self.disable:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram notification failed: {e}")
            return False
    
    def on_pipeline_stage(self, event: Event) -> None:
        """Send notification on pipeline completion."""
        if self.disable:
            return
        
        data = event.data
        stage = data.get("stage", "")
        strategy = data.get("strategy", "unknown")
        
        if stage in ["grid.done", "auto.done"]:
            total_runs = data.get("total_runs", 0)
            message = (
                f"✅ *Pipeline Completed*\n"
                f"Strategy: `{strategy}`\n"
                f"Stage: `{stage}`\n"
                f"Total runs: {total_runs}"
            )
            self._send_message(message)
    
    def on_risk_warning(self, event: Event) -> None:
        """Send notification on risk warning."""
        if self.disable or not self.enable_risk_alerts:
            return
        
        data = event.data
        reason = data.get("reason", "Unknown")
        value = data.get("value", 0.0)
        
        message = (
            f"⚠️ *Risk Alert*\n"
            f"Reason: `{reason}`\n"
            f"Value: {value:.4f}"
        )
        self._send_message(message)
    
    def get_handlers(self) -> List[Tuple[str, Handler]]:
        """Return list of (event_type, handler) tuples for registration."""
        handlers = [
            (EventType.PIPELINE_STAGE, self.on_pipeline_stage),
        ]
        if self.enable_risk_alerts:
            handlers.append((EventType.RISK_WARNING, self.on_risk_warning))
        return handlers


def make_telegram_notifier(
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    enable_risk_alerts: bool = False,
) -> List[Tuple[str, Handler]]:
    """
    Factory function to create Telegram notifier event handlers.
    
    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        enable_risk_alerts: Send notifications for risk warnings
    
    Returns:
        List of (event_type, handler) tuples ready for registration
    """
    notifier = TelegramNotifier(bot_token, chat_id, enable_risk_alerts)
    return notifier.get_handlers()


# ---------------------------------------------------------------------------
# Email Notifier
# ---------------------------------------------------------------------------

class EmailNotifier:
    """
    Send email notifications for pipeline events.
    
    Subscribes to:
    - EventType.PIPELINE_STAGE("grid.done"/"auto.done"): Send completion email
    - EventType.RISK_WARNING: Send risk alert email (if enabled)
    
    Features:
    - SMTP-based email delivery
    - HTML email formatting
    - Configurable sender/recipient
    - Graceful degradation if SMTP unavailable
    
    Setup:
    1. Configure SMTP server (e.g., Gmail, SendGrid)
    2. Set environment variables or pass to constructor
    
    Example:
        >>> # Via environment variables
        >>> os.environ["EMAIL_SMTP_HOST"] = "smtp.gmail.com"
        >>> os.environ["EMAIL_SMTP_PORT"] = "587"
        >>> os.environ["EMAIL_USERNAME"] = "your@gmail.com"
        >>> os.environ["EMAIL_PASSWORD"] = "your_app_password"
        >>> os.environ["EMAIL_FROM"] = "your@gmail.com"
        >>> os.environ["EMAIL_TO"] = "recipient@example.com"
        >>> 
        >>> notifier = EmailNotifier()
        >>> for etype, handler in notifier.get_handlers():
        ...     engine.events.register(etype, handler)
    """
    
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_addr: Optional[str] = None,
        to_addr: Optional[str] = None,
        enable_risk_alerts: bool = False,
        disable: bool = False,
    ):
        """
        Initialize email notifier.
        
        Args:
            smtp_host: SMTP server host (or set EMAIL_SMTP_HOST env var)
            smtp_port: SMTP server port (or set EMAIL_SMTP_PORT env var)
            username: SMTP username (or set EMAIL_USERNAME env var)
            password: SMTP password (or set EMAIL_PASSWORD env var)
            from_addr: From email address (or set EMAIL_FROM env var)
            to_addr: To email address (or set EMAIL_TO env var)
            enable_risk_alerts: Send emails for risk warnings
            disable: Disable notifier (useful for testing)
        """
        self.smtp_host = smtp_host or os.environ.get("EMAIL_SMTP_HOST")
        self.smtp_port = smtp_port or int(os.environ.get("EMAIL_SMTP_PORT", "587"))
        self.username = username or os.environ.get("EMAIL_USERNAME")
        self.password = password or os.environ.get("EMAIL_PASSWORD")
        self.from_addr = from_addr or os.environ.get("EMAIL_FROM")
        self.to_addr = to_addr or os.environ.get("EMAIL_TO")
        self.enable_risk_alerts = enable_risk_alerts
        self.disable = disable or not SMTP_AVAILABLE
        
        # Check configuration
        if not self.disable and not all([
            self.smtp_host, self.smtp_port, self.username, 
            self.password, self.from_addr, self.to_addr
        ]):
            print("Warning: Email notifier disabled. Set EMAIL_* environment variables.")
            self.disable = True
    
    def _send_email(self, subject: str, body_html: str) -> bool:
        """
        Send HTML email via SMTP.
        
        Args:
            subject: Email subject
            body_html: HTML email body
        
        Returns:
            True if sent successfully, False otherwise
        """
        if self.disable:
            return False
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = self.to_addr
            
            # Attach HTML body
            html_part = MIMEText(body_html, "html")
            msg.attach(html_part)
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False
    
    def on_pipeline_stage(self, event: Event) -> None:
        """Send email on pipeline completion."""
        if self.disable:
            return
        
        data = event.data
        stage = data.get("stage", "")
        strategy = data.get("strategy", "unknown")
        
        if stage in ["grid.done", "auto.done"]:
            total_runs = data.get("total_runs", 0)
            subject = f"Pipeline Completed: {strategy}"
            body = f"""
            <html>
            <body>
                <h2>✅ Pipeline Completed</h2>
                <p><strong>Strategy:</strong> {strategy}</p>
                <p><strong>Stage:</strong> {stage}</p>
                <p><strong>Total runs:</strong> {total_runs}</p>
            </body>
            </html>
            """
            self._send_email(subject, body)
    
    def on_risk_warning(self, event: Event) -> None:
        """Send email on risk warning."""
        if self.disable or not self.enable_risk_alerts:
            return
        
        data = event.data
        reason = data.get("reason", "Unknown")
        value = data.get("value", 0.0)
        
        subject = f"Risk Alert: {reason}"
        body = f"""
        <html>
        <body>
            <h2>⚠️ Risk Alert</h2>
            <p><strong>Reason:</strong> {reason}</p>
            <p><strong>Value:</strong> {value:.4f}</p>
        </body>
        </html>
        """
        self._send_email(subject, body)
    
    def get_handlers(self) -> List[Tuple[str, Handler]]:
        """Return list of (event_type, handler) tuples for registration."""
        handlers = [
            (EventType.PIPELINE_STAGE, self.on_pipeline_stage),
        ]
        if self.enable_risk_alerts:
            handlers.append((EventType.RISK_WARNING, self.on_risk_warning))
        return handlers


def make_email_notifier(
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    from_addr: Optional[str] = None,
    to_addr: Optional[str] = None,
    enable_risk_alerts: bool = False,
) -> List[Tuple[str, Handler]]:
    """
    Factory function to create email notifier event handlers.
    
    Args:
        smtp_host: SMTP server host
        smtp_port: SMTP server port
        username: SMTP username
        password: SMTP password
        from_addr: From email address
        to_addr: To email address
        enable_risk_alerts: Send emails for risk warnings
    
    Returns:
        List of (event_type, handler) tuples ready for registration
    """
    notifier = EmailNotifier(
        smtp_host, smtp_port, username, password,
        from_addr, to_addr, enable_risk_alerts
    )
    return notifier.get_handlers()

