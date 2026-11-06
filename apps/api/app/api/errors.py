"""Consistent API error responses."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from shared.ids import new_id


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        field_path: Optional[str] = None,
        allowed: Any = None,
        retryable: bool = False,
        correlation_id: Optional[str] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field_path = field_path
        self.allowed = allowed
        self.retryable = retryable
        self.correlation_id = correlation_id or new_id()
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "field_path": self.field_path,
                "allowed_values_or_range": self.allowed,
                "correlation_id": self.correlation_id,
                "retryable": self.retryable,
            }
        }


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", new_id())
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "field_path": None,
                "allowed_values_or_range": None,
                "correlation_id": cid,
                "retryable": False,
            }
        },
    )
