"""NexusGuard — Audit Middleware (request-level logging)"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time


class AuditMiddleware(BaseHTTPMiddleware):
    """Lightweight request-level middleware for timing and tracing."""

    SKIP_PATHS = {"/health", "/api/docs", "/api/redoc", "/api/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Add timing header for observability
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        response.headers["X-NexusGuard-Version"] = "1.0.0"
        return response
