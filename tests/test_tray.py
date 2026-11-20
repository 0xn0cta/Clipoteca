from __future__ import annotations

import unittest

from clipoteca.tray import WindowsTray


class TrayIconTests(unittest.TestCase):
    def test_brand_mark_is_transparent_and_uses_tray_dimensions(self) -> None:
        icon = WindowsTray._make_icon()

        self.assertEqual(icon.size, (64, 64))
        self.assertEqual(icon.mode, "RGBA")
        self.assertEqual(icon.getpixel((0, 0))[3], 0)
        self.assertGreater(icon.getbbox()[2], 0)


if __name__ == "__main__":
    unittest.main()
