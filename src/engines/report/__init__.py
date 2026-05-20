"""Report engine — V6 ring wrapper over reporting + attribution.

Re-exports the interactive ECharts-friendly report generator plus the
attribution / risk-metric helpers used to fill the report payload.
Satisfies the V6 ``ReportPort`` and ``AttributionPort`` ports.
"""

from __future__ import annotations

from src.backtest.attribution import (
    compute_capm_metrics,
    compute_concentration_metrics,
    compute_information_ratio,
    compute_sector_exposure,
    compute_style_exposure,
    compute_tracking_error,
    compute_var_es,
)
from src.backtest.report_generator import (
    InteractiveReportGenerator,
    ReportConfig,
    ReportSection,
)

__all__ = (
    "InteractiveReportGenerator",
    "ReportConfig",
    "ReportSection",
    "compute_var_es",
    "compute_tracking_error",
    "compute_information_ratio",
    "compute_capm_metrics",
    "compute_style_exposure",
    "compute_concentration_metrics",
    "compute_sector_exposure",
)
