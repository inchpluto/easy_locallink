# LocalLink Record Preview and Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship LocalLink 2.3 with overflow-safe transfer records, capability-driven previews and installers, and one consistent connection state machine across Windows, Android, and the shared web UI.

**Architecture:** Both hosts attach a common capability contract to transfer records. The web UI renders actions only from that contract, while small native bridges perform privileged open/install operations. Connection establishment is separated into address probing, LocalLink identity detection, pairing authentication, and ready state.

**Tech Stack:** Python 3.10+, `http.server`, PySide6/QWebChannel, HTML/CSS/vanilla JavaScript, Node built-in test runner, Android Java API 26–35, JUnit 4, Gradle, PyInstaller.

## Global Constraints

- Preserve LocalLink protocol v2 upload, download, discovery, and pairing compatibility.
- Do not upload files to cloud preview services.
- Office conversion is optional and Windows-only through a locally installed LibreOffice executable.
- Android Office viewing uses `ACTION_VIEW`; APK installation always requires Android system confirmation.
- Preview APIs accept record IDs, never arbitrary file paths.
- HTML and SVG previews must not execute active content.
- Office conversion limit is 200 MB and 60 seconds; text preview limit is 2 MB.
- Current workspace has no Git repository, so commit steps are replaced by test checkpoints recorded in this plan.

---

### Task 1: Python File Capability Contract

**Files:**
- Create: `locallink/capabilities.py`
- Modify: `locallink/core.py`
- Test: `tests/test_capabilities.py`

**Interfaces:**
- Produces: `resolve_capabilities(filename: str, platform: str, converter_available: bool, sniffed_mime: str = "") -> dict`
- Produces record fields: `mime_type`, `category`, `actions`, `installable`.

- [ ] **Step 1: Write the failing capability tests**

```python
from locallink.capabilities import resolve_capabilities

def test_office_actions_depend_on_host_capability():
    assert resolve_capabilities("slides.pptx", "windows", True)["actions"] == [
        "preview_convert", "open_external", "download"
    ]
    assert resolve_capabilities("slides.pptx", "android", False)["actions"] == [
        "open_external", "download"
    ]

def test_installers_are_platform_scoped():
    assert resolve_capabilities("release.apk", "android", False)["actions"] == ["install", "download"]
    assert resolve_capabilities("setup.exe", "windows", False)["actions"] == ["open_external", "download"]
    assert "install" not in resolve_capabilities("photo.jpg.exe", "android", False)["actions"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `D:\pycharm\venv\Scripts\python.exe -m pytest tests/test_capabilities.py -q`

Expected: collection fails because `locallink.capabilities` does not exist.

- [ ] **Step 3: Implement the minimal resolver**

Create immutable extension sets for image, media, text, PDF, Office, Android package, and Windows installer categories. Use `mimetypes.guess_type`, normalize suffixes to lowercase, reject installer actions when `sniffed_mime` contradicts the expected package type, and return literal ordered action arrays from the design.

- [ ] **Step 4: Add capability fields to real records**

Extend `TransferStore.list(platform="windows", converter_available=False)` to merge `resolve_capabilities(...)` into file records and return text records with `category="text"` and `actions=["preview_inline"]`.

- [ ] **Step 5: Verify GREEN and regression suite**

Run: `D:\pycharm\venv\Scripts\python.exe -m pytest tests/test_capabilities.py tests/test_core.py -q`

Expected: all selected tests pass.

---

### Task 2: Office Conversion and Safe Preview Service

**Files:**
- Create: `locallink/preview.py`
- Modify: `locallink/server.py`
- Modify: `locallink/core.py`
- Test: `tests/test_preview.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `OfficePreviewService(cache_dir: Path, converter: Path | None, timeout: int = 60, max_bytes: int = 209715200)`.
- Produces: `get_or_create(record: TransferRecord, source: Path) -> Path`.
- Server consumes `LocalLinkServer.preview_service` for `GET /api/preview/{id}?format=pdf`.

- [ ] **Step 1: Write a failing cache behavior test**

```python
from dataclasses import replace
from locallink.core import TransferRecord
from locallink.preview import OfficePreviewService

class FakeConverter:
    def __init__(self, pdf_bytes):
        self.pdf_bytes = pdf_bytes
        self.calls = 0

    def convert(self, source, output, profile_dir, timeout):
        self.calls += 1
        output.write_bytes(self.pdf_bytes)

def test_preview_cache_reuses_pdf_until_source_changes(tmp_path):
    converter = FakeConverter(pdf_bytes=b"%PDF-1.4\npreview")
    service = OfficePreviewService(tmp_path / "cache", converter=converter)
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"office")
    record = TransferRecord(
        id="record-1", kind="file", name="slides.pptx", size=source.stat().st_size,
        sha256="0" * 64, created_at=1.0, sender="Phone"
    )

    first = service.get_or_create(record, source)
    second = service.get_or_create(record, source)

    assert first.read_bytes() == b"%PDF-1.4\npreview"
    assert first == second
    assert converter.calls == 1
```

