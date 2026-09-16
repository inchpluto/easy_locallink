package app.locallink.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class TrustedDevicePolicyTest {
    @Test public void stableIdMatchesAfterIpAddressChanges() {
        assertTrue(TrustedDevicePolicy.sameRecord(
                "192.168.1.20:53317", "pc-id",
                "192.168.1.82:53317", "pc-id"));
    }

    @Test public void recycledAddressIsReplacedAfterExplicitRetrust() {
        assertTrue(TrustedDevicePolicy.sameRecord(
                "192.168.1.82:53317", "old-id",
                "192.168.1.82:53317", "new-id"));
    }

    @Test public void deviceIdHasPriorityWhenSelectingPairingCode() {
        assertEquals(2, TrustedDevicePolicy.matchScore(
                "192.168.1.20:53317", "pc-id",
                "192.168.1.82:53317", "pc-id"));
        assertEquals(1, TrustedDevicePolicy.matchScore(
                "192.168.1.82:53317", "old-id",
                "192.168.1.82:53317", "new-id"));
    }

    @Test public void discoveryRefreshesOnlyTheSameDevicesAddress() {
        assertEquals("192.168.1.82:53317", TrustedDevicePolicy.preferredHost(
                "192.168.1.20:53317", "pc-id",
                "pc-id", "192.168.1.82:53317"));
        assertEquals("192.168.1.20:53317", TrustedDevicePolicy.preferredHost(
                "192.168.1.20:53317", "pc-id",
                "other-id", "192.168.1.82:53317"));
    }
}
