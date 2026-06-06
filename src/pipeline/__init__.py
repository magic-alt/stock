"""
Pipeline Event Handlers Module

Provides event subscribers for pipeline visualization and persistence.
Decouples analysis output generation from core engine logic.
"""
from __future__ import annotations

from .handlers import make_pipeline_handlers, PipelineEventCollector

__all__ = ["make_pipeline_handlers", "PipelineEventCollector"]
