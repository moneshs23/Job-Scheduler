from datetime import datetime, timedelta, timezone

from app.config.constants import (
    RETRY_STRATEGY_CUSTOM,
    RETRY_STRATEGY_EXPONENTIAL,
    RETRY_STRATEGY_FIXED,
    RETRY_STRATEGY_LINEAR,
)
from app.models.queue import RetryPolicy

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_MS = 1000
DEFAULT_MAX_DELAY_MS = 300_000
DEFAULT_MULTIPLIER = 2.0


def compute_delay_ms(policy: RetryPolicy | None, attempt_number: int) -> int:
    """attempt_number is 1-indexed: the delay before the Nth retry attempt."""
    if policy is None:
        base, max_delay, multiplier, strategy, custom = (
            DEFAULT_BASE_DELAY_MS,
            DEFAULT_MAX_DELAY_MS,
            DEFAULT_MULTIPLIER,
            RETRY_STRATEGY_EXPONENTIAL,
            None,
        )
    else:
        base, max_delay, multiplier, strategy, custom = (
            policy.base_delay_ms,
            policy.max_delay_ms,
            policy.multiplier,
            policy.strategy,
            policy.custom_delays,
        )

    if strategy == RETRY_STRATEGY_FIXED:
        delay = base
    elif strategy == RETRY_STRATEGY_LINEAR:
        delay = base * attempt_number
    elif strategy == RETRY_STRATEGY_CUSTOM and custom:
        idx = min(attempt_number - 1, len(custom) - 1)
        delay = custom[idx]
    else:  # exponential (default)
        delay = base * (multiplier ** (attempt_number - 1))

    return min(int(delay), max_delay)


def max_retries_for(policy: RetryPolicy | None) -> int:
    return policy.max_retries if policy is not None else DEFAULT_MAX_RETRIES


def next_retry_at(policy: RetryPolicy | None, attempt_number: int) -> datetime:
    delay_ms = compute_delay_ms(policy, attempt_number)
    return datetime.now(timezone.utc) + timedelta(milliseconds=delay_ms)
