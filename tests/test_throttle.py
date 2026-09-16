import unittest

from locallink.core import PairingThrottle


class PairingThrottleTests(unittest.TestCase):
    """A 6 digit code must not be enumerable at request speed.

    Contract: ``free_attempts=N`` lets N wrong tries through untouched; try
    N+1 is the first throttled one and waits ``base_delay``, doubling each
    further failure up to ``max_delay``.
    """

    def test_free_attempts_are_not_delayed(self):
        clock = FakeClock()
        throttle = PairingThrottle(free_attempts=3, base_delay=1.0, clock=clock, sleep=clock.sleep)

        # Tries 1..3 are free; try 4 is the first throttled one.
        for _ in range(3):
            self.assertEqual(throttle.wait("10.0.0.9"), 0.0)
            self.assertEqual(throttle.retry_after("10.0.0.9"), 0)
            throttle.record("10.0.0.9", False)

        self.assertEqual(clock.sleep_calls, [])
        self.assertEqual(throttle.wait("10.0.0.9"), 1.0)

    def test_delay_doubles_and_caps(self):
        clock = FakeClock()
        throttle = PairingThrottle(
            free_attempts=2, base_delay=0.25, max_delay=0.8, clock=clock, sleep=clock.sleep
        )
        for _ in range(2):
            throttle.wait("phone")
            throttle.record("phone", False)
        # Attempts 3..6 owe 0.25, 0.5, 0.8, then stay capped at 0.8.
        expected = [0.25, 0.5, 0.8, 0.8]
        for delay in expected:
            self.assertEqual(throttle.wait("phone"), delay)
            throttle.record("phone", False)
        # wait() only sleeps when a cooldown is owed, so the two free attempts
        # leave no trace here.
        self.assertEqual(clock.sleep_calls, expected)

    def test_throttling_is_scoped_to_one_source(self):
        clock = FakeClock()
        throttle = PairingThrottle(free_attempts=1, base_delay=5.0, clock=clock, sleep=clock.sleep)
        # One free try, then the cooldown starts at base_delay.
        self.assertEqual(throttle.wait("attacker"), 0.0)
        throttle.record("attacker", False)

        self.assertEqual(throttle.wait("attacker"), 5.0)
        self.assertEqual(throttle.retry_after("attacker"), 5)
        # A different device on the LAN is never locked out by someone else.
        self.assertEqual(throttle.wait("victim"), 0.0)
        self.assertEqual(throttle.retry_after("victim"), 0)

    def test_success_clears_the_counter(self):
        clock = FakeClock()
        throttle = PairingThrottle(free_attempts=1, base_delay=5.0, clock=clock, sleep=clock.sleep)
        for _ in range(3):
            throttle.wait("phone")
            throttle.record("phone", False)
        self.assertGreater(throttle.retry_after("phone"), 0)

        throttle.record("phone", True)

        self.assertEqual(throttle.wait("phone"), 0.0)
        self.assertEqual(throttle.snapshot()["throttled_sources"], 0)
        self.assertEqual(throttle.snapshot()["failed_attempts"], 3)

    def test_stale_entries_are_forgotten(self):
        clock = FakeClock()
        throttle = PairingThrottle(
            free_attempts=1, base_delay=5.0, idle_forget=60.0, clock=clock, sleep=clock.sleep
        )
        for _ in range(3):
            throttle.wait("phone")
            throttle.record("phone", False)
        self.assertGreater(throttle.retry_after("phone"), 0)
        clock.now += 61.0

        self.assertEqual(throttle.wait("phone"), 0.0)
        self.assertEqual(throttle.snapshot()["throttled_sources"], 0)
        # The counter is lifetime observability, not throttle state.
        self.assertEqual(throttle.snapshot()["failed_attempts"], 3)

    def test_retry_after_rounds_up_to_whole_seconds(self):
        clock = FakeClock()
        throttle = PairingThrottle(free_attempts=1, base_delay=0.4, clock=clock, sleep=clock.sleep)
        for _ in range(2):
            throttle.wait("phone")
            throttle.record("phone", False)

        self.assertEqual(throttle.retry_after("phone"), 1)
        self.assertEqual(throttle.retry_after("unknown-source"), 0)


class FakeClock:
    """Monotonic clock stub that records the enforced delays instead of waiting."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleep_calls: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.now += seconds


if __name__ == "__main__":
    unittest.main()
