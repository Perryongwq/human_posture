# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.auth import get_current_user
from app.core.models import JWTClaims
from app.core.redis_client import close_redis_pools
from app.app_mcp.client import get_session_pool
from app.middleware.activity import ActivityLogMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — pools are lazily initialised on first request, nothing to do here
    yield
    # Shutdown — close all connections cleanly
    await get_session_pool().close_all()
    close_redis_pools()


app = FastAPI(title=f"{settings.APP_NAME} API", version="1.0.0", lifespan=lifespan)

# ══ CORS MUST BE BEFORE ROUTERS ═══════════════════════════════════
# Starlette processes middleware in reverse-registration order.
# CORSMiddleware MUST be added before any app.include_router() call.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,        # Required — frontend sends Authorization header
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
# ActivityLogMiddleware is added last → becomes outermost → sees every request
app.add_middleware(ActivityLogMiddleware)

# ══ Routers (import AFTER middleware registration) ════════════════
from app.routers import example, posture
app.include_router(example.router)
app.include_router(posture.router)

# ══ Core Routes ═══════════════════════════════════════════════════

@app.get("/health")
def health_check():
    """Unauthenticated liveness probe."""
    return {"status": "ok"}


@app.get("/api/me", response_model=JWTClaims)
def get_me(user: JWTClaims = Depends(get_current_user)):
    """
    Proof-of-auth endpoint.
    Returns JWT claims for the authenticated user.
    With AUTH_MODE=0, returns mock dev claims.
    """
    return user
