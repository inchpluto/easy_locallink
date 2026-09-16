package app.locallink.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import java.util.Arrays;
import org.junit.Test;

public class FileCapabilitiesTest {
    @Test public void androidOfficeUsesExternalViewer() {
        FileCapabilities.Result result = FileCapabilities.resolve("report.docx", "");
        assertEquals(Arrays.asList("open_external", "download"), result.actions);
        assertEquals("application/vnd.openxmlformats-officedocument.wordprocessingml.document", result.mimeType);
    }

    @Test public void apkCanReachSystemInstaller() {
        FileCapabilities.Result result = FileCapabilities.resolve("LocalLink.apk", "application/vnd.android.package-archive");
        assertEquals(Arrays.asList("install", "download"), result.actions);
        assertTrue(result.installable);
    }

    @Test public void mismatchedApkMimeIsDownloadOnly() {
        FileCapabilities.Result result = FileCapabilities.resolve("fake.apk", "text/plain");
        assertEquals(Arrays.asList("download"), result.actions);
        assertFalse(result.installable);
    }

    @Test public void imagePreviewsInline() {
        assertEquals(Arrays.asList("preview_inline", "download"),
                FileCapabilities.resolve("photo.jpg", "image/jpeg").actions);
    }
}
