package app.locallink.mobile;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public class ConnectionStateMachineTest {
    @Test public void offlineFails() {
        assertResult(false, "", "", 0, "", ConnectionStateMachine.State.FAILED, "OFFLINE");
    }

    @Test public void foreignServiceFails() {
        assertResult(true, "other", "id", 200, "", ConnectionStateMachine.State.FAILED, "NOT_LOCALLINK");
    }

    @Test public void pairingRejectedFails() {
        assertResult(true, "locallink", "id", 401, "", ConnectionStateMachine.State.FAILED, "PAIRING_REJECTED");
    }

    @Test public void authenticatedIdentityChangeRequiresRetrust() {
        assertResult(true, "locallink", "new", 200, "old", ConnectionStateMachine.State.RETRUST_REQUIRED, "IDENTITY_CHANGED");
    }

    @Test public void authenticatedLocalLinkIsReady() {
        assertResult(true, "locallink", "same", 200, "same", ConnectionStateMachine.State.READY, null);
    }

    private void assertResult(boolean reachable, String service, String observedId, int statusCode,
                              String trustedId, ConnectionStateMachine.State state, String error) {
        ConnectionStateMachine.Result result = ConnectionStateMachine.classify(
                reachable, service, observedId, statusCode, trustedId);
        assertEquals(state, result.state);
        assertEquals(error, result.error);
    }
}
