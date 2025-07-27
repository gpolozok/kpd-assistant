from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional
from pydantic import BaseModel

from kpd_assistant.lib.config import Config


class ErrorResponse(BaseModel):
    status: str = "error"
    data: Optional[dict] = None
    message: str


api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="Enter your API key in the header",
    auto_error=False
)


async def validate_api_key(api_key: str = Security(api_key_header)) -> str:
    if api_key != Config.project["fastapi_key"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(
                message="Invalid or missing API Key"
            ).model_dump()
        )
    return api_key
