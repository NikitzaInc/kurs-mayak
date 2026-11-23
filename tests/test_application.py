from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import create_autospec
from uuid import UUID

import pytest

from application import Adapters, MarketServices, Services, build_application
from contracts import AssetPair, Quote, TriggerEvent
from ports import (
    Clock,
    DeliveryFailed,
    DeliveryUncertain,
    HistoryProvider,
    IdGenerator,
    Messenger,
    OpenUnitOfWork,
    QuoteProvider,
    Scheduler,
    UnitOfWork,
)
from services import AlertService, ConversionService, DynamicsService


PAIR = AssetPair(UUID(int=1), "BTC", "USD", "crypto")
QUOTED_AT = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeProvider:
    quote: Quote
    requests: list[tuple[AssetPair, ...]] = field(default_factory=list)

    async def get_batch(self, pairs: Sequence[AssetPair]) -> Sequence[Quote]:
        self.requests.append(tuple(pairs))
        return [self.quote]


@dataclass
class FrozenClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


@dataclass
class RecordingMessenger:
    sent: list[TriggerEvent] = field(default_factory=list)
    failure: DeliveryFailed | DeliveryUncertain | None = None

    async def send_alert(self, event: TriggerEvent) -> int:
        if self.failure is not None:
            raise self.failure
        self.sent.append(event)
        return len(self.sent)


@dataclass
class RecordingRateReader:
    provider: QuoteProvider
    clock: Clock
    checked_at: datetime | None = None

    async def get_current(self, pair_id: UUID) -> Quote:
        assert pair_id == PAIR.id
        self.checked_at = self.clock.now()
        (quote,) = await self.provider.get_batch([PAIR])
        return quote


@asynccontextmanager
async def memory_uow() -> AsyncIterator[UnitOfWork]:
    yield create_autospec(UnitOfWork, instance=True, spec_set=True)


@pytest.mark.asyncio
async def test_wires_provider_clock_and_delivery_into_modules() -> None:
    clock = FrozenClock(datetime(2026, 1, 1, 0, 2, tzinfo=UTC))
    provider = FakeProvider(Quote(PAIR.id, Decimal("81234.5678"), "test", QUOTED_AT, QUOTED_AT))
    messenger = RecordingMessenger()
    adapters = Adapters(
        quote_provider=provider,
        history_provider=create_autospec(HistoryProvider, instance=True, spec_set=True),
        open_uow=memory_uow,
        scheduler=create_autospec(Scheduler, instance=True, spec_set=True),
        messenger=messenger,
        clock=clock,
    )
    def market(source: QuoteProvider, open_uow: OpenUnitOfWork, time: Clock) -> MarketServices:
        assert open_uow is memory_uow
        reader = RecordingRateReader(source, time)
        return MarketServices(reader, create_autospec(ConversionService, instance=True))

    def dynamics(source: HistoryProvider, open_uow: OpenUnitOfWork, time: Clock) -> DynamicsService:
        assert (source, open_uow, time) == (adapters.history_provider, memory_uow, clock)
        service: DynamicsService = create_autospec(DynamicsService, instance=True)
        return service

    def alerts(open_uow: OpenUnitOfWork, ids: IdGenerator) -> AlertService:
        assert (open_uow, ids) == (memory_uow, adapters.ids)
        service: AlertService = create_autospec(AlertService, instance=True)
        return service

    def bot(services: Services, open_uow: OpenUnitOfWork, transport: Messenger) -> Services:
        assert (open_uow, transport) == (memory_uow, messenger)
        return services

    app = build_application(
        adapters,
        build_market=market,
        build_dynamics=dynamics,
        build_alerts=alerts,
        build_bot=bot,
        build_worker=lambda services, deps: (services, deps.messenger),
    )
    rates = app.bot.market.rates
    quote = await rates.get_current(PAIR.id)
    assert quote == provider.quote
    assert provider.requests == [(PAIR,)]
    assert isinstance(rates, RecordingRateReader)
    assert rates.checked_at == clock.value

    worker_services, worker_messenger = app.worker
    assert worker_services is app.bot
    event = TriggerEvent(
        id=UUID(int=2), alert_id=UUID(int=3), trigger_seq=1, pair=PAIR,
        price=quote.price, threshold=Decimal("81000"), condition="ge",
        detected_at=clock.value, quoted_at=quote.quoted_at, chat_id=42,
    )
    assert await worker_messenger.send_alert(event) == 1
    assert messenger.sent == [event]

    for failure in (DeliveryFailed(), DeliveryUncertain()):
        messenger.failure = failure
        with pytest.raises(type(failure)) as caught:
            await worker_messenger.send_alert(event)
        assert caught.value is failure
    assert messenger.sent == [event]
