from locallink.capabilities import resolve_capabilities


def test_office_actions_depend_on_host_platform_and_converter():
    assert resolve_capabilities("slides.pptx", "windows", True)["actions"] == [
        "preview_convert",
        "open_external",
        "download",
    ]
    assert resolve_capabilities("slides.pptx", "windows", False)["actions"] == [
        "open_external",
        "download",
    ]
    assert resolve_capabilities("slides.pptx", "android", False)["actions"] == [
        "open_external",
        "download",
    ]


def test_browser_native_types_are_previewable():
    image = resolve_capabilities("photo.JPG", "windows", False)
    text = resolve_capabilities("notes.md", "android", False)
    assert image["category"] == "image"
    assert image["actions"] == ["preview_inline", "download"]
    assert text["category"] == "text"
    assert text["actions"] == ["preview_inline", "open_external", "download"]


def test_installers_are_platform_scoped():
    apk = resolve_capabilities(
        "release.apk", "android", False, "application/vnd.android.package-archive"
    )
    windows = resolve_capabilities(
        "setup.exe", "windows", False, "application/vnd.microsoft.portable-executable"
    )
    assert apk["actions"] == ["install", "download"]
    assert apk["installable"] is True
    assert windows["actions"] == ["open_external", "download"]
    assert windows["installable"] is True


def test_mime_mismatch_suppresses_install_action():
    disguised = resolve_capabilities("photo.jpg.apk", "android", False, "image/jpeg")
    assert "install" not in disguised["actions"]
    assert disguised["installable"] is False


def test_unknown_binary_is_download_only():
    result = resolve_capabilities("archive.unknown", "windows", True)
    assert result["category"] == "binary"
    assert result["actions"] == ["download"]
