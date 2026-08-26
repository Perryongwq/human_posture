# App Changelog

> **Purpose:** Tracks every file-level change made to this template.
> After pulling this template, to update existing codebase, use this log to know exactly which files to **add**, **replace**, or **review** — rather than doing a blind diff.

---

## How to Use This File

| Symbol    | Meaning                                                            |
| --------- | ------------------------------------------------------------------ |
| ➕ ADD    | New file — safe to copy directly into your project                 |
| ✏️ MODIFY | Existing file changed — review the diff and merge carefully        |
| 🗑️ DELETE | File removed from template — consider removing from your project   |
| ⚙️ CONFIG | Config/build file — changes may affect your build pipeline or deps |

**When pulling a new version of this template:**

1. Check the entries since your last sync version.
2. For each `➕ ADD` — copy the file into your project.
3. For each `✏️ MODIFY` — compare against your local copy and merge changes.
4. For each `⚙️ CONFIG` — review carefully before applying (may affect deps or tooling).
5. Update your local sync version marker.

---

## Version History

---

### v1.1.1 — 22-06-2026

> **MCP module renamed to `app_mcp`**
>
> The `app/mcp` folder has been renamed to `app/app_mcp` to avoid ambiguity with
> the MCP protocol namespace. All internal imports updated throughout the project.

| Change     | File                          | Notes                                                                                 |
| ---------- | ----------------------------- | ------------------------------------------------------------------------------------- |
| 🗑️ DELETE | `app/mcp/`                    | Folder removed — replaced by `app/app_mcp/`.                                          |
| ➕ ADD     | `app/app_mcp/`                | Renamed from `app/mcp/`. Contains `__init__.py`, `caller.py`, `client.py`, `config.py`, `utils.py`. |
| ✏️ MODIFY  | `app/app_mcp/caller.py`       | Updated module-level docstring imports and `from app.mcp.client` → `from app.app_mcp.client`. |
| ✏️ MODIFY  | `app/main.py`                 | Updated `from app.mcp.client` → `from app.app_mcp.client`.                           |
| ✏️ MODIFY  | `app/routers/example.py`      | Updated three imports: `app.mcp.*` → `app.app_mcp.*`.                                |
| ✏️ MODIFY  | `README.md`                   | Updated code example imports in section 6 to use `app.app_mcp`.                      |

**Migration notes for existing users:**

1. **Rename the folder** — `mv app/mcp app/app_mcp` (or `git mv app/mcp app/app_mcp`).
2. **Update all imports** — Replace every `from app.mcp.` with `from app.app_mcp.` across your codebase.
3. **Check for string references** — Search for `"app/mcp"` or `"app.mcp"` in configs, docs, and scripts and update those too.

---

### v1.1.0 — 10-06-2026

> **Config overhaul + runtime bug fixes**
>
> Replaces `.env` with `conf/maincfg.json` as the primary config source.
> All settings now live in a single JSON file alongside other conf files — no shell environment setup needed.
> Also ports several runtime correctness fixes: blocking Redis I/O moved off the event loop, fire-and-forget task GC fix, circuit breaker concurrency fix, and RabbitMQ connection leak fixes.

