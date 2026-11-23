"""Сборка сервисов, Telegram-бота и фонового обработчика."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ports import (
    Clock,
    HistoryProvider,
    IdGenerator,
    Messenger,
    OpenUnitOfWork,
    QuoteProvider,
    Scheduler,
)
from services import AlertService, ConversionService, DynamicsService, RateService


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidGenerator:
    def next(self) -> UUID:
        return uuid4()


@dataclass(frozen=True, slots=True)
class Adapters:
    quote_provider: QuoteProvider
    history_provider: HistoryProvider
    open_uow: OpenUnitOfWork
    scheduler: Scheduler
    messenger: Messenger
    clock: Clock = field(default_factory=UtcClock)
    ids: IdGenerator = field(default_factory=UuidGenerator)


@dataclass(frozen=True, slots=True)
class MarketServices:
    rates: RateService
    conversion: ConversionService


@dataclass(frozen=True, slots=True)
class Services:
    market: MarketServices
    dynamics: DynamicsService
    alerts: AlertService


@dataclass(frozen=True, slots=True)
class Application[Bot, Worker]:
    bot: Bot
    worker: Worker


def build_application[Bot, Worker](
    adapters: Adapters,
    *,
    build_market: Callable[[QuoteProvider, OpenUnitOfWork, Clock], MarketServices],
    build_dynamics: Callable[[HistoryProvider, OpenUnitOfWork, Clock], DynamicsService],
    build_alerts: Callable[[OpenUnitOfWork, IdGenerator], AlertService],
    build_bot: Callable[[Services, OpenUnitOfWork, Messenger], Bot],
    build_worker: Callable[[Services, Adapters], Worker],
) -> Application[Bot, Worker]:
    """Фабрики получают зависимости явно. Сборка не запускает опрос или доставку."""
    services = Services(
        market=build_market(adapters.quote_provider, adapters.open_uow, adapters.clock),
        dynamics=build_dynamics(adapters.history_provider, adapters.open_uow, adapters.clock),
        alerts=build_alerts(adapters.open_uow, adapters.ids),
    )
    return Application(
        bot=build_bot(services, adapters.open_uow, adapters.messenger),
        worker=build_worker(services, adapters),
    )
