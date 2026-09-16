# Stable Device Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent LocalLink upgrades and restarts from falsely blocking trusted Android connections while retaining explicit re-trust for genuine identity changes.

**Architecture:** Persist Python host IDs beside transfer data. Classify an authenticated identity mismatch as a recoverable state, then let Android update the trusted record only after an explicit confirmation.

**Tech Stack:** Python `pathlib/secrets`, Android Java, JUnit 4, Node assertions.

## Global Constraints

- Pairing-code authentication remains mandatory.
- Identity changes are never accepted silently.
- Existing trusted-device records remain readable.

---

### Task 1: Persistent Python host identity

**Files:** `tests/test_server.py`, `locallink/server.py`

- [ ] Add a test creating two servers over one data directory and assert literal ID equality.
- [ ] Run the test and verify it fails because the IDs differ.
- [ ] Add atomic `.device-id` loading/creation and pass the result to `LocalLinkServer`.
- [ ] Verify same-directory equality and different-directory inequality.

### Task 2: Recoverable identity transition

**Files:** `tests/connection_state.test.mjs`, `locallink/static/connection-state.js`, Android connection state tests and implementation.

- [ ] Change the expected authenticated mismatch to `retrust_required / IDENTITY_CHANGED` and verify RED.
- [ ] Add the state to both state machines and verify GREEN.

### Task 3: Android re-trust confirmation

**Files:** `android/app/src/main/java/app/locallink/mobile/MainActivity.java`

- [ ] On `RETRUST_REQUIRED`, show the old/new device warning only after authentication succeeds.
- [ ] Confirm updates the trusted ID and resumes the requested action; cancel leaves the record unchanged.
- [ ] Run Android unit tests and assemble the debug APK.

### Task 4: Full verification and packaging

- [ ] Run Python, Node and Android test suites.
- [ ] Rebuild Windows and Android 2.3 artifacts and refresh SHA-256 values.
