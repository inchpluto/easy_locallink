package app.locallink.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.function.DoubleSupplier;
import java.util.function.LongConsumer;

/** Mirrors tests/test_throttle.py: freeAttempts comparisons, then a growing cooldown. */
public class PairingThrottleTest {

    /** Deterministic clock that records the enforced delays instead of waiting. */
    private static final class FakeClock implements DoubleSupplier, LongConsumer {
        double now = 1000.0;
        final List<Long> sleeps = new ArrayList<>();

        @Override public double getAsDouble() { return now; }

        @Override public void accept(long millis) {
            sleeps.add(millis);
            now += millis / 1000.0;
        }
    }

    private static PairingThrottle throttle(FakeClock clock, int free, double base, double max) {
        return new PairingThrottle(free, base, max, 900.0, clock, clock);
    }

    @Test
    public void freeAttemptsAreNotDelayed() {
        FakeClock clock = new FakeClock();
        PairingThrottle throttle = throttle(clock, 3, 1.0, 60.0);

        for (int attempt = 0; attempt < 3; attempt++) {
            assertEquals(0, throttle.retryAfter("10.0.0.9"));
            throttle.record("10.0.0.9", false);
        }

        assertEquals(0, clock.sleeps.size());
        assertEquals(1, throttle.retryAfter("10.0.0.9"));
    }

    @Test
    public void delayDoublesAndCaps() {
        FakeClock clock = new FakeClock();
        PairingThrottle throttle = throttle(clock, 2, 0.25, 0.8);
        for (int attempt = 0; attempt < 2; attempt++) {
            throttle.waitOut("phone");
            throttle.record("phone", false);
        }

        long[] expected = {250L, 500L, 800L, 800L};
        for (long millis : expected) {
            throttle.waitOut("phone");
            throttle.record("phone", false);
        }

        assertEquals(expected.length, clock.sleeps.size());
        for (int index = 0; index < expected.length; index++) {
            assertEquals(expected[index], clock.sleeps.get(index).longValue());
        }
    }

    @Test
    public void throttlingIsScopedToOneSource() {
        FakeClock clock = new FakeClock();
        PairingThrottle throttle = throttle(clock, 1, 5.0, 60.0);
        assertEquals(0, throttle.retryAfter("attacker"));
        throttle.record("attacker", false);

        assertEquals(5, throttle.retryAfter("attacker"));
        // A different device on the LAN is never locked out by someone else.
        assertEquals(0, throttle.retryAfter("victim"));
    }

    @Test
    public void successClearsTheCounter() {
        FakeClock clock = new FakeClock();
        PairingThrottle throttle = throttle(clock, 1, 5.0, 60.0);
        for (int attempt = 0; attempt < 3; attempt++) {
            throttle.waitOut("phone");
            throttle.record("phone", false);
        }
        assertTrue(throttle.retryAfter("phone") > 0);

        throttle.record("phone", true);

        assertEquals(0, throttle.retryAfter("phone"));
        assertEquals(3, throttle.snapshot().optInt("failed_attempts"));
        assertEquals(0, throttle.snapshot().optInt("throttled_sources"));
    }

    @Test
    public void staleEntriesAreForgotten() {
        FakeClock clock = new FakeClock();
        PairingThrottle throttle = throttle(clock, 1, 5.0, 60.0);
        for (int attempt = 0; attempt < 3; attempt++) {
            throttle.waitOut("phone");
            throttle.record("phone", false);
        }
        assertTrue(throttle.retryAfter("phone") > 0);
        clock.now += 901.0;

        throttle.waitOut("phone");

        assertEquals(0, throttle.retryAfter("phone"));
        assertEquals(3, throttle.snapshot().optInt("failed_attempts"));
    }

    @Test
    public void retryAfterRoundsUpToWholeSeconds() {
        FakeClock clock = new FakeClock();
        PairingThrottle throttle = throttle(clock, 1, 0.4, 60.0);
        assertEquals(0, throttle.retryAfter("unknown-source"));
        throttle.record("phone", false);

        assertEquals(1, throttle.retryAfter("phone"));
    }
}
