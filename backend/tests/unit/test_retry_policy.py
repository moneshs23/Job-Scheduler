from app.models.queue import RetryPolicy
from app.retry.policy import compute_delay_ms, max_retries_for


def make_policy(**overrides) -> RetryPolicy:
    defaults = dict(
        strategy="exponential", max_retries=5, base_delay_ms=1000, max_delay_ms=300_000, multiplier=2.0,
        custom_delays=None,
    )
    defaults.update(overrides)
    return RetryPolicy(**defaults)


def test_exponential_backoff_doubles_each_attempt():
    policy = make_policy(strategy="exponential", base_delay_ms=1000, multiplier=2.0)
    assert compute_delay_ms(policy, 1) == 1000
    assert compute_delay_ms(policy, 2) == 2000
    assert compute_delay_ms(policy, 3) == 4000


def test_exponential_backoff_caps_at_max_delay():
    policy = make_policy(strategy="exponential", base_delay_ms=1000, multiplier=2.0, max_delay_ms=3000)
    assert compute_delay_ms(policy, 5) == 3000


def test_fixed_strategy_never_grows():
    policy = make_policy(strategy="fixed", base_delay_ms=500)
    assert compute_delay_ms(policy, 1) == 500
    assert compute_delay_ms(policy, 10) == 500


def test_linear_strategy_scales_with_attempt():
    policy = make_policy(strategy="linear", base_delay_ms=1000)
    assert compute_delay_ms(policy, 1) == 1000
    assert compute_delay_ms(policy, 3) == 3000


def test_custom_strategy_uses_explicit_delays():
    policy = make_policy(strategy="custom", custom_delays=[100, 500, 2000])
    assert compute_delay_ms(policy, 1) == 100
    assert compute_delay_ms(policy, 2) == 500
    assert compute_delay_ms(policy, 3) == 2000
    # Beyond the list, hold at the last configured delay.
    assert compute_delay_ms(policy, 10) == 2000


def test_no_policy_falls_back_to_defaults():
    assert compute_delay_ms(None, 1) == 1000
    assert max_retries_for(None) == 3
