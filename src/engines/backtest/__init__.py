"""Backtest engine — V6 ring wrapper over the historical simulator.

Re-exports :class:`BacktestEngine` plus the multi-backend registry
abstractions, repro snapshot helpers and the strategy admission /
baseline workflow.  Together these satisfy the V6 ``BacktestPort``,
``ReproPort`` and ``AdmissionPort`` ports.
"""

from __future__ import annotations

from src.backtest.admission import (
    AdmissionProfile,
    HistoricalSampleCase,
    RegressionTolerance,
    evaluate_admission,
    generate_historical_baseline,
    register_strategy_baseline,
    resolve_admission_profile,
    write_admission_artifacts,
    write_baseline_artifacts,
)
from src.backtest.analysis import pareto_front
from src.backtest.engine import BacktestEngine
from src.backtest.engine_base import BackendRunResult, EngineBackend, EngineRegistry
from src.backtest.repro import (
    build_repro_command,
    build_snapshot_payload,
    compute_data_fingerprint,
    compute_report_signature,
    write_snapshot,
)

__all__ = (
    "BacktestEngine",
    "EngineBackend",
    "EngineRegistry",
    "BackendRunResult",
    "AdmissionProfile",
    "HistoricalSampleCase",
    "RegressionTolerance",
    "evaluate_admission",
    "generate_historical_baseline",
    "register_strategy_baseline",
    "resolve_admission_profile",
    "write_admission_artifacts",
    "write_baseline_artifacts",
    "build_repro_command",
    "build_snapshot_payload",
    "compute_data_fingerprint",
    "compute_report_signature",
    "write_snapshot",
    "pareto_front",
)
