"""
RabbitMQ client for the data insert queue.

Adapted from the sample AMQP.py reference, using AmqpConnection
and project settings instead of external config files.

Usage — default queue (PIKA_VHOST / PIKA_QUEUE from .env):
    from app.queue.amqp import AMQP

    amqp = AMQP()
    amqp.initializequeue()
    amqp.send_pika_json(sql, data)

Usage — explicit target queue:
    amqp = AMQP(vhost="/otherdb", queue="otherqueue")
    amqp.initializequeue()
    amqp.send_pika_json(sql, data)
"""
import json
import logging

from app.core.config import settings
from app.queue.connection import AmqpConnection

logger = logging.getLogger(__name__)


class AMQP:
    """
    RabbitMQ publisher.

    vhost / queue override the settings defaults, letting one app send to
    multiple queues without creating separate settings entries.

      - initializequeue() declares the target queue via a persistent connection
      - send_pika_json() publishes via send_message() which opens its
        own fresh connection with publisher confirms (delivery_mode=2)
    """

    def __init__(self, vhost: str | None = None, queue: str | None = None) -> None:
        self._vhost = vhost if vhost is not None else settings.PIKA_VHOST
        self._queue = queue if queue is not None else settings.PIKA_QUEUE
        self._dataqueue: AmqpConnection | None = None

    def initializequeue(self) -> None:
        """Declare the durable task queue on the broker and immediately close the declare connection."""
        self._dataqueue = AmqpConnection(
            hostname=settings.PIKA_HOST,
            port=settings.PIKA_PORT,
            username=settings.PIKA_USER,
            password=settings.PIKA_PASS,
            vhosts=self._vhost,
            connection_name=self._queue,
            exchanges="",
            queues=self._queue,
            routingkeys=self._queue,
            qdurable="True",
            queuetype="QUEUE",
        )
        self._dataqueue.connect()
        self._dataqueue.setup_queues_task()
        self._dataqueue.connection.close()  # declaration done; send_message opens its own connection
        logger.debug("RabbitMQ queue declared: %s on vhost %s", self._queue, self._vhost)

    def createsendjson(self, sql: str, data: list) -> str:
        """Build the JSON payload expected by the consumer."""
        return json.dumps({
            "sql": sql,
            "data": data,
            "token": settings.PIKA_TOKEN,
        })

    def send_pika_json(self, sql: str, data: list) -> None:
        """Publish sql + data as a persistent confirmed message."""
        payload = self.createsendjson(sql, data)
        self._send_message_loop(self._dataqueue, payload)

    def _send_message_loop(self, dataqueue: AmqpConnection, payload: str) -> None:
        """Delegate to send_message — opens fresh connection with confirm_delivery."""
        dataqueue.send_message(payload)
        logger.debug("Published to queue=%s vhost=%s", self._queue, self._vhost)


