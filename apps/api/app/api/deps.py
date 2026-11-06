"""API dependencies — development auth is NOT production-safe."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Header, Request

from app.api.errors import APIError
from app.core.config import get_settings
from app.services.engine import Engine, get_engine
from shared.ids import new_id


async def correlation_id(request: Request, x_correlation_id: Annotated[Optional[str], Header()] = None) -> str:
    cid = x_correlation_id or new_id()
    request.state.correlation_id = cid
    return cid


async def tenant_id(
    x_tenant_id: Annotated[Optional[str], Header()] = None,
    x_actor_id: Annotated[Optional[str], Header()] = None,
) -> str:
    settings = get_settings()
    if settings.auth_mode == "development":
        # Development auth — NOT production-safe
        return x_tenant_id or settings.default_tenant_id
    # Entra ID placeholder
    if not x_tenant_id:
        raise APIError("UNAUTHORIZED", "Entra ID auth required", status_code=401)
    return x_tenant_id


async def actor_id(x_actor_id: Annotated[Optional[str], Header()] = None) -> str:
    return x_actor_id or get_settings().default_user_id


def engine() -> Engine:
    return get_engine()


TenantDep = Annotated[str, ...]
