import os
import asyncio, inspect
import json
from config.logging import get_logger

from confluent_kafka import Producer, Consumer, KafkaException
from threading import Thread, Event
from typing import Callable, Optional, Dict, Any
from utils.enums import *

logger = get_logger()

class KafkaProducer:
    def __init__(
        self,
        bootstrap_servers: str = os.getenv(SecretEnum.KAFKA_BOOTSTRAP_SERVERS.value),
        *,
        extra_producer_conf: Optional[Dict[str, Any]] = None,
    ):
        pconf = {
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": True,          # safe/ordered produce
            "linger.ms": 5,                      # Small batch delay for better throughput
            "batch.size": 16384,                 # 16KB batch size
            "compression.type": "lz4",
            "acks": "all",                       # Must be 'all' when idempotence is enabled
            "retries": 3,                        # Retry failed sends
            "delivery.timeout.ms": 30000,        # 30 second timeout
        }
        if extra_producer_conf:
            pconf.update(extra_producer_conf)
        self.producer = Producer(pconf)

    # ---------- Producer ----------
    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"[KafkaClient] Delivery failed: {err} | topic={msg.topic()} partition={msg.partition()}")
            # Could implement retry logic here or dead letter queue
        else:
            logger.debug(
                "[KafkaClient] Delivered to %s [%d] @ %d",
                msg.topic(), msg.partition(), msg.offset(),
            )

    def produce(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        serialize_json: bool = True,
    ):
        """Send a message. If serialize_json=True, value is json-dumped."""
        payload = json.dumps(value).encode("utf-8") if serialize_json else value
        self.producer.produce(
            topic=topic,
            value=payload,
            key=key.encode("utf-8") if isinstance(key, str) else key,
            headers=[(k, v.encode("utf-8")) for k, v in (headers or {}).items()],
            callback=self._delivery_report,
        )
        # Poll to serve delivery callbacks - non-blocking
        self.producer.poll(0)

    def flush(self, timeout: float = 10.0):
        """Flush producer buffer to ensure all messages are sent."""
        remaining = self.producer.flush(timeout)
        if remaining > 0:
            logger.warning(f"[KafkaClient] {remaining} messages still in queue after flush timeout")
        return remaining

    def get_producer_queue_size(self) -> int:
        """Get the number of messages waiting in the producer queue."""
        return len(self.producer)

    def get_producer_metrics(self) -> dict:
        """Get producer performance metrics."""
        try:
            metrics = self.producer.list_topics(timeout=1)
            return {
                "queue_size": len(self.producer),
                "topics_metadata": len(metrics.topics) if metrics else 0,
            }
        except Exception as e:
            logger.warning(f"Failed to get producer metrics: {e}")
            return {"queue_size": len(self.producer), "error": str(e)}

    def close(self):
        """Close producer and flush remaining messages"""
        self.flush()


class KafkaConsumer:
    def __init__(
        self,
        bootstrap_servers: str = os.getenv(SecretEnum.KAFKA_BOOTSTRAP_SERVERS.value),
        group_id: str = os.getenv(SecretEnum.KAFKA_GROUP_ID.value),   
        consumer_topics: list[str] = None,
        *,
        enable_auto_commit: bool = False,
        auto_offset_reset: str = "earliest",
        enable_auto_offset_store: bool = False,
        extra_consumer_conf: Optional[Dict[str, Any]] = None,
        asyncio_loop: asyncio.AbstractEventLoop | None = None,
    ):
        self.consumer_topics = consumer_topics or []
        self._stop = Event()
        
        cconf = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": enable_auto_commit,
            "enable.auto.offset.store": enable_auto_offset_store,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,         # Faster session timeout
            "heartbeat.interval.ms": 10000,      # More frequent heartbeats
            "fetch.min.bytes": 1,                # Don't wait for large batches
            "fetch.wait.max.ms": 100,            # Small wait time for low latency
        }

        if extra_consumer_conf:
            cconf.update(extra_consumer_conf)

        self.consumer = Consumer(cconf)
        self._thread: Optional[Thread] = None
        self._on_message: Optional[Callable[..., bool]] = None  # return True to commit
        self._asyncio_loop = asyncio_loop

    # ---------- Consumer ----------
    def start_consumer(
        self,
        on_message: Callable[[str, bytes, Dict[str, str], Dict[str, Any]], bool],
        poll_timeout: float = 1.0,
    ):
        """
        Start background consumer. on_message(key, value_bytes, headers, meta) -> bool
        Return True to commit the message, False to skip (or when auto-commit is on, return value is ignored).
        """
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Consumer already running")

        self._on_message = on_message
        self.consumer.subscribe(self.consumer_topics)

        def _loop():
            logger.debug("[KafkaClient] Consumer started, subscribed to %s", self.consumer_topics)
            try:
                while not self._stop.is_set():
                    msg = self.consumer.poll(poll_timeout)
                    if msg is None:
                        continue
                    if msg.error():
                        logger.error("[KafkaClient] Consumer error: %s", msg.error())
                        continue

                    key = msg.key().decode("utf-8") if msg.key() else None
                    headers_raw = msg.headers() or []
                    headers = {k: (v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v)
                               for k, v in headers_raw}

                    meta = {
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                        "timestamp": msg.timestamp(),
                    }

                    try:
                        should_commit = True
                        if self._on_message:
                            res = self._on_message(key, msg.value(), headers, meta)

                            # If handler is async, run it on the provided loop and wait for result
                            if inspect.isawaitable(res):
                                if not self._asyncio_loop:
                                    raise RuntimeError("Async handler provided but no asyncio_loop set")
                                res = asyncio.run_coroutine_threadsafe(res, self._asyncio_loop).result()

                            should_commit = bool(res)

                        # Commit the message and store the offsets after message is processed
                        if should_commit:
                            self.consumer.store_offsets(msg)
                            self.consumer.commit(message=msg, asynchronous=True)

                    except Exception as e:
                        # Don't crash the loop on user callback errors
                        logger.exception("[KafkaClient] on_message error: %s", e)
            except KafkaException as e:
                logger.exception("[KafkaClient] Kafka exception: %s", e)
            finally:
                try:
                    self.consumer.close()
                except Exception:
                    pass
                logger.debug("[KafkaClient] Consumer stopped")

        self._stop.clear()
        self._thread = Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_consumer(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def close(self):
        """Close consumer and stop background thread"""
        self.stop_consumer()