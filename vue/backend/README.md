# Backend — FastAPI App Template

A FastAPI backend pre-wired with JWE authentication and optional RBAC enforcement.
Developers only need to touch `app/main.py`, `app/routers/`, and `conf/maincfg.json`.

---

## Folder Structure

```
backend/
├── conf/
│   ├── maincfg.json           ← app config (replaces .env)
│   ├── mcp_setting.json       ← MCP server URLs
│   └── mcpkey.json            ← MCP bearer token
├── requirements.txt
├── pytest.ini
├── app/
│   ├── main.py            ← register your routers here
│   ├── routers/           ← add your route files here
│   │   └── example.py
│   ├── core/              ← framework internals — do not edit
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── rbac.py
│   │   └── redis_client.py
│   ├── middleware/        ← automatic cross-cutting behaviour
│   │   └── activity.py   ← logs every endpoint hit to RabbitMQ
│   └── queue/             ← RabbitMQ insert helpers
│       ├── connection.py  ← AmqpConnection (low-level pika wrapper)
│       ├── amqp.py        ← AMQP class (initializequeue / send_pika_json)
│       ├── insert.py      ← SQL constants + typed insert functions
│       └── activity.py   ← activity log publisher
└── tests/
```

---

## 1. Setup

### Create and activate the virtual environment

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**

```bash
python -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Configure Environment

All configuration lives in `conf/maincfg.json`. The file is pre-filled with shared infrastructure values — **you only need to update the app-specific fields** highlighted below.

```jsonc
{
    // ── Required ──────────────────────────────────────────────────────
    // App JWE key — decrypts tokens issued by VueAuthService.
    // CRITICAL: Must be identical to JWT_JWE_KEY in VueAuthService.
    "JWT_JWE_KEY": "<base64url-encoded-32-byte-key>",

    // ── RBAC (required when AUTH_MODE=2) ──────────────────────────────
    // Pre-filled — no changes needed unless RBAC server changes.
    "RBAC_API_URL": "http://163.50.34.41:31101",
    "RBAC_API_KEY": "<rbac-api-key>",
    "REDIS_HOST": "163.50.34.57",
    "REDIS_WRITE_PORT": 6379,
    "REDIS_READ_PORT": 6380,
    "REDIS_PASS": "<redis-password>",
    "REDIS_EXPIRE": 3600,

    // ── CORS ──────────────────────────────────────────────────────────
    // Leave CORS_ORIGINS empty when using CORS_ORIGIN_REGEX.
    "CORS_ORIGINS": [],

    // Regex: matches any port on the listed hosts.
    // To add a host: append |<new-ip> inside the group.
    "CORS_ORIGIN_REGEX": "https?://(localhost|127\\.0\\.0\\.1|163\\.50\\.34\\.41)(:\\d+)?",

    // ── App identity ──────────────────────────────────────────────────
    // Your application name — used as the MCP client identity.
    "APP_NAME": "YOUR_APP_NAME",

    // Auth mode: 0=off (dev) | 1=sso only | 2=sso + RBAC
    "AUTH_MODE": 1,

    // ── RabbitMQ insert queue ─────────────────────────────────────────
    // Security token — included in every queue payload and validated by the consumer.
    "PIKA_TOKEN": "<your-consumer-token>",
    // Shared broker connection (all queues use the same broker).
    "PIKA_HOST": "163.50.34.28",
    "PIKA_PORT": 5672,
    "PIKA_USER": "webuser",
    "PIKA_PASS": "userweb",

    // Default vhost & queue
    "PIKA_VHOST": "/realtimedb",
    "PIKA_QUEUE": "<your-queue-name>",

    // Additional vhost & queue (optional — add more pairs as needed)
    "PIKA_VHOST_2": "",
    "PIKA_QUEUE_2": "",

    // Activity log queue — records every endpoint access (ip, route, payroll, username)
    "PIKA_VUE_VHOST": "/vue",
    "PIKA_VUE_QUEUE": "activity_log"
}
```

> **Note:** JSON does not support comments (`//`). The snippet above uses `jsonc` notation for documentation only — the actual `conf/maincfg.json` file uses plain JSON.

**AUTH_MODE reference**

