"""
Simple API key auth middleware for single-user deployment.
Set API_SECRET in env. If unset, auth is disabled (local dev).
Exempt: /health, /docs, /openapi.json, /redoc
"""
import os

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        secret = os.getenv("API_SECRET")
        if not secret or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if key != secret:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)
