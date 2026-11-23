from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from application import UtcClock, UuidGenerator
from contracts import Alert, AppError, ErrorCode, Quote


NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR_ID = UUID(int=1)


@pytest.mark.parametrize("price", ["0", "-0.01", "NaN", "Infinity"])
def test_quote_requires_positive_finite_price(price: str) -> None:
    with pytest.raises(ValueError, match="price"):
        Quote(PAIR_ID, Decimal(price), "test", NOW, NOW)


@pytest.mark.parametrize("naive_field", ["quoted_at", "received_at"])
def test_quote_requires_aware_timestamps(naive_field: str) -> None:
    naive = NOW.replace(tzinfo=None)
    quoted_at = naive if naive_field == "quoted_at" else NOW
    received_at = naive if naive_field == "received_at" else NOW
    with pytest.raises(ValueError, match="часовой пояс"):
        Quote(PAIR_ID, Decimal("0.00000001"), "test", quoted_at, received_at)


def test_new_alert_state() -> None:
    alert = Alert(UUID(int=2), UUID(int=3), PAIR_ID, "ge", Decimal("0.00000001"))
    assert alert.active and alert.last_match is None
    assert alert.last_quote_at is None and alert.trigger_seq == 0


def test_app_error_preserves_public_fields() -> None:
    correlation_id = UUID(int=4)
    with pytest.raises(AppError) as caught:
        raise AppError(
            ErrorCode.STALE_QUOTE, "Котировка устарела", retryable=True, correlation_id=correlation_id
        )
    error = caught.value
    assert error.code.value == "StaleQuote"
    assert error.user_message == str(error) == "Котировка устарела"
    assert error.retryable and error.correlation_id == correlation_id


def test_builtin_clock_and_id_generator() -> None:
    assert UtcClock().now().tzinfo is UTC
    assert UuidGenerator().next().version == 4