| Value | Behaviour                                                                         |
| ----- | --------------------------------------------------------------------------------- |
| `0`   | Auth disabled — all routes return mock dev claims. Use for local dev without SSO. |
| `1`   | SSO enabled — routes require a valid JWE token from VueAuthService.               |
| `2`   | SSO + RBAC — routes additionally check role/department access via the RBAC API.   |

---

## 3. Run the App

```bash
uvicorn app.main:app --port 8000 --reload
```

Once running:

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The frontend connects directly via `VITE_API_URL` in `frontend/.env` — no nginx or reverse proxy needed:

```env
# frontend/.env
VITE_API_URL=http://163.50.34.44:8000/api   # production
VITE_API_URL=http://localhost:8000/api       # local dev
```

---

## 4. Adding a New Router

### Step 1 — Create your router file

Create a new file inside `app/routers/`, e.g. `app/routers/orders.py`:

```python
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.models import JWTClaims
from app.core.rbac import require_rbac

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/")
async def list_orders(user: JWTClaims = Depends(get_current_user)):
    return {"message": f"Orders for {user.username}"}
```

### Step 2 — Register it in `main.py`

Open `app/main.py` and add two lines in the routers section:

```python
# ══ Routers (import AFTER middleware registration) ════════════════
from app.routers import example
app.include_router(example.router)

from app.routers import orders          # ← add this
app.include_router(orders.router)       # ← add this
```

That's it. Your new routes are live at `/api/orders/`.

---

## 5. Protecting Routes

### Auth only — verify the user is logged in

Use `Depends(get_current_user)` to require a valid token.
The dependency returns a `JWTClaims` object with the user's details.

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.models import JWTClaims

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("/")
async def list_items(user: JWTClaims = Depends(get_current_user)):
    # user.username  — AD display name  e.g. "jsmith"
    # user.payroll   — employee ID      e.g. "EMP12345"
    # user.deptcode  — department code  e.g. "IT"
    return {"owner": user.username}
```

> When `AUTH_MODE=0` this dependency returns mock dev claims automatically —
> no token needed. No code changes required between dev and production.

---

### Auth + RBAC — restrict by role and department

Use `Depends(require_rbac("YOUR_SCREEN_ID"))` alongside `get_current_user`.
The RBAC check is a **transparent no-op** when `AUTH_MODE != 2`, so the same
code works in all environments.

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.models import JWTClaims
from app.core.rbac import require_rbac

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/")
async def list_reports(
    user: JWTClaims = Depends(get_current_user),
    _: None = Depends(require_rbac("YOUR_SCREEN_ID")),
):
    return {"message": f"Reports for {user.username}"}
```

Replace `"YOUR_SCREEN_ID"` with the screen ID registered in the RBAC system.

**What `require_rbac` checks (when `AUTH_MODE=2`)**

1. Looks up the user's RBAC level from Redis cache (re-fetches from API on miss)
2. Finds the screen definition by `screen_id`
3. Verifies the user's level meets `min_level` for that screen
4. Verifies the user's `deptcode` is in the screen's `allowed_depts`

Returns `403` if any check fails, `503` if the RBAC service is unreachable.

---

## 6. Querying the Database via MCP

The template includes a pre-wired MCP (Model Context Protocol) client layer.
Routers call `caller_func()` — everything else (connection, handshake, retry,
circuit breaker, decompression) is handled automatically.

### Config files (pre-filled — no changes needed)

**`conf/mcp_setting.json`** — server URLs are already set for the shared infrastructure:

```json
{
  "PRASS_MCP_SERVER": "http://163.50.34.41:31107/api",
  "EPRASS_MCP_SERVER": "http://163.50.34.41:31103/api",
  "MCP_SERVER_EPRASS_19C": "http://163.50.34.41:31102/api",
  "CLIENT_VERSION": "1.0.0",
  "APIKEY_PATH": "conf/mcpkey.json"
}
```

> `CLIENT_NAME` is not in this file — it is read automatically from `APP_NAME`
> in `conf/maincfg.json`, so the MCP server always sees your app's identity without any
> extra configuration.

### Querying in a router

