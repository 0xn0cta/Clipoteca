from __future__ import annotations

from pathlib import Path

from PIL import Image


ICON_PATH = Path(__file__).resolve().parents[1] / "packaging" / "clipoteca.ico"


def test_packaged_windows_icon_contains_common_sizes() -> None:
    assert ICON_PATH.is_file()
    with Image.open(ICON_PATH) as icon:
        assert icon.format == "ICO"
        sizes = icon.info.get("sizes", set())
    assert {(16, 16), (32, 32), (48, 48), (256, 256)}.issubset(sizes)
