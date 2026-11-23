"""Контракты сервисов из HLD 4.2. Ошибки операций передаются через AppError."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from contracts import (
    Alert,
    AlertCondition,
    AlertState,
    ConversionDirection,
    ConversionResult,
    DynamicsResult,
    HistoryDays,
    Quote,
    TriggerEvent,
)


class RateService(Protocol):
    async def get_current(self, pair_id: UUID) -> Quote: ...


class ConversionService(Protocol):
    async def convert(
        self, pair_id: UUID, direction: ConversionDirection, amount: Decimal
    ) -> ConversionResult: ...


class DynamicsService(Protocol):
    async def analyze(self, pair_id: UUID, days: HistoryDays) -> DynamicsResult: ...


class AlertService(Protocol):
    async def create(
        self, actor_id: UUID, pair_id: UUID, condition: AlertCondition, threshold: Decimal
    ) -> Alert: ...

    async def list(self, actor_id: UUID) -> Sequence[Alert]: ...

    async def set_active(self, actor_id: UUID, alert_id: UUID, active: bool) -> Alert: ...

    async def delete(self, actor_id: UUID, alert_id: UUID) -> None: ...


class AlertEvaluator(Protocol):
    def evaluate(
        self, state: AlertState, quote: Quote
    ) -> tuple[AlertState, TriggerEvent | None]:
        """Вычисляет новое состояние и событие без ввода-вывода."""
        ...
