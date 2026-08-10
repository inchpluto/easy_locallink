from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\33347\AppData\Local\Temp\codex-clipboard-8ec78335-d534-429c-8e34-81ed0faa46f0.png")
ASSETS = ROOT / "assets"


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    image = Image.open(SOURCE).convert("RGBA")
    image.save(ASSETS / "locallink-icon.png", optimize=True)
    image.save(
        ASSETS / "locallink.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    sizes = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    resources = ROOT / "android" / "app" / "src" / "main" / "res"
    for density, size in sizes.items():
        folder = resources / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        resized = image.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(folder / "ic_launcher.png", optimize=True)


if __name__ == "__main__":
    main()
