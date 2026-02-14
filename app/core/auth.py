from fastapi import Header, HTTPException

from app.core.config import settings


def verify_api_key(x_api_key: str = Header(default="")) -> None:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