| Change     | File                         | Notes                                                                                                                                                                   |
| ---------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ➕ ADD     | `conf/maincfg.json`          | New primary config file replacing `.env`. All settings (JWE key, RBAC, Redis, CORS, RabbitMQ) go here. **Add to `.gitignore` — contains secrets.**                     |
| ✏️ MODIFY  | `app/core/config.py`         | Switched from `env_file` to `JsonConfigSettingsSource` pointing at `conf/maincfg.json`. Env vars still override JSON (test-safe). Added `Path`, `Tuple`, `Type` imports. |
| ✏️ MODIFY  | `app/core/rbac.py`           | Extracted `_redis_read_cache` / `_redis_write_cache` helpers; both Redis calls now run via `asyncio.to_thread()` — fixes event-loop blocking bug.                       |
| ✏️ MODIFY  | `app/app_mcp/caller.py`      | Added `_probe_in_flight` flag to `CircuitBreaker` — enforces single-probe semantics in `HALF_OPEN` state under concurrent load. Reset in `finally` and `reset()`.       |
| ✏️ MODIFY  | `app/middleware/activity.py` | Added `_background_tasks` set — holds strong references to fire-and-forget `asyncio.Task` objects so they cannot be silently GC'd mid-execution.                        |
| ✏️ MODIFY  | `app/queue/amqp.py`          | `initializequeue()` now closes the declare connection immediately after `setup_queues_task()`. Removed dead module-level `_dataqueue` variable and `close_amqp()`.       |
| ✏️ MODIFY  | `app/queue/connection.py`    | `send_message()` now sets `socket_timeout=5` / `connection_attempts=2` (fail-fast on dead broker) and wraps publish in `try/finally` to guarantee `connection.close()`. |
| ✏️ MODIFY  | `app/main.py`                | Removed `close_amqp()` import and lifespan call — it was dead code (module-level `_dataqueue` was never assigned).                                                      |
| ✏️ MODIFY  | `README.md`                  | All `.env` references updated to `conf/maincfg.json`. Section 2 rewritten as a fully documented `jsonc` config reference preserving all former `.env` comments.         |
| ✏️ MODIFY  | `.gitignore`                 | Added `conf/maincfg.json`.                                                                                                                                              |
| ✏️ MODIFY  | `tests/conftest.py`          | Changed `os.environ.setdefault` → `os.environ` (force-set) so the test JWE key always overrides the JSON config value.                                                  |
| ✏️ MODIFY  | `tests/test_config.py`       | Updated tests to reflect `maincfg.json` as config source and `.gitignore` assertion for `maincfg.json`.                                                                 |
| ✏️ MODIFY  | `tests/test_rbac_integration.py` | Fixed pre-existing screen ID mismatch (`_CAPTURED_SCREEN_ID` now correctly set to `"PROTECTED_SCREEN"`).                                                           |
| 🗑️ DELETE | `.env`                       | No longer used — all values moved to `conf/maincfg.json`. Safe to delete from your project.                                                                            |

**Migration notes for existing users:**

1. **Create `conf/maincfg.json`** — Copy the new `conf/maincfg.json` from the template and fill in your values. All fields match what was previously in `.env` (same names, JSON types for numbers/arrays).
2. **Add `conf/maincfg.json` to `.gitignore`** — It contains secrets. Copy the updated `.gitignore` or add the line manually.
3. **`app/core/config.py`** — Replace entirely. If you have added custom settings fields, re-add them to the new version.
4. **`app/core/rbac.py`** — Replace entirely. The changes are in the helper functions and `asyncio.to_thread()` calls — if you have not modified this file, replace directly.
5. **`app/app_mcp/caller.py`** — Replace entirely if you have not modified it. If you have, merge the `_probe_in_flight` changes into your `CircuitBreaker.call_async()` and `reset()` methods.
6. **`app/middleware/activity.py`** — Replace or add the `_background_tasks` set and update the `create_task` block (3 lines). Low risk — additive change only.
7. **`app/queue/amqp.py`** — Replace. If you have added insert functions, move them to the new file after replacing.
8. **`app/queue/connection.py`** — Replace or apply the two changes to `send_message()`: add the 3 timeout params to `ConnectionParameters` and wrap the publish block in `try/finally`.
9. **`app/main.py`** — Remove `from app.queue.amqp import close_amqp` and `close_amqp()` from the lifespan function.
10. **Delete `.env`** — Once `conf/maincfg.json` is in place and tested, the `.env` file can be deleted.
11. **Tests** — If you maintain the template tests, replace `tests/conftest.py`, `tests/test_config.py`, and `tests/test_rbac_integration.py`.

---

## Adding a New Entry

When you make changes, add a block at the **top** of the Version History section:

```markdown
### vX.Y.Z — DD-MM-YYYY

> Short description of the release.

| Change    | File           | Notes                       |
| --------- | -------------- | --------------------------- |
| ➕ ADD    | `path/to/file` | What it does                |
| ✏️ MODIFY | `path/to/file` | What changed and why        |
| 🗑️ DELETE | `path/to/file` | Why it was removed          |
| ⚙️ CONFIG | `requirements.txt` | Added `some-package>=1.0.0` |
```
