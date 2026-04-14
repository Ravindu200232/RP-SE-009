from __future__ import annotations

from typing import Callable
import json
import os

from .models import PackageRequest


def consume_review_done(callback: Callable[[PackageRequest], None]) -> None:
    try:
        import pika
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install pika to enable RabbitMQ consumption.") from exc

    queue_name = os.getenv("AGENT4_REVIEW_QUEUE", "review_done")
    parameters = pika.URLParameters(os.getenv("AGENT4_RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"))
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)

    def handler(ch, method, properties, body):
        payload = json.loads(body.decode("utf-8"))
        callback(PackageRequest.from_dict(payload))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=handler)
    channel.start_consuming()

