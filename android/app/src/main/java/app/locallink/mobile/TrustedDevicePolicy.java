package app.locallink.mobile;

final class TrustedDevicePolicy {
    private TrustedDevicePolicy() {}

    static int matchScore(String savedHost, String savedId, String candidateHost, String candidateId) {
        if (notEmpty(savedId) && notEmpty(candidateId) && savedId.equals(candidateId)) return 2;
        if (notEmpty(savedHost) && savedHost.equals(candidateHost)) return 1;
        return 0;
    }

    static boolean sameRecord(String savedHost, String savedId, String candidateHost, String candidateId) {
        return matchScore(savedHost, savedId, candidateHost, candidateId) > 0;
    }

    static String preferredHost(String savedHost, String savedId, String discoveredId, String discoveredHost) {
        if (notEmpty(savedId) && savedId.equals(discoveredId) && notEmpty(discoveredHost)) return discoveredHost;
        return savedHost;
    }

    private static boolean notEmpty(String value) { return value != null && !value.isEmpty(); }
}
