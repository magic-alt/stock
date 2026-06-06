"""Re-export of jetbot financial-facts adapter.

The canonical implementation lives in ``src.data_sources.jetbot_facts``.
This module provides a stable import path under ``src.adapters.data``.
"""

from src.data_sources.jetbot_facts import (
    CORE_METRICS,
    SUPPORTED_SCHEMA_VERSIONS,
    JetbotExportEnvelope,
    JetbotFactRecord,
    JetbotFactsProvider,
    get_jetbot_facts_provider,
)

__all__ = [
    "CORE_METRICS",
    "SUPPORTED_SCHEMA_VERSIONS",
    "JetbotExportEnvelope",
    "JetbotFactRecord",
    "JetbotFactsProvider",
    "get_jetbot_facts_provider",
]
