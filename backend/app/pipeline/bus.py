"""Message bus between collectors and the NLP processor.

``KafkaBus`` uses Apache Kafka (aiokafka). ``MemoryBus`` is an asyncio queue
with the same interface so the system also runs on a laptop without Kafka.
"""

import asyncio
import json
import logging
import time

logger = logging.getLogger("brandshield.bus")


class MemoryBus:
    name = "memory"

    def __init__(self, maxsize: int = 50_000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self.published = 0

    async def start(self) -> None:
        logger.info("Using in-memory message bus")

    async def stop(self) -> None:
        pass

    async def publish(self, message: dict) -> None:
        await self._queue.put(message)
        self.published += 1

    def depth(self) -> int | None:
        return self._queue.qsize()

    async def batches(self, max_batch: int = 32, max_wait: float = 0.5):
        while True:
            first = await self._queue.get()
            batch = [first]
            deadline = time.monotonic() + max_wait
            while len(batch) < max_batch:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self._queue.get(), timeout=remaining))
                except TimeoutError:
                    break
            yield batch


class KafkaBus:
    name = "kafka"

    def __init__(self, bootstrap_servers: str, topic: str, group_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.published = 0
        self._producer = None
        self._consumer = None

    async def start(self) -> None:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            linger_ms=20,
        )
        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await asyncio.wait_for(self._producer.start(), timeout=10)
        await asyncio.wait_for(self._consumer.start(), timeout=10)
        logger.info("Connected to Kafka at %s (topic %s)", self.bootstrap_servers, self.topic)

    async def stop(self) -> None:
        for client in (self._consumer, self._producer):
            if client is not None:
                try:
                    await client.stop()
                except Exception:
                    pass

    async def publish(self, message: dict) -> None:
        await self._producer.send(self.topic, message)
        self.published += 1

    def depth(self) -> int | None:
        return None  # consumer lag is not tracked here

    async def batches(self, max_batch: int = 32, max_wait: float = 0.5):
        while True:
            records = await self._consumer.getmany(timeout_ms=int(max_wait * 1000), max_records=max_batch)
            batch = [r.value for msgs in records.values() for r in msgs]
            if batch:
                yield batch


async def create_bus(settings):
    if settings.bus_backend.lower() == "kafka":
        bus = KafkaBus(settings.kafka_bootstrap_servers, settings.kafka_topic_raw, settings.kafka_group_id)
        try:
            await bus.start()
            return bus
        except Exception as exc:
            logger.warning("Kafka unavailable (%s) - falling back to the in-memory bus", exc)
            await bus.stop()
    bus = MemoryBus()
    await bus.start()
    return bus
