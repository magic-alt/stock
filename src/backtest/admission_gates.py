"""Strategy admission gate registry for staged rollout controls."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from src.backtest.admission import compute_params_signature

DEFAULT_STRATEGY_GATE_ROOT = os.path.join("report", "strategy_admission_gates")
STRATEGY_GATE_SEQUENCE = (
    "research",
    "baseline_registered",
    "admission_passed",
    "paper_validated",
    "live_candidate",
    "production",
)
_STAGE_INDEX = {stage: index for index, stage in enumerate(STRATEGY_GATE_SEQUENCE)}


class StrategyGateError(Exception):
    """Base error for strategy gate operations."""


class InvalidStrategyGateTransition(StrategyGateError):
    """Raised when a gate transition skips required stages."""


class MissingStrategyGateStage(StrategyGateError):
    """Raised when a required stage has not yet been reached."""

    def __init__(
        self,
        strategy_name: str,
        required_stage: str,
        current_stage: str,
        params_signature: str,
    ) -> None:
        self.strategy_name = strategy_name
        self.required_stage = required_stage
        self.current_stage = current_stage
        self.params_signature = params_signature
        super().__init__(
            "Strategy gate requirement not met: "
            f"strategy={strategy_name} params_signature={params_signature} "
            f"required={required_stage} current={current_stage}"
        )


def _now_ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_strategy_name(strategy_name: str) -> str:
    token = str(strategy_name or "").strip().lower()
    return token or "unknown"


def _normalize_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(params) if isinstance(params, dict) else {}


def _normalize_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def compute_gate_params_signature(params: Optional[Dict[str, Any]]) -> str:
    """Return a stable params signature for gate lookups."""
    return compute_params_signature(_normalize_params(params))


def stage_index(stage: str) -> int:
    """Return the sequence index for one gate stage."""
    if stage not in _STAGE_INDEX:
        raise InvalidStrategyGateTransition(f"Unknown strategy gate stage: {stage}")
    return _STAGE_INDEX[stage]


def strategy_gate_dir(
    strategy_name: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    params_signature: Optional[str] = None,
    gate_root: str = DEFAULT_STRATEGY_GATE_ROOT,
) -> str:
    """Return the directory for one strategy/params gate record."""
    signature = params_signature or compute_gate_params_signature(params)
    return os.path.abspath(os.path.join(gate_root, _normalize_strategy_name(strategy_name), signature))


def strategy_gate_path(
    strategy_name: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    params_signature: Optional[str] = None,
    gate_root: str = DEFAULT_STRATEGY_GATE_ROOT,
) -> str:
    """Return the persisted JSON path for one gate record."""
    return os.path.join(
        strategy_gate_dir(
            strategy_name,
            params=params,
            params_signature=params_signature,
            gate_root=gate_root,
        ),
        "gate_status.json",
    )


def _new_gate_payload(strategy_name: str, params: Dict[str, Any], params_signature: str) -> Dict[str, Any]:
    ts = _now_ts()
    return {
        "strategy": _normalize_strategy_name(strategy_name),
        "params": params,
        "params_signature": params_signature,
        "gate_sequence": list(STRATEGY_GATE_SEQUENCE),
        "current_stage": "research",
        "current_stage_index": stage_index("research"),
        "created_at": ts,
        "updated_at": ts,
        "artifacts": {},
        "results": {},
        "history": [],
    }


def _write_gate_payload(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    return payload


def load_strategy_gate(
    strategy_name: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    params_signature: Optional[str] = None,
    gate_root: str = DEFAULT_STRATEGY_GATE_ROOT,
) -> Optional[Dict[str, Any]]:
    """Load one gate record when it exists."""
    path = strategy_gate_path(
        strategy_name,
        params=params,
        params_signature=params_signature,
        gate_root=gate_root,
    )
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise StrategyGateError(f"Invalid strategy gate payload at {path}")

    current_stage = str(payload.get("current_stage", "research"))
    payload["gate_sequence"] = list(STRATEGY_GATE_SEQUENCE)
    payload["current_stage"] = current_stage
    payload["current_stage_index"] = stage_index(current_stage)
    return payload


def ensure_strategy_gate(
    strategy_name: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    gate_root: str = DEFAULT_STRATEGY_GATE_ROOT,
    source: str = "gate.init",
    details: Optional[Dict[str, Any]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ensure a research-stage record exists for one strategy/params pair."""
    normalized_params = _normalize_params(params)
    params_signature = compute_gate_params_signature(normalized_params)
    existing = load_strategy_gate(
        strategy_name,
        params_signature=params_signature,
        gate_root=gate_root,
    )
    if existing is not None:
        return existing

    payload = _new_gate_payload(strategy_name, normalized_params, params_signature)
    stage_details = {"reason": "strategy_gate_initialized"}
    stage_details.update(_normalize_payload(details))
    stage_artifacts = _normalize_payload(artifacts)
    payload["history"].append(
        {
            "stage": "research",
            "timestamp": payload["created_at"],
            "source": source,
            "details": stage_details,
            "artifacts": stage_artifacts,
        }
    )
    if stage_details:
        payload["results"]["research"] = stage_details
    if stage_artifacts:
        payload["artifacts"]["research"] = stage_artifacts
    return _write_gate_payload(
        strategy_gate_path(
            strategy_name,
            params_signature=params_signature,
            gate_root=gate_root,
        ),
        payload,
    )


