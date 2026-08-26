"""
Database insert functions — send records to RabbitMQ for async DB insertion.

SQL queries are defined as module-level constants (no external JSON file).
Each public function builds the bind-variable list and calls _send_to_queue().

Usage in an async route:
    import asyncio
    from app.queue.insert import insert_cap_check

    success = await asyncio.to_thread(insert_cap_check, lot_no, part_no, ...)

Usage in sync code:
    from app.queue.insert import insert_cap_check

    success = insert_cap_check(lot_no, part_no, ...)

Targeting a non-default queue (e.g. PIKA_VHOST_2 / PIKA_QUEUE_2):
    from app.core.config import settings
    from app.queue.insert import insert_cap_check

    success = insert_cap_check(..., vhost=settings.PIKA_VHOST_2, queue=settings.PIKA_QUEUE_2)
"""
import logging

from app.queue.amqp import AMQP

logger = logging.getLogger(__name__)

# ── SQL constants ─────────────────────────────────────────────────────────────

_SQL_INSERT_CAP_CHECK = (
    "INSERT INTO PRASS.RTH0054 "
    "(NOC0027, RTO0002, CDC0145, RTO0001, RTO0011, DHC0060, HID0006) "
    "VALUES (:1, :2, :3, :4, :5, :6, TO_DATE(:7, 'YYYY/MM/DD HH24:MI:SS'))"
)

# Add more SQL constants here as needed:
# _SQL_INSERT_XYZ = "INSERT INTO ..."


# ── Public insert functions ───────────────────────────────────────────────────

def insert_cap_check(
    lot_no: str,
    part_no: str,
    payroll: str,
    station: str,
    process: str,
    remarks: str,
    create_datetime: str,
    *,
    vhost: str | None = None,
    queue: str | None = None,
) -> bool:
    """
    Send a cap check record to the RabbitMQ insert queue.

    Args:
        lot_no:          Lot number          (NOC0027)
        part_no:         Part number         (RTO0002)
        payroll:         Employee payroll ID (CDC0145)
        station:         Station name        (RTO0001)
        process:         Process name        (RTO0011)
        remarks:         Remarks             (DHC0060)
        create_datetime: Datetime string     (HID0006) — format 'YYYY/MM/DD HH24:MI:SS'
        vhost:           Override PIKA_VHOST (keyword-only). Defaults to settings.PIKA_VHOST.
        queue:           Override PIKA_QUEUE (keyword-only). Defaults to settings.PIKA_QUEUE.

    Returns:
        True if the message was published successfully, False otherwise.
    """
    data = [[
        lot_no,          # :1 NOC0027
        part_no,         # :2 RTO0002
        payroll,         # :3 CDC0145
        station,         # :4 RTO0001
        process,         # :5 RTO0011
        remarks,         # :6 DHC0060
        create_datetime, # :7 HID0006
    ]]
    logger.info(
        "insert_cap_check — lot=%s part=%s process=%s station=%s",
        lot_no, part_no, process, station,
    )
    return _send_to_queue(_SQL_INSERT_CAP_CHECK, data, vhost=vhost, queue=queue)


# ── Internal helper ───────────────────────────────────────────────────────────

def _send_to_queue(sql: str, data: list, vhost: str | None = None, queue: str | None = None) -> bool:
    """
    Declare the queue and publish sql+data via AmqpConnection.send_message(),
    which opens a fresh confirmed connection per publish then closes it.

    vhost / queue override the .env defaults (PIKA_VHOST / PIKA_QUEUE) so the
    same helper can target multiple queues.

    Returns True on success, False on any error.
    """
    amqp = AMQP(vhost=vhost, queue=queue)
    try:
        amqp.initializequeue()
        amqp.send_pika_json(sql, data)
        return True
    except Exception as exc:
        logger.error("_send_to_queue failed: %s", exc)
        return False
