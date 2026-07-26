"""In-process domain event bus (port + default adapter).

Modules publish events without knowing who subscribes. Swapping this for
Postgres LISTEN/NOTIFY or Redis pub/sub later is a container.py change, not a
refactor -- every module only ever depends on the EventBus port below.
"""

import abc
import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base for all domain events. Payloads must stay IDs + metadata -- events flow
    into the audit log verbatim, so never put clinical text or PII in a payload."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    care_home_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None


EventHandler = Callable[[DomainEvent], Awaitable[None]]
TEvent = TypeVar("TEvent", bound=DomainEvent)


class EventBus(abc.ABC):
    @abc.abstractmethod
    def subscribe(self, event_type: type[TEvent], handler: Callable[[TEvent], Awaitable[None]]) -> None:
        """Each call is typed to the specific event subclass being subscribed to, even
        though storage below is keyed generically -- callers never have to cast their
        handler's parameter type to DomainEvent."""
        ...

    @abc.abstractmethod
    async def publish(self, event: DomainEvent) -> None: ...


class InMemoryEventBus(EventBus):
    """Phase 1 default adapter. Handlers run concurrently and errors are logged, not
    raised, so a broken subscriber (e.g. audit) never blocks the publisher's request."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[TEvent], handler: Callable[[TEvent], Awaitable[None]]) -> None:
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(type(event), [])
        results = await asyncio.gather(*(h(event) for h in handlers), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                # TODO: route through telemetry.py once structured logging is wired up.
                print(f"[event_bus] handler failed for {type(event).__name__}: {result!r}")