```python
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.models import JWTClaims
from app.app_mcp.caller import caller_func
from app.app_mcp.config import load_mcp_config
from app.app_mcp.utils import to_records

router = APIRouter(prefix="/api/lots", tags=["lots"])


@router.get("/{lot_no}")
async def get_lot(lot_no: str, user: JWTClaims = Depends(get_current_user)):
    config = load_mcp_config()

    result = await caller_func(
        config,
        table_name="prass.MY_TABLE",
        columns="*",
        condition={"LOT_COL": lot_no},
        order_by=None,
        limit=100,
        db="prass",          # "prass" | "eprass" | "eprass19c"
    )

    if result is None:
        return {"error": "Query failed or no data found"}

    return to_records(result)  # → array of objects, ready for Vue.js
```

**Why `to_records()`?** The MCP server returns a columnar format
(`columns` array + `rows` array of arrays). `to_records()` zips them into an
array of objects so the Vue frontend can access fields by name:

```js
// ✅ With to_records — works naturally in Vue templates
row.HID1000;
row.CDC0068;

// ❌ Without it — requires brittle index lookups
row[0]; // HID1000
row[2]; // CDC0068
```

**`db` values**

| Value         | Connects to             |
| ------------- | ----------------------- |
| `"prass"`     | `PRASS_MCP_SERVER`      |
| `"eprass"`    | `EPRASS_MCP_SERVER`     |
| `"eprass19c"` | `MCP_SERVER_EPRASS_19C` |

---

### What caller_func handles automatically

| Feature         | Detail                                                      |
| --------------- | ----------------------------------------------------------- |
| Retry           | 3 attempts, exponential backoff (1s → 2s → 4s)              |
| Smart retry     | Permanent errors (bad SQL, missing column) fail immediately |
| Circuit breaker | Opens after 5 transient failures, recovers after 60s        |
| Decompression   | gzip / zlib / lzma responses decompressed transparently     |

---

### MCP folder structure

```
app/
└── mcp/
    ├── client.py   ← MCPClient + CompressionHelper (HTTP layer)
    ├── caller.py   ← caller_func + CircuitBreaker + retry (do not edit)
    ├── config.py   ← load_mcp_config() loader
    └── utils.py    ← to_records() and other result helpers
conf/
    ├── mcp_setting.json   ← server URLs (no changes needed)
    └── mcpkey.json        ← bearer token
```

---

## 7. Inserting Data via RabbitMQ

All database inserts go through the RabbitMQ queue — the backend publishes
the SQL + data, and the consumer service handles the actual DB write.

### Config (`conf/maincfg.json`)

```json
{
    "PIKA_HOST": "163.50.34.28",
    "PIKA_PORT": 5672,
    "PIKA_USER": "webuser",
    "PIKA_PASS": "userweb",
    "PIKA_TOKEN": "<your-consumer-token>",

    "PIKA_VHOST": "/realtimedb",
    "PIKA_QUEUE": "realtimedb_opr_19c",

    "PIKA_VHOST_2": "/otherdb",
    "PIKA_QUEUE_2": "other_queue_name"
}
```

`PIKA_TOKEN` is included in every queue payload and validated by the consumer.
All queue targets share the same broker connection credentials.

---

### Queue module structure

```
app/queue/
├── connection.py  ← AmqpConnection — pika wrapper (publish + consume)
├── amqp.py        ← AMQP class — initializequeue() + send_pika_json()
└── insert.py      ← SQL constants + typed insert functions
```

**How a message flows:**

```
route handler
  → insert_cap_check(...)          # insert.py
    → _send_to_queue(sql, data)
      → AMQP.initializequeue()     # declares queue
      → AMQP.send_pika_json()      # builds JSON payload
        → AmqpConnection.send_message()   # fresh connection + confirm_delivery
          → RabbitMQ broker
            → consumer inserts into Oracle DB
```

The payload sent to the broker:
```json
{
  "sql": "INSERT INTO EPRASS.RTH0054 ...",
  "data": [["E25Y015800", "PART-001", "EMP12345", "ST01", "PROC-A", "OK", "2026/04/09 13:00:00"]],
  "token": "<PIKA_TOKEN>"
}
```

---

### Using a built-in insert function (default queue)

