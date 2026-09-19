from fastapi import Header, HTTPException
from backend.config import settings

async def verify_api_key(x_api_key: str = Header(default="")):
    if not settings.API_KEY or settings.API_KEY == "changeme":
        raise HTTPException(status_code=500, detail="Server API key not configured.")
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return True