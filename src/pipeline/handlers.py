"""
Pipeline Event Handlers

Event subscribers for grid search and auto pipeline results processing.
Handles visualization (heatmaps, Pareto charts) and persistence (CSV, reports).
"""
from __future__ import annotations

import os
from typing import List, Tuple, Dict, Any, Callable
import pandas as pd

from src.core.events import Event, EventType, Handler


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
