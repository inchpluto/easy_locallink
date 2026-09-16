package app.locallink.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

public class MobileHostServerAssetTest {
    @Test public void servesTheCurrentWorkspaceStylesheet() {
        assertTrue(MobileHostServer.isBundledAsset("workspace.css"));
        assertTrue(MobileHostServer.isBundledAsset("index.html"));
        assertTrue(MobileHostServer.isBundledAsset("future-theme.css"));
        assertFalse(MobileHostServer.isBundledAsset("../workspace.css"));
        assertFalse(MobileHostServer.isBundledAsset("private.json"));
    }
}
