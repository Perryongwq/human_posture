# backend/app/routers/example.py
"""
Example protected router demonstrating both auth dependencies side-by-side.

Teams: Copy this pattern for your own routes.
  - Depends(get_current_user) extracts JWT claims
  - Depends(require_rbac("SCREEN_ID")) enforces RBAC (no-op when AUTH_MODE != 2)
"""
import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.models import JWTClaims
from app.core.rbac import require_rbac
from app.app_mcp.caller import caller_func
from app.app_mcp.config import load_mcp_config
from app.app_mcp.utils import to_records
from app.queue.insert import insert_cap_check

router = APIRouter(prefix="/api", tags=["example"])


# ── Request model ─────────────────────────────────────────────────────────────

class CapCheckRequest(BaseModel):
    lot_no: str
    part_no: str
    station: str
    process: str
    remarks: str
    create_datetime: str  # format: 'YYYY/MM/DD HH24:MI:SS'


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/whoami")
async def whoami(
    user: JWTClaims = Depends(get_current_user),
    _: None = Depends(require_rbac("PROTECTED_SCREEN")),
):
    """
    Example protected endpoint with RBAC enforcement.

    Demonstrates both auth dependencies used together:
      - get_current_user: extracts and validates JWT claims
      - require_rbac(screen_id): checks RBAC access (transparent no-op when AUTH_MODE != 2)

    Replace "PROTECTED_SCREEN" with your actual screen ID.
    """
    return {
        "message": f"Hello, {user.username}!",
        "payroll": user.payroll,
        "department": user.deptcode,
    }


@router.get("/testdb")
async def test_db(
      user: JWTClaims = Depends(get_current_user),
      _: None = Depends(require_rbac("PROTECTED_SCREEN")),
    ):
    """
    Example endpoint for testing database read via MCP.
    Returns results as an array of objects — ready for Vue.js.
    """
    config = load_mcp_config()

    result = await caller_func(
        config,
        table_name="eprass.RTH0041",
        columns="*",
        condition={"NOC0027": "E25Y015800"},
        order_by=None,
        limit=100,
        db="eprass19c",  # "prass" | "eprass" | "eprass19c"
    )

    if result is None:
        return {"error": "Query failed or no data found"}

    return to_records(result)


@router.post("/testinsert")
async def test_insert(
    body: CapCheckRequest,
    user: JWTClaims = Depends(get_current_user),
    _: None = Depends(require_rbac("PROTECTED_SCREEN")),
):
    """
    Example endpoint for testing a RabbitMQ insert (cap check record).

    payroll is taken from the authenticated user's JWT — not sent by the client.
    Sends to the default queue (PIKA_VHOST / PIKA_QUEUE).
    """
    success = await asyncio.to_thread(
        insert_cap_check,      # insert function from app/queue/insert.py
        body.lot_no,
        body.part_no,
        user.payroll,          
        body.station,
        body.process,
        body.remarks,
        body.create_datetime,
    )

    if not success:
        return {"status": "error", "message": "Failed to queue insert"}

    return {"status": "ok"}


@router.post("/testinsert2")
async def test_insert_queue2(
    body: CapCheckRequest,
    user: JWTClaims = Depends(get_current_user),
    _: None = Depends(require_rbac("PROTECTED_SCREEN")),
):
    """
    Example endpoint targeting the second RabbitMQ queue (PIKA_VHOST_2 / PIKA_QUEUE_2).

    Same payload as /testinsert — only the destination queue differs.
    Set PIKA_VHOST_2 and PIKA_QUEUE_2 in .env to enable.
    """
    success = await asyncio.to_thread(
        insert_cap_check,
        body.lot_no,
        body.part_no,
        user.payroll,
        body.station,
        body.process,
        body.remarks,
        body.create_datetime,
        vhost=settings.PIKA_VHOST_2,
        queue=settings.PIKA_QUEUE_2,
    )

    if not success:
        return {"status": "error", "message": "Failed to queue insert (queue 2)"}

    return {"status": "ok", "queue": settings.PIKA_QUEUE_2}

