import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.db.mongo_client import get_db
from backend.db.risk_config_repo import (
    get_risk_bands,
    replace_risk_bands,
    DEFAULT_RISK_BANDS,
    MIN_BANDS,
    MAX_BANDS,
)
from backend.db import audit_repo
from backend.utils.auth import verify_api_key

logger = logging.getLogger("orbit_sentinel.risk_config_router")

router = APIRouter()


class RiskBandInput(BaseModel):
    key: str = Field(..., min_length=1, max_length=24)
    min_score: float = Field(..., gt=0, le=1)
    color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")


class RiskBandsUpdate(BaseModel):
    bands: List[RiskBandInput]


@router.get("")
async def read_risk_bands(db=Depends(get_db)):
    """Returns the currently active, ordered risk category bands."""
    bands = await get_risk_bands(db)
    return {"bands": bands, "defaults": DEFAULT_RISK_BANDS, "min_bands": MIN_BANDS, "max_bands": MAX_BANDS}


@router.put("", dependencies=[Depends(verify_api_key)])
async def write_risk_bands(payload: RiskBandsUpdate, request: Request, db=Depends(get_db)):
    """
    Replaces the full set of risk category bands without requiring a code
    change or redeploy. Teams can add, remove, rename, recolor, or rescore
    bands freely, subject to:
      - between MIN_BANDS and MAX_BANDS bands (inclusive)
      - unique, non-empty keys
      - unique min_score values

    Every change is written to the audit log with the full old -> new diff.
    """
    bands = payload.bands

    if not (MIN_BANDS <= len(bands) <= MAX_BANDS):
        raise HTTPException(
            status_code=400,
            detail=f"Must provide between {MIN_BANDS} and {MAX_BANDS} risk bands."
        )

    keys = [b.key.strip().upper() for b in bands]
    if len(set(keys)) != len(keys):
        raise HTTPException(status_code=400, detail="Band keys must be unique.")

    scores = [b.min_score for b in bands]
    if len(set(scores)) != len(scores):
        raise HTTPException(status_code=400, detail="Band min_score values must be unique.")

    before = await get_risk_bands(db)
    normalized = [{"key": k, "min_score": b.min_score, "color": b.color} for k, b in zip(keys, bands)]
    result = await replace_risk_bands(db, normalized)

    actor_key = request.headers.get("x-api-key", "")
    actor = f"OPERATOR (key ...{actor_key[-4:]})" if len(actor_key) >= 4 else "OPERATOR"

    def _fmt(bands_list):
        return ", ".join(f"{b['key']}={b['min_score']}" for b in bands_list)

    await audit_repo.append_audit_entry(db, {
        "timestamp": datetime.now(timezone.utc),
        "action_type": "RISK_CONFIG_UPDATED",
        "actor": actor,
        "outcome": "SUCCESS",
        "severity": "INFO",
        "details": f"Risk bands changed from [{_fmt(before)}] to [{_fmt(result)}].",
        "notes": "Updated via Risk Threshold Configuration panel (no-code).",
    })

    return {"bands": result}