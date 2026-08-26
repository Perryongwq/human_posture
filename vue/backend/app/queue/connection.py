"""
AmqpConnection — low-level RabbitMQ wrapper using pika.

Ported from the sample reference. Handles connect, queue setup,
publish (with publisher confirms), and consume patterns.
"""
import functools
import logging
import os

import pika
import pika.exceptions
from retry import retry

logger = logging.getLogger(__name__)


class AmqpConnection:
    def __init__(
        self,
        hostname: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        vhosts: str = "",
        connection_name: str = "",
        exchanges: str = "",
        queues: str = "",
        routingkeys: str = "",
        qdurable: str = "",
        queuetype: str = "",
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.virtual_host = vhosts
        self.connection_name = connection_name
        self.exchanges = exchanges
        self.queues = queues
        self.routingkeys = routingkeys
        self.qdurable = qdurable
        self.queuetype = queuetype
        self.connection = None
        self.channel = None

    def send_message(self, message: str) -> None:
        """
        Publish a single message using a fresh connection with publisher confirms.
        Opens and closes its own connection — safe and reliable for one-off sends.
        """
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.hostname,
                port=self.port,
                virtual_host=self.virtual_host,
                credentials=pika.PlainCredentials(self.username, self.password),
                socket_timeout=5,
                connection_attempts=2,
                retry_delay=1,
            )
        )
        try:
            channel = connection.channel()
            channel.confirm_delivery()
            channel.basic_publish(
                exchange=self.exchanges,
                routing_key=self.routingkeys,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            connection.close()

    def connect(self) -> None:
        params = pika.ConnectionParameters(
            host=self.hostname,
            port=self.port,
            credentials=pika.PlainCredentials(self.username, self.password),
            virtual_host=self.virtual_host,
            client_properties={"connection_name": self.connection_name},
        )
        self.connection = pika.BlockingConnection(parameters=params)
        self.channel = self.connection.channel()

    def extended_connect(self) -> None:
        params = pika.ConnectionParameters(
            host=self.hostname,
            port=self.port,
            credentials=pika.PlainCredentials(self.username, self.password),
            virtual_host=self.virtual_host,
            client_properties={"connection_name": self.connection_name},
            heartbeat=600,
            blocked_connection_timeout=300,
        )
        self.connection = pika.BlockingConnection(parameters=params)
        self.channel = self.connection.channel()

    def setup_queues_fanout(self) -> None:
        durable = self.qdurable == "True"
        self.channel.queue_declare(self.queues, durable=durable)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.queue_bind(self.queues, exchange=self.exchanges, routing_key="")

    def setup_queues_task(self) -> None:
        durable = self.qdurable == "True"
        self.channel.queue_declare(self.queues, durable=durable)

    def do_async(self, callback, *args, **kwargs) -> None:
        if self.connection.is_open:
            self.connection.add_callback_threadsafe(
                functools.partial(callback, *args, **kwargs)
            )

    def publish(self, payload: str) -> None:
        if self.connection.is_open and self.channel.is_open:
            self.channel.basic_publish(
                exchange=self.exchanges,
                routing_key=self.routingkeys,
                body=payload,
            )
        else:
            logger.warning("publish skipped — connection is closed")

    def publish_persistent(self, payload: str) -> None:
        if self.connection.is_open and self.channel.is_open:
            self.channel.confirm_delivery()
            self.channel.basic_publish(
                exchange=self.exchanges,
                routing_key=self.routingkeys,
                body=payload,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        else:
            logger.warning("publish_persistent skipped — connection is closed")

    @retry(pika.exceptions.AMQPConnectionError, delay=1, backoff=2)
    def consume(self, on_message) -> None:
        if self.connection.is_closed or self.channel.is_closed:
            self.connect()
            self.setup_queues_task()
        try:
            self.channel.basic_consume(
                queue=self.queues, auto_ack=True, on_message_callback=on_message
            )
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.connection.close()
            os._exit(1)
        except pika.exceptions.ChannelClosedByBroker:
            logger.warning("Channel closed by broker")

    @retry(pika.exceptions.AMQPConnectionError, delay=1, backoff=2)
    def consume2(self, on_message) -> None:
        if self.connection.is_closed or self.channel.is_closed:
            self.connect()
            if self.queuetype == "QUEUE":
                self.setup_queues_task()
            else:
                self.setup_queues_fanout()
        try:
            self.channel.basic_consume(
                queue=self.queues, auto_ack=True, on_message_callback=on_message
            )
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.connection.close()
            os._exit(1)
        except pika.exceptions.ChannelClosedByBroker:
            logger.warning("Channel closed by broker")

    @retry(pika.exceptions.AMQPConnectionError, delay=1, backoff=2)
    def consume_noack(self, on_message) -> None:
        if self.connection.is_closed or self.channel.is_closed:
            self.connect()
            if self.queuetype == "QUEUE":
                self.setup_queues_task()
            else:
                self.setup_queues_fanout()
        try:
            self.channel.basic_consume(
                queue=self.queues, auto_ack=False, on_message_callback=on_message
            )
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.connection.close()
            os._exit(1)
        except pika.exceptions.ChannelClosedByBroker:
            logger.warning("Channel closed by broker")