The fake converter must implement the same `convert(source, output, profile_dir, timeout)` boundary as the subprocess adapter; assertions target the real cache behavior rather than mock calls inside the service.

- [ ] **Step 2: Run test and verify RED**

Run: `D:\pycharm\venv\Scripts\python.exe -m pytest tests/test_preview.py -q`

Expected: import failure for `OfficePreviewService`.

- [ ] **Step 3: Implement converter discovery and cache**

Search standard LibreOffice installation paths and `PATH`. Execute with an isolated `-env:UserInstallation=file:///...` profile, `--headless`, `--safe-mode`, `--convert-to pdf`, and a fixed output directory. On timeout terminate the child process and remove the temporary profile. Cache filenames must include record ID, source size, and `st_mtime_ns`.

- [ ] **Step 4: Add preview endpoint tests**

```python
def test_office_preview_returns_cached_pdf(self):
    payload = b"fake-office"
    _, raw, _ = self.request(
        "/api/upload?code=123456", "POST", payload,
        {"X-Filename": "deck.pptx", "Content-Length": str(len(payload))},
    )
    item = json.loads(raw)["item"]
    self.server.preview_service = FakePreviewService(b"%PDF-1.4\nconverted")
    status, body, headers = self.request(
        f"/api/preview/{item['id']}?code=123456&format=pdf"
    )
    self.assertEqual(status, 200)
    self.assertEqual(headers["Content-Type"], "application/pdf")
    self.assertTrue(headers["Content-Disposition"].startswith("inline;"))
    self.assertEqual(body, b"%PDF-1.4\nconverted")
```

- [ ] **Step 5: Implement endpoint error mapping and cleanup**

Return JSON errors `PREVIEW_UNSUPPORTED` and `PREVIEW_CONVERSION_FAILED`. Add `TransferStore.delete` and `clear` hooks that remove files whose cache name begins with the deleted record ID. Text preview must stop after 2 MB and never render HTML as active markup.

- [ ] **Step 6: Verify GREEN**

Run: `D:\pycharm\venv\Scripts\python.exe -m pytest tests/test_preview.py tests/test_server.py -q`

Expected: all selected tests pass.

---

### Task 3: Testable Web View Models and Overflow-Safe Records

**Files:**
- Create: `locallink/static/ui-model.js`
- Create: `tests/web_ui.test.mjs`
- Modify: `locallink/static/index.html`
- Modify: `locallink/static/app.js`
- Modify: `locallink/static/style.css`

**Interfaces:**
- Produces global `LocalLinkUI.historyModel(item, hostDevice)`.
- Produces global `LocalLinkUI.connectionMessage(code, detail)`.
- Produces `renderTextReader(item)` and capability-driven action buttons in `app.js`.

- [ ] **Step 1: Write failing Node tests for long text and actions**

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import '../locallink/static/ui-model.js';

test('history model preserves long text without marking it as a filename', () => {
  const model = globalThis.LocalLinkUI.historyModel({
    id: '1', kind: 'text', text: '第一行\nhttps://example.com/' + 'a'.repeat(300),
    sender: 'Phone', receiver: 'PC', actions: ['preview_inline']
  }, 'PC');
  assert.equal(model.summary.includes('\n'), true);
  assert.deepEqual(model.actions, ['preview_inline']);
});

