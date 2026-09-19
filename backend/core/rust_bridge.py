import asyncio
import json
import os
import logging
from pathlib import Path
from backend.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _resolve_binary_path() -> str:
    path = Path(settings.RUST_SGP4_BINARY_PATH)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)

def is_rust_available() -> bool:
    return os.path.exists(_resolve_binary_path())

async def propagate_via_rust(satellites: list[dict], timestamps: list) -> dict:
    """
    Serialize satellites + timestamps to JSON, pipe to Rust binary via subprocess.
    timestamps is list of datetime objects, convert to ISO strings.
    Returns dict: {norad_id: [position_dict, ...]}
    Raises RuntimeError if binary fails.
    """
    payload = json.dumps({
        "satellites": satellites,
        "timestamps": [t.isoformat() + "Z" for t in timestamps]
    })
    proc = await asyncio.create_subprocess_exec(
        _resolve_binary_path(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate(payload.encode())
    if proc.returncode != 0:
        raise RuntimeError(f"Rust SGP4 failed (exit {proc.returncode}): {stderr.decode()[:500]}")
    result = json.loads(stdout.decode())
    return result.get("results", {})
