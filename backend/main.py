import os
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import router, limiter
from api.auth_router import auth_router
import data.history_store as history_store

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

_HSTS_MAX_AGE = int(os.getenv("HSTS_MAX_AGE", "31536000"))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={_HSTS_MAX_AGE}; includeSubDomains"
            )
        return response


app = FastAPI(
    title="Project Sentinel",
    description="Enterprise Agentic Document Routing & Compliance Engine",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://sentinel-ui-sanjeev-2026.s3-website.ap-south-1.amazonaws.com",
    # Vercel deployments — both preview and production
    "https://sentinel-enterprise.vercel.app",
    "https://sentinel-enterprise-daarshnicsanjeev.vercel.app",
]
_extra = os.getenv("ALLOWED_ORIGINS", "")
# Also support wildcard Vercel preview URLs via pattern matching below
_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Allow all Vercel preview + production deployments
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type", "x-api-key", "authorization"],
)

app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.on_event("startup")
async def startup():
    await history_store.init_db()