```python
import asyncio
from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.models import JWTClaims
from app.queue.insert import insert_cap_check

router = APIRouter(prefix="/api/capcheck", tags=["capcheck"])


@router.post("/")
async def submit_cap_check(
    lot_no: str,
    part_no: str,
    station: str,
    process: str,
    remarks: str,
    create_datetime: str,
    user: JWTClaims = Depends(get_current_user),
):
    success = await asyncio.to_thread(
        insert_cap_check,
        lot_no,
        part_no,
        user.payroll,      # payroll from the authenticated user's JWT
        station,
        process,
        remarks,
        create_datetime,   # format: 'YYYY/MM/DD HH24:MI:SS'
    )

    if not success:
        return {"status": "error", "message": "Failed to queue insert"}

    return {"status": "ok"}
```

> `asyncio.to_thread()` runs the blocking pika call in a thread pool so the
> async event loop is not blocked.

---

### Sending to a different queue

Every insert function accepts optional `vhost` / `queue` keyword arguments that
override the `maincfg.json` defaults:

```python
from app.core.config import settings
from app.queue.insert import insert_cap_check

# Default queue (PIKA_VHOST / PIKA_QUEUE from maincfg.json)
insert_cap_check(lot_no, part_no, payroll, station, process, remarks, dt)

# Second queue (PIKA_VHOST_2 / PIKA_QUEUE_2 from maincfg.json)
insert_cap_check(
    lot_no, part_no, payroll, station, process, remarks, dt,
    vhost=settings.PIKA_VHOST_2,
    queue=settings.PIKA_QUEUE_2,
)
```

To add a third queue, define `PIKA_VHOST_3` / `PIKA_QUEUE_3` in `conf/maincfg.json` and in
`app/core/config.py`, then pass them the same way.

---

### Adding a new insert function

**Step 1** — Add the SQL constant to `app/queue/insert.py`:

```python
_SQL_INSERT_MY_TABLE = (
    "INSERT INTO EPRASS.MY_TABLE "
    "(COL1, COL2, COL3) "
    "VALUES (:1, :2, TO_DATE(:3, 'YYYY/MM/DD HH24:MI:SS'))"
)
```

**Step 2** — Add the function below it:

```python
def insert_my_table(col1: str, col2: str, col3: str) -> bool:
    """Send a MY_TABLE record to the insert queue."""
    data = [[col1, col2, col3]]
    logger.info("insert_my_table — col1=%s", col1)
    return _send_to_queue(_SQL_INSERT_MY_TABLE, data)
```

**Step 3** — Call it from your route:

```python
from app.queue.insert import insert_my_table

success = await asyncio.to_thread(insert_my_table, val1, val2, val3)
```

---

## 8. Activity Logging

Every endpoint hit is automatically logged to a dedicated RabbitMQ queue —
no changes needed to route files.

### How it works

`ActivityLogMiddleware` (registered in `main.py`) intercepts every HTTP request.
After the response is sent to the client it publishes a log entry as a
fire-and-forget background task — zero impact on response latency.

```
Client → ActivityLogMiddleware → CORSMiddleware → your route
              ↓ (after response sent — non-blocking)
      publish to activity_log queue → consumer → Oracle DB
```

**Captured fields per request:**

| Field | Source |
|---|---|
| `IP_ADDRESS` | `X-Forwarded-For` header → `client.host` fallback |
| `HTTP_METHOD` | `GET`, `POST`, etc. |
| `ROUTE` | URL path e.g. `/api/whoami` |
| `PAYROLL` | From JWT — empty string when unauthenticated |
| `USERNAME` | From JWT — empty string when unauthenticated |
| `LOG_DATETIME` | UTC timestamp at time of request |

**AUTH_MODE=0 behaviour:** logs `payroll=DEV001 / username=dev` so development
activity is still visible in the log without a real token.

**Skipped automatically:** `OPTIONS` preflight requests and `/health` liveness probes.

**Fault-tolerant:** if the queue is unavailable, a warning is logged and the
request continues normally — activity logging never crashes the app.

---

### Config (`conf/maincfg.json`)

```json
{
    "PIKA_VUE_VHOST": "/vue",
    "PIKA_VUE_QUEUE": "activity_log"
}
```

---

## 9. Running Tests

```bash
pytest tests/
```
