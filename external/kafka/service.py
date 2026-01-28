"""Kafka service connector using confluent-kafka."""

import asyncio
import inspect
import json
from threading import Thread, Event
from typing import Callable, Optional, Dict, Any

from confluent_kafka import Producer, Consumer, KafkaException

from config.logging import get_logger
from config import Config

logger = get_logger()


class KafkaProducer:
    """Kafka Producer wrapper using confluent-kafka."""
    
    def __init__(
        self,
        bootstrap_servers: str = None,
        extra_producer_conf: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Kafka producer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
            extra_producer_conf: Additional producer configuration
        """
        bootstrap_servers = bootstrap_servers or Config.KAFKA_BROKERS
        
        pconf = {
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": True,
            "linger.ms": 5,
            "batch.size": 16384,
            "compression.type": "lz4",
            "acks": "all",
            "retries": 3,
            "delivery.timeout.ms": 30000,
        }
        
        if extra_producer_conf:
            pconf.update(extra_producer_conf)
        
        self.producer = Producer(pconf)
    
    def _delivery_report(self, err, msg):
        """Callback for delivery reports."""
        if err is not None:
            logger.error(
                f"[KafkaClient] Delivery failed: {err} | "
                f"topic={msg.topic()} partition={msg.partition()}"
            )
        else:
            logger.debug(
                f"[KafkaClient] Delivered to {msg.topic()} "
                f"[{msg.partition()}] @ {msg.offset()}"
            )
    
    def produce(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        serialize_json: bool = True,
    ):
        """
        Send a message to Kafka.
        
        Args:
            topic: Topic name
            value: Message value
            key: Optional message key
            headers: Optional message headers
            serialize_json: Whether to JSON serialize the value
        """
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
        """
        Flush producer buffer.
        
        Args:
            timeout: Maximum time to wait
        
        Returns:
            Number of messages still in queue
        """
        remaining = self.producer.flush(timeout)
        if remaining > 0:
            logger.warning(
                f"[KafkaClient] {remaining} messages still in queue after flush timeout"
            )
        return remaining
    
    def close(self):
        """Close producer and flush remaining messages."""
        self.flush()


class KafkaConsumer:
    """Kafka Consumer wrapper using confluent-kafka."""
    
    def __init__(
        self,
        bootstrap_servers: str = None,
        group_id: str = None,
        consumer_topics: list[str] = None,
        max_workers: int = 10,
        enable_auto_commit: bool = False,
        auto_offset_reset: str = "earliest",
        enable_auto_offset_store: bool = False,
        extra_consumer_conf: Optional[Dict[str, Any]] = None,
        asyncio_loop: asyncio.AbstractEventLoop = None,
    ):
        """
        Initialize Kafka consumer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers
            group_id: Consumer group ID
            consumer_topics: List of topics to consume
            max_workers: Maximum worker threads
            enable_auto_commit: Enable auto commit
            auto_offset_reset: Auto offset reset strategy
            enable_auto_offset_store: Enable auto offset store
            extra_consumer_conf: Additional consumer configuration
            asyncio_loop: Event loop for async handlers
        """
        bootstrap_servers = bootstrap_servers or Config.KAFKA_BROKERS
        group_id = group_id or Config.KAFKA_GROUP_ID
        
        self.consumer_topics = consumer_topics or []
        self._stop = Event()
        self._asyncio_loop = asyncio_loop
        self._on_message: Optional[Callable[..., bool]] = None
        
        cconf = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": enable_auto_commit,
            "enable.auto.offset.store": enable_auto_offset_store,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,
            "heartbeat.interval.ms": 10000,
            "fetch.min.bytes": 1,
            "fetch.wait.max.ms": 100,
        }
        
        if extra_consumer_conf:
            cconf.update(extra_consumer_conf)
        
        self.consumer = Consumer(cconf)
        self._thread: Optional[Thread] = None
    
    def start_consumer(
        self,
        on_message: Callable[[str, bytes, Dict[str, str], Dict[str, Any]], bool],
        poll_timeout: float = 1.0,
    ):
        """
        Start background consumer.
        
        Args:
            on_message: Message handler callback
            poll_timeout: Poll timeout in seconds
        """
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Consumer already running")
        
        self._on_message = on_message
        self.consumer.subscribe(self.consumer_topics)
        
        def _loop():
            try:
                while not self._stop.is_set():
                    msg = self.consumer.poll(poll_timeout)
                    if msg is None:
                        continue
                    if msg.error():
                        logger.error(f"[KafkaClient] Consumer error: {msg.error()}")
                        continue
                    
                    key = msg.key().decode("utf-8") if msg.key() else None
                    headers_raw = msg.headers() or []
                    headers = {
                        k: (v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v)
                        for k, v in headers_raw
                    }
                    
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
                            
                            # If handler is async, run it on the provided loop
                            if inspect.isawaitable(res):
                                if not self._asyncio_loop:
                                    raise RuntimeError(
                                        "Async handler provided but no asyncio_loop set"
                                    )
                                res = asyncio.run_coroutine_threadsafe(
                                    res, self._asyncio_loop
                                ).result()
                            
                            should_commit = bool(res)
                        
                        # Commit the message if handler returns True
                        if should_commit:
                            self.consumer.store_offsets(msg)
                            self.consumer.commit(message=msg, asynchronous=True)
                    
                    except Exception as e:
                        logger.exception(f"[KafkaClient] on_message error: {e}")
            
            except KafkaException as e:
                logger.exception(f"[KafkaClient] Kafka exception: {e}")
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
        """Stop the consumer thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
    
    def close(self):
        """Close consumer and stop background thread."""
        self.stop_consumer()