test('file actions come from the server contract', () => {
  const model = globalThis.LocalLinkUI.historyModel({
    id: '2', kind: 'file', name: 'slides.pptx', actions: ['preview_convert', 'download']
  }, 'PC');
  assert.deepEqual(model.actions, ['preview_convert', 'download']);
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test tests/web_ui.test.mjs`

Expected: module not found or `LocalLinkUI` undefined.

- [ ] **Step 3: Implement view model and render semantic record cards**

Move extension-independent presentation decisions into `ui-model.js`. In `app.js`, create DOM-safe text using `textContent`; do not interpolate untrusted text into attributes. Render text summary, route, metadata, and actions as separate regions.

- [ ] **Step 4: Implement responsive CSS**

Use `grid-template-columns:minmax(0,1fr) 230px 170px minmax(190px,auto)`. Apply `min-width:0` to `.payload`, `.payload-content`, `.history-item`, and route children. Use `white-space:pre-wrap`, `overflow-wrap:anywhere`, and `-webkit-line-clamp:3` for text summaries. At 1100px move metadata/actions to a second grid row; at 600px use one column. Buttons use `flex-wrap:wrap`.

- [ ] **Step 5: Add dedicated text reader**

The modal must render a `<pre class="text-reader">` with text nodes, linkify only `http:` and `https:` tokens through `document.createElement('a')`, and provide Copy and Save TXT buttons.

- [ ] **Step 6: Verify GREEN**

Run: `node --test tests/web_ui.test.mjs && node --check locallink/static/app.js`

Expected: Node tests and syntax check pass.

---

### Task 4: Shared Connection State Machine

**Files:**
- Create: `locallink/static/connection-state.js`
- Create: `tests/connection_state.test.mjs`
- Create: `android/app/src/main/java/app/locallink/mobile/ConnectionStateMachine.java`
- Create: `android/app/src/test/java/app/locallink/mobile/ConnectionStateMachineTest.java`
- Modify: `android/app/build.gradle`
- Modify: `android/app/src/main/java/app/locallink/mobile/MainActivity.java`

**Interfaces:**
- JavaScript: `LocalLinkConnection.classify(probeResult, statusResult, trustedDevice) -> {state, error}`.
- Java: `ConnectionStateMachine.Result classify(boolean reachable, String service, String observedId, int statusCode, String trustedId)` where `Result` exposes `State state` and nullable `String error`.

- [ ] **Step 1: Write failing JavaScript transition tests**

```javascript
test('identity change blocks a trusted connection', () => {
  const result = LocalLinkConnection.classify(
    {ok:true, service:'locallink', id:'new-id'}, {ok:true}, {id:'old-id'}
  );
  assert.deepEqual(result, {state:'failed', error:'IDENTITY_CHANGED'});
});

test('valid health and status reach ready', () => {
  const result = LocalLinkConnection.classify(
    {ok:true, service:'locallink', id:'same'}, {ok:true}, {id:'same'}
  );
  assert.deepEqual(result, {state:'ready', error:null});
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test tests/connection_state.test.mjs`

Expected: `LocalLinkConnection` undefined.

- [ ] **Step 3: Implement JavaScript state machine and UI state labels**

Expose only the exact design states and error codes. The sender header must display the authenticated device name and ID-derived trust state. Disable send controls outside `ready`.

- [ ] **Step 4: Write Android transition tests before Java implementation**

Add `testImplementation 'junit:junit:4.13.2'`. Test offline, non-LocalLink, pairing rejected, identity changed, and ready cases with literal expected enums.

- [ ] **Step 5: Run Android tests and verify RED**

Run from `android`: `gradle :app:testDebugUnitTest`

Expected: compilation fails because `ConnectionStateMachine` does not exist.

- [ ] **Step 6: Implement Java state machine and integrate MainActivity**

Replace the single preflight request with `/api/health` then authenticated `/api/status`. Persist trusted `device_id`, name, host, and code. Keep manual input after failures. For system shares, success opens a native result panel with Continue, View Records, and Devices actions.

- [ ] **Step 7: Verify GREEN**

Run: `gradle :app:testDebugUnitTest :app:assembleDebug`

Expected: unit tests and debug build pass.

---

### Task 5: Windows Native Open and Office Bridge

**Files:**
- Create: `locallink/native_bridge.py`
- Modify: `locallink/desktop.py`
- Modify: `locallink/static/app.js`
- Test: `tests/test_native_bridge.py`

**Interfaces:**
- Produces `NativeFileBridge.open_record(record_id: str) -> dict`.
- Produces `NativeFileBridge.reveal_record(record_id: str) -> dict`.
- Produces Qt slots exposed under WebChannel object name `localLinkNative`.

- [ ] **Step 1: Write failing path-safety test**

```python
def test_bridge_resolves_only_existing_store_records(tmp_path):
    store = TransferStore(tmp_path)
    bridge = NativeFileBridge(store, opener=lambda path: path)
    assert bridge.open_record("missing") == {"ok": False, "error": "FILE_NOT_FOUND"}
    assert not (tmp_path.parent / "secret.txt").exists()
```

- [ ] **Step 2: Run test and verify RED**

Run: `D:\pycharm\venv\Scripts\python.exe -m pytest tests/test_native_bridge.py -q`

Expected: import failure for `NativeFileBridge`.

- [ ] **Step 3: Implement bridge and QWebChannel integration**

Resolve IDs through `TransferStore.get/path_for`, check the resolved path remains below `store.files`, then call `QDesktopServices.openUrl`. Register the bridge with `QWebChannel` and inject `qwebchannel.js` only in the embedded desktop page. External browsers receive download-only actions.

- [ ] **Step 4: Verify GREEN**

Run: `D:\pycharm\venv\Scripts\python.exe -m pytest tests/test_native_bridge.py -q`

Expected: all bridge tests pass.

---

### Task 6: Android External Open and APK Installation

**Files:**
- Create: `android/app/src/main/java/app/locallink/mobile/NativeFileBridge.java`
- Create: `android/app/src/main/java/app/locallink/mobile/FileCapabilities.java`
- Create: `android/app/src/test/java/app/locallink/mobile/FileCapabilitiesTest.java`
- Create: `android/app/src/main/res/xml/file_paths.xml`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/src/main/java/app/locallink/mobile/MainActivity.java`
- Modify: `android/app/src/main/java/app/locallink/mobile/MobileHostServer.java`
- Modify: `locallink/static/app.js`

**Interfaces:**
- WebView object: `LocalLinkNative.openExternal(id)` and `LocalLinkNative.installApk(id)`.
- Native methods resolve record IDs inside `MobileHostServer`; JavaScript cannot supply filesystem paths.

- [ ] **Step 1: Add failing Android host capability unit cases**

```java
@Test public void androidOfficeUsesExternalViewer() {
    assertEquals(Arrays.asList("open_external", "download"),
        FileCapabilities.resolve("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document").actions);
}

@Test public void apkRequiresMatchingPackageMime() {
    assertEquals(Arrays.asList("install", "download"),
        FileCapabilities.resolve("release.apk", "application/vnd.android.package-archive").actions);
    assertFalse(FileCapabilities.resolve("photo.jpg.apk", "image/jpeg").actions.contains("install"));
}
```

- [ ] **Step 2: Run test and verify RED**

Run from `android`: `gradle :app:testDebugUnitTest`

Expected: test compilation fails because `FileCapabilities` does not exist.

- [ ] **Step 3: Implement Android capabilities, FileProvider, and bridge**

Implement the same ordered action contract as Python in `FileCapabilities.resolve(name, mime)`, then attach those fields in `MobileHostServer.historyJson()`. Declare `REQUEST_INSTALL_PACKAGES` and an unexported `FileProvider` with temporary read grants. For Office files, create a content URI and launch `ACTION_VIEW` with `FLAG_GRANT_READ_URI_PERMISSION`. Catch `ActivityNotFoundException` and report `NO_EXTERNAL_VIEWER` to the page.

- [ ] **Step 4: Implement explicit APK confirmation flow**

Read package name and version using `PackageManager.getPackageArchiveInfo`, show a native confirmation dialog containing filename, source device, size, and SHA-256 prefix, check `canRequestPackageInstalls()`, then route either to `ACTION_MANAGE_UNKNOWN_APP_SOURCES` or the system package installer. Never start this flow automatically after receipt.

- [ ] **Step 5: Verify GREEN and build**

Run from `android`: `gradle :app:testDebugUnitTest :app:assembleDebug`

Expected: tests pass and APK builds.

---

### Task 7: Integrated UI, Protocol Documentation, and Release

**Files:**
- Modify: `protocol/protocol.md`
- Modify: `README.md`
- Modify: `android/app/build.gradle`
- Modify: `LocalLink-v2.spec`
- Test: all test files above

**Interfaces:**
- Release version: Android `versionCode 7`, `versionName 2.3.0`, Windows directory name `LocalLink-2.3`.

- [ ] **Step 1: Run complete automated verification**

Run:

```powershell
D:\pycharm\venv\Scripts\python.exe -m pytest -q
node --test tests/*.test.mjs
node --check locallink/static/app.js
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

Expected: every suite passes without JavaScript errors or Python tracebacks.

- [ ] **Step 2: Perform browser visual verification**

At 1366×768 and 390×844, create records containing Chinese paragraphs, newlines, a 300-character URL, and an unbroken 300-character token. Confirm no horizontal overflow, summaries are three lines, action buttons wrap, and the full reader preserves content.

- [ ] **Step 3: Perform file behavior verification**

Transfer PNG, PDF, TXT, DOCX, PPTX, APK, and an unknown binary. Verify actions match capabilities. Run Windows once with LibreOffice available and once with converter path disabled. On Android verify Office opens through a compatible app or returns `NO_EXTERNAL_VIEWER`, and APK reaches the system confirmation page only after an explicit click.

- [ ] **Step 4: Perform connection verification**

Exercise PC→phone, phone→PC, and phone→phone. Verify offline, wrong pairing code, and identity-change messages. Verify Android share completion stays on the result screen.

- [ ] **Step 5: Update docs and version**

Document capability fields, preview endpoint, limits, native opening behavior, installation safety, and connection states. Change Android version to 2.3.0/code 7 and directory build name to `LocalLink-2.3`.

- [ ] **Step 6: Build release artifacts and hashes**

Run:

```powershell
D:\pycharm\venv\Scripts\python.exe -m PyInstaller --noconfirm --clean LocalLink-Portable.spec
D:\pycharm\venv\Scripts\python.exe -m PyInstaller --noconfirm LocalLink-v2.spec
```

Copy the Android debug APK to `dist\LocalLink-Android-2.3-debug.apk`, calculate SHA-256 for both EXE forms and APK, and verify APK badging reports version 2.3.0/code 7.
