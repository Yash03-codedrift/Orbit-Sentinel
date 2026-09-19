import logging
from typing import Any, Dict, List

logger = logging.getLogger("orbit_sentinel.risk_config_repo")

DEFAULT_RISK_BANDS: List[Dict[str, Any]] = [
    {"key": "CRITICAL", "min_score": 0.15, "color": "#FF2D55"},
    {"key": "HIGH", "min_score": 0.05, "color": "#FF6B35"},
    {"key": "MEDIUM", "min_score": 0.01, "color": "#FFB800"},
    {"key": "LOW", "min_score": 0.001, "color": "#00D4FF"},
]

_CONFIG_ID = "risk_bands"
MIN_BANDS = 2
MAX_BANDS = 6


def _sorted_desc(bands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(bands, key=lambda b: b["min_score"], reverse=True)


async def get_risk_bands(db: Any) -> List[Dict[str, Any]]:
    """
    Returns the active, ordered (highest severity first) list of risk bands.
    Falls back to DEFAULT_RISK_BANDS if no config has been saved yet.
    """
    doc = await db["risk_config"].find_one({"config_id": _CONFIG_ID})
    if not doc or not doc.get("bands"):
        return [dict(b) for b in DEFAULT_RISK_BANDS]
    return _sorted_desc([
        {"key": str(b["key"]), "min_score": float(b["min_score"]), "color": str(b.get("color", "#00D4FF"))}
        for b in doc["bands"]
    ])


async def replace_risk_bands(db: Any, bands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Overwrites the full band list (this is a replace, not a merge — the caller
    is expected to send the complete desired set of bands).
    """
    ordered = _sorted_desc(bands)
    await db["risk_config"].update_one(
        {"config_id": _CONFIG_ID},
        {"$set": {"config_id": _CONFIG_ID, "bands": ordered}},
        upsert=True,
    )
    logger.info(f"Risk bands updated: {[b['key'] for b in ordered]}")
    return ordered


def top_severity_keys(bands: List[Dict[str, Any]], count: int = 2) -> List[str]:
    """
    Returns the `count` highest-severity band keys from an already-sorted
    (descending) band list. Used anywhere the system needs a generic notion
    of "high risk" without hardcoding label names like CRITICAL/HIGH.
    """
    return [b["key"] for b in bands[:count]]