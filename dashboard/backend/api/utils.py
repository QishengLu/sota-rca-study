"""Shared utility functions for API routes."""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import Session, text

logger = logging.getLogger(__name__)

# Fault type mapping from RCABench
FAULT_TYPES: list[str] = [
    "PodKill",  # 0
    "PodFailure",  # 1
    "ContainerKill",  # 2
    "MemoryStress",  # 3
    "CPUStress",  # 4
    "HTTPRequestAbort",  # 5
    "HTTPResponseAbort",  # 6
    "HTTPRequestDelay",  # 7
    "HTTPResponseDelay",  # 8
    "HTTPResponseReplaceBody",  # 9
    "HTTPResponsePatchBody",  # 10
    "HTTPRequestReplacePath",  # 11
    "HTTPRequestReplaceMethod",  # 12
    "HTTPResponseReplaceCode",  # 13
    "DNSError",  # 14
    "DNSRandom",  # 15
    "TimeSkew",  # 16
    "NetworkDelay",  # 17
    "NetworkLoss",  # 18
    "NetworkDuplicate",  # 19
    "NetworkCorrupt",  # 20
    "NetworkBandwidth",  # 21
    "NetworkPartition",  # 22
    "JVMLatency",  # 23
    "JVMReturn",  # 24
    "JVMException",  # 25
    "JVMGarbageCollector",  # 26
    "JVMCPUStress",  # 27
    "JVMMemoryStress",  # 28
    "JVMMySQLLatency",  # 29
    "JVMMySQLException",  # 30
]

# Mapping from fine-grained fault type to 6 coarse categories (per paper)
FAULT_CATEGORY_MAP: dict[str, str] = {
    # PodChaos
    "PodKill": "PodChaos",
    "PodFailure": "PodChaos",
    "ContainerKill": "PodChaos",
    # StressChaos
    "MemoryStress": "StressChaos",
    "CPUStress": "StressChaos",
    # HTTPFault
    "HTTPRequestAbort": "HTTPFault",
    "HTTPResponseAbort": "HTTPFault",
    "HTTPRequestDelay": "HTTPFault",
    "HTTPResponseDelay": "HTTPFault",
    "HTTPResponseReplaceBody": "HTTPFault",
    "HTTPResponsePatchBody": "HTTPFault",
    "HTTPRequestReplacePath": "HTTPFault",
    "HTTPRequestReplaceMethod": "HTTPFault",
    "HTTPResponseReplaceCode": "HTTPFault",
    # NetworkChaos (includes DNS and TimeSkew)
    "DNSError": "NetworkChaos",
    "DNSRandom": "NetworkChaos",
    "TimeSkew": "NetworkChaos",
    "NetworkDelay": "NetworkChaos",
    "NetworkLoss": "NetworkChaos",
    "NetworkDuplicate": "NetworkChaos",
    "NetworkCorrupt": "NetworkChaos",
    "NetworkBandwidth": "NetworkChaos",
    "NetworkPartition": "NetworkChaos",
    # JVMChaos
    "JVMLatency": "JVMChaos",
    "JVMReturn": "JVMChaos",
    "JVMException": "JVMChaos",
    "JVMGarbageCollector": "JVMChaos",
    "JVMCPUStress": "JVMChaos",
    "JVMMemoryStress": "JVMChaos",
    "JVMMySQLLatency": "JVMChaos",
    "JVMMySQLException": "JVMChaos",
}

# Base directory for RCABench dataset
# Get project root by resolving the path and going up from backend/api/utils.py
# Structure: RCAgentEval/scripts/dashboard/backend/api/utils.py
# So we need to go up 4 levels: api -> backend -> dashboard -> scripts -> RCAgentEval
_CURRENT_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _CURRENT_FILE.parent.parent.parent.parent.parent
RCABENCH_BASE_DIR = _PROJECT_ROOT / "data" / "rcabench_dataset"


def get_fault_type_from_injection(datapack_name: str) -> str:
    """Get fault type by reading injection.json from filesystem.

    Args:
        datapack_name: The datapack name (e.g., "ts0-ts-basic-service-dns-pdvxjg")

    Returns:
        Fault type name (e.g., "DNSError") or "unknown" if not found.
    """
    if not datapack_name:
        return "unknown"

    # Try to find the injection.json file
    datapack_dir = RCABENCH_BASE_DIR / datapack_name
    injection_file = datapack_dir / "injection.json"

    # Also try converted directory
    if not injection_file.exists():
        injection_file = datapack_dir / "converted" / "injection.json"

    # If still not found, try parent directory
    if not injection_file.exists():
        injection_file = datapack_dir.parent / "injection.json"

    if not injection_file.exists():
        logger.debug(f"injection.json not found for datapack: {datapack_name}")
        return "unknown"

    try:
        with open(injection_file, encoding="utf-8") as f:
            injection_data = json.load(f)

        fault_type_index = injection_data.get("fault_type")

        if fault_type_index is not None and 0 <= fault_type_index < len(FAULT_TYPES):
            return FAULT_TYPES[fault_type_index]

    except Exception as e:
        logger.warning(f"Error reading injection.json for {datapack_name}: {e}")

    return "unknown"


def parse_json_field(value: Any) -> dict | list | None:
    """Parse JSON field that may be str (SQLite) or dict/list (PostgreSQL).

    Args:
        value: The value to parse, can be None, dict, list, or JSON string.

    Returns:
        Parsed dict/list or None if parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def parse_datapack_name(datapack_name: str) -> tuple[str, str]:
    """Parse datapack_name to extract fault_type and system.

    Handles two formats:
    - "system_faulttype" -> (faulttype, system)
    - "system-faulttype-id" -> (faulttype, system)

    Args:
        datapack_name: The datapack name string.

    Returns:
        Tuple of (fault_type, system), defaults to ("unknown", "unknown").
    """
    if not datapack_name:
        return ("unknown", "unknown")

    # Format: "system_faulttype"
    if "_" in datapack_name:
        parts = datapack_name.split("_")
        if len(parts) >= 2:
            return (parts[1], parts[0])
        return ("unknown", parts[0] if parts else "unknown")

    # Format: "system-faulttype-id"
    parts = datapack_name.split("-")
    if len(parts) >= 3:
        system = parts[0]
        fault_type = "-".join(parts[1:-1]) if len(parts) > 3 else parts[1]
        return (fault_type, system)

    return ("unknown", "unknown")


def safe_query(db: Session, query: str, params: dict[str, Any] | None = None) -> list:
    """Execute a query safely, returning empty list if table doesn't exist.

    Args:
        db: Database session.
        query: SQL query string.
        params: Optional query parameters.

    Returns:
        List of query results, or empty list if table not found.

    Raises:
        OperationalError/ProgrammingError: For database errors other than missing tables.
    """
    try:
        stmt = text(query)
        if params:
            stmt = stmt.bindparams(**params)
        return list(db.exec(stmt))
    except (OperationalError, ProgrammingError) as e:
        error_str = str(e).lower()
        if "no such table" in error_str or "does not exist" in error_str:
            logger.warning(f"Table not found: {e}")
            return []
        raise


def avg(values: list[float]) -> float:
    """Calculate average of a list of values.

    Args:
        values: List of numeric values.

    Returns:
        Average value, or 0.0 if list is empty.
    """
    return sum(values) / len(values) if values else 0.0


def get_difficulty_from_meta(data_meta: dict | None) -> dict[str, Any]:
    """Extract pre-computed difficulty metadata from data_meta.

    Falls back to get_fault_type_from_injection / parse_datapack_name when
    difficulty sub-field is not yet populated.

    Returns:
        Dict with keys: spl, n_svc, n_edge, fault_type, fault_category
    """
    if not data_meta:
        return {"spl": None, "n_svc": None, "n_edge": None, "fault_type": "unknown", "fault_category": "unknown"}

    difficulty = data_meta.get("difficulty")
    if isinstance(difficulty, dict):
        return {
            "spl": difficulty.get("spl"),
            "n_svc": difficulty.get("n_svc"),
            "n_edge": difficulty.get("n_edge"),
            "fault_type": difficulty.get("fault_type", "unknown"),
            "fault_category": difficulty.get("fault_category", "unknown"),
        }

    # Fallback: compute on the fly from datapack_name
    datapack_name = data_meta.get("datapack_name", "")
    fault_type = get_fault_type_from_injection(datapack_name)
    fault_category = FAULT_CATEGORY_MAP.get(fault_type, "unknown")
    return {"spl": None, "n_svc": None, "n_edge": None, "fault_type": fault_type, "fault_category": fault_category}
