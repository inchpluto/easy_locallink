package app.locallink.mobile;

public final class ConnectionStateMachine {
    public enum State { IDLE, PROBING, AUTHENTICATING, READY, RETRUST_REQUIRED, FAILED }

    public static final class Result {
        public final State state;
        public final String error;
        Result(State state, String error) { this.state = state; this.error = error; }
    }

    private ConnectionStateMachine() {}

    public static Result classify(boolean reachable, String service, String observedId,
                                  int statusCode, String trustedId) {
        if (!reachable) return new Result(State.FAILED, "OFFLINE");
        if (!"locallink".equals(service)) return new Result(State.FAILED, "NOT_LOCALLINK");
        if (statusCode == 401) return new Result(State.FAILED, "PAIRING_REJECTED");
        if (statusCode < 200 || statusCode >= 300) return new Result(State.FAILED, "AUTH_FAILED");
        if (trustedId != null && !trustedId.isEmpty() && observedId != null
                && !observedId.isEmpty() && !trustedId.equals(observedId)) {
            return new Result(State.RETRUST_REQUIRED, "IDENTITY_CHANGED");
        }
        return new Result(State.READY, null);
    }
}