def is_stage_at_least(payload: Optional[Dict[str, Any]], required_stage: str) -> bool:
    """Return True when the payload has reached at least the required stage."""
    if not isinstance(payload, dict):
        return False
    current_stage = str(payload.get("current_stage", "research"))
    return stage_index(current_stage) >= stage_index(required_stage)


def build_strategy_gate_summary(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a compact summary suitable for logs and release decisions."""
    if not isinstance(payload, dict):
        return {
            "exists": False,
            "current_stage": "research",
            "current_stage_index": stage_index("research"),
            "params_signature": None,
            "updated_at": None,
        }
    current_stage = str(payload.get("current_stage", "research"))
    return {
        "exists": True,
        "strategy": payload.get("strategy"),
        "current_stage": current_stage,
        "current_stage_index": stage_index(current_stage),
        "params_signature": payload.get("params_signature"),
        "updated_at": payload.get("updated_at"),
    }


def require_strategy_stage(
    strategy_name: str,
    required_stage: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    gate_root: str = DEFAULT_STRATEGY_GATE_ROOT,
) -> Dict[str, Any]:
    """Raise when the strategy has not yet reached the required stage."""
    normalized_params = _normalize_params(params)
    params_signature = compute_gate_params_signature(normalized_params)
    payload = load_strategy_gate(
        strategy_name,
        params_signature=params_signature,
        gate_root=gate_root,
    )
    current_stage = str(payload.get("current_stage", "research")) if payload else "research"
    if is_stage_at_least(payload, required_stage):
        return payload or {}
    raise MissingStrategyGateStage(
        _normalize_strategy_name(strategy_name),
        required_stage,
        current_stage,
        params_signature,
    )


def promote_strategy_gate(
    strategy_name: str,
    target_stage: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    gate_root: str = DEFAULT_STRATEGY_GATE_ROOT,
    source: str = "gate.update",
    details: Optional[Dict[str, Any]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
    allow_reset: bool = False,
) -> Dict[str, Any]:
    """Promote one strategy gate forward, or reset later stages when explicitly requested."""
    normalized_params = _normalize_params(params)
    params_signature = compute_gate_params_signature(normalized_params)
    path = strategy_gate_path(
        strategy_name,
        params_signature=params_signature,
        gate_root=gate_root,
    )
    payload = ensure_strategy_gate(
        strategy_name,
        params=normalized_params,
        gate_root=gate_root,
        source=source,
    )
    current_stage = str(payload.get("current_stage", "research"))
    current_index = stage_index(current_stage)
    target_index = stage_index(target_stage)

    if target_index > current_index + 1:
        raise InvalidStrategyGateTransition(
            f"Cannot skip strategy gate stages: current={current_stage} target={target_stage}"
        )
    if target_index < current_index and not allow_reset:
        return payload

    ts = _now_ts()
    stage_details = _normalize_payload(details)
    stage_artifacts = _normalize_payload(artifacts)
    if allow_reset and target_index < current_index:
        stage_details.setdefault("reset_from_stage", current_stage)

    payload["updated_at"] = ts
    payload["current_stage"] = target_stage
    payload["current_stage_index"] = target_index

    if stage_details:
        payload.setdefault("results", {}).setdefault(target_stage, {}).update(stage_details)
    if stage_artifacts:
        payload.setdefault("artifacts", {}).setdefault(target_stage, {}).update(stage_artifacts)
    payload.setdefault("history", []).append(
        {
            "stage": target_stage,
            "timestamp": ts,
            "source": source,
            "details": stage_details,
            "artifacts": stage_artifacts,
        }
    )
    return _write_gate_payload(path, payload)