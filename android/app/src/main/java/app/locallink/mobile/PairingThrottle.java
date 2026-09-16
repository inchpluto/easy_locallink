package app.locallink.mobile;

import org.json.JSONObject;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.function.DoubleSupplier;
import java.util.function.LongConsumer;

/**
 * Per source address cooldown for pairing-code attempts.
 *
 * Mirrors {@code locallink.core.PairingThrottle}: a 6 digit code is about 20
 * bits of entropy, so an unthrottled endpoint can be enumerated in seconds by
 * anything on the LAN.  Exactly {@code freeAttempts} wrong tries are compared
 * against the code; from then on the source owes an exponentially growing delay
 * and its attempts are refused without comparing the code at all.  Throttling
 * is keyed by source address so one guessing host cannot lock out another.
 */
final class PairingThrottle {
    private final int freeAttempts;
    private final double baseDelay;
    private final double maxDelay;
    private final double idleForget;
    private final DoubleSupplier clock;
    private final LongConsumer sleepMillis;
    private final Object lock = new Object();
    private final HashMap<String, long[]> failures = new HashMap<>();
    private int totalFailures;

    PairingThrottle() { this(5, 1.0, 60.0, 900.0, PairingThrottle::now, PairingThrottle::pause); }

    PairingThrottle(int freeAttempts, double baseDelay, double maxDelay, double idleForget,
                    DoubleSupplier clock, LongConsumer sleepMillis) {
        this.freeAttempts = Math.max(1, freeAttempts);
        this.baseDelay = Math.max(0.0, baseDelay);
        this.maxDelay = Math.max(this.baseDelay, maxDelay);
        this.idleForget = idleForget;
        this.clock = clock;
        this.sleepMillis = sleepMillis;
    }

    private static double now() { return System.nanoTime() / 1_000_000_000.0; }

    private static void pause(long millis) {
        try { Thread.sleep(millis); } catch (InterruptedException error) { Thread.currentThread().interrupt(); }
    }

    /** Seconds of cooldown owed by a source; 0 when it may still try. */
    int retryAfter(String source) {
        synchronized (lock) {
            double delay = delayFor(failures.get(source));
            return delay <= 0.0 ? 0 : Math.max(1, (int) (delay + 0.999));
        }
    }

    /** Sleep out the cooldown owed by this source. */
    void waitOut(String source) {
        long millis;
        synchronized (lock) {
            prune(clock.getAsDouble());
            millis = (long) (delayFor(failures.get(source)) * 1000.0);
        }
        if (millis > 0) sleepMillis.accept(millis);
    }

    void record(String source, boolean success) {
        synchronized (lock) {
            double now = clock.getAsDouble();
            if (success) { failures.remove(source); return; }
            long[] entry = failures.get(source);
            if (entry == null) { entry = new long[2]; failures.put(source, entry); }
            entry[0] += 1;
            entry[1] = (long) now;
            totalFailures += 1;
        }
    }

    JSONObject snapshot() {
        synchronized (lock) {
            int throttled = 0;
            for (long[] entry : failures.values()) if (delayFor(entry) > 0.0) throttled++;
            return new JSONObject()
                    .put("failed_attempts", totalFailures)
                    .put("throttled_sources", throttled);
        }
    }

    private double delayFor(long[] entry) {
        if (entry == null || entry[0] < freeAttempts) return 0.0;
        return Math.min(baseDelay * Math.pow(2.0, entry[0] - freeAttempts), maxDelay);
    }

    private void prune(double now) {
        Iterator<Map.Entry<String, long[]>> iterator = failures.entrySet().iterator();
        while (iterator.hasNext()) if (now - iterator.next().getValue()[1] > idleForget) iterator.remove();
    }
}
