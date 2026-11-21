from __future__ import annotations

import unittest
import base64
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from clipoteca.tray import WindowsTray, show_windows_notification


class TrayIconTests(unittest.TestCase):
    def test_brand_mark_is_transparent_and_uses_tray_dimensions(self) -> None:
        icon = WindowsTray._make_icon()

        self.assertEqual(icon.size, (64, 64))
        self.assertEqual(icon.mode, "RGBA")
        self.assertEqual(icon.getpixel((0, 0))[3], 0)
        self.assertGreater(icon.getbbox()[2], 0)

    def test_native_toast_uses_a_logo_and_passes_text_as_data(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("clipoteca.tray.app_data_dir", return_value=Path(directory)),
            patch("clipoteca.tray.subprocess.run") as run,
            patch.dict("os.environ", {"SystemRoot": "C:/Windows"}),
        ):
            message = 'Grabación & mezcla <día 2>\nArchivo «video».'
            show_windows_notification("Descarga completada", message)

            arguments = run.call_args.args[0]
            options = run.call_args.kwargs
            data = json.loads(base64.b64decode(options["input"]))
            self.assertEqual(data["message"], message)
            self.assertTrue(data["icon"].startswith("file:"))
            self.assertTrue((Path(directory) / "notifications" / "clipoteca.png").is_file())
            self.assertEqual(len(data["tag"]), 16)
            self.assertIn("-NonInteractive", arguments)
            script = base64.b64decode(arguments[-1]).decode("utf-16-le")
            self.assertIn("ToastGeneric", script)
            self.assertNotIn(message, script)


if __name__ == "__main__":
    unittest.main()
