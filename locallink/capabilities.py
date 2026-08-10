from __future__ import annotations

import mimetypes
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".log", ".xml", ".html", ".htm", ".yaml", ".yml"}
WORD_EXTENSIONS = {".doc", ".docx", ".odt", ".rtf"}
SHEET_EXTENSIONS = {".xls", ".xlsx", ".ods"}
PRESENTATION_EXTENSIONS = {".ppt", ".pptx", ".odp"}
WINDOWS_INSTALLERS = {".exe", ".msi", ".msix", ".appx"}

APK_MIME = "application/vnd.android.package-archive"
WINDOWS_EXECUTABLE_MIMES = {
    "application/vnd.microsoft.portable-executable",
    "application/x-msdownload",
    "application/x-msi",
    "application/octet-stream",
}


def resolve_capabilities(
    filename: str,
    platform: str,
    converter_available: bool,
    sniffed_mime: str = "",
) -> dict:
    suffix = Path(filename).suffix.lower()
    guessed_mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    mime_type = sniffed_mime or guessed_mime
    platform = platform.lower()
    installable = False

    if suffix in IMAGE_EXTENSIONS:
        category, actions = "image", ["preview_inline", "download"]
    elif suffix in VIDEO_EXTENSIONS:
        category, actions = "video", ["preview_inline", "download"]
    elif suffix in AUDIO_EXTENSIONS:
        category, actions = "audio", ["preview_inline", "download"]
    elif suffix == ".pdf":
        category, actions = "pdf", ["preview_inline", "open_external", "download"]
    elif suffix in TEXT_EXTENSIONS:
        category, actions = "text", ["preview_inline", "open_external", "download"]
    elif suffix in WORD_EXTENSIONS:
        category = "document"
        actions = (["preview_convert"] if platform == "windows" and converter_available else []) + [
            "open_external",
            "download",
        ]
    elif suffix in SHEET_EXTENSIONS:
        category = "spreadsheet"
        actions = (["preview_convert"] if platform == "windows" and converter_available else []) + [
            "open_external",
            "download",
        ]
    elif suffix in PRESENTATION_EXTENSIONS:
        category = "presentation"
        actions = (["preview_convert"] if platform == "windows" and converter_available else []) + [
            "open_external",
            "download",
        ]
    elif suffix == ".apk":
        category = "android-package"
        installable = not sniffed_mime or sniffed_mime == APK_MIME
        actions = ["install", "download"] if platform == "android" and installable else ["download"]
        mime_type = APK_MIME if not sniffed_mime else sniffed_mime
    elif suffix in WINDOWS_INSTALLERS:
        category = "windows-installer"
        installable = not sniffed_mime or sniffed_mime in WINDOWS_EXECUTABLE_MIMES
        actions = ["open_external", "download"] if platform == "windows" and installable else ["download"]
    else:
        category, actions = "binary", ["download"]

    return {
        "mime_type": mime_type,
        "category": category,
        "actions": actions,
        "installable": installable,
    }
