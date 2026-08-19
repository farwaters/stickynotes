#!/usr/bin/env python3
"""RFC-0.30: cork default, void skin, persist in VIEW.json."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve

OPEN = """# index
## [2026-08-18T10:00+02] ASK | sample-ask-note
- From: Alphane @ host
- Status: OPEN
- Body: live ask
"""


class Theme030(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.index = self.td / "NOTICE-BOARD.md"
        self.view = self.td / "VIEW.json"
        self.index.write_text(OPEN, encoding="utf-8")
        self.view.write_text("{}", encoding="utf-8")
        self._old = {k: os.environ.get(k) for k in ("NOTICE_BOARD_INDEX", "NOTICE_BOARD_VIEW")}
        os.environ["NOTICE_BOARD_INDEX"] = str(self.index)
        os.environ["NOTICE_BOARD_VIEW"] = str(self.view)

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_theme_cork(self):
        self.assertEqual(serve.normalize_theme(None), "cork")
        self.assertEqual(serve.normalize_theme("nope"), "cork")
        self.assertEqual(serve.board_payload()["theme"], "cork")

    def test_set_void_and_back(self):
        out = serve.apply_board_action("void", "theme")
        self.assertTrue(out.get("ok"))
        self.assertEqual(out["theme"], "void")
        saved = json.loads(self.view.read_text(encoding="utf-8"))
        self.assertEqual(saved["theme"], "void")
        self.assertEqual(serve.apply_board_action("cork", "theme")["theme"], "cork")

    def test_bad_theme_stays_cork(self):
        serve.apply_board_action("purple", "theme")
        self.assertEqual(serve.board_payload()["theme"], "cork")


if __name__ == "__main__":
    unittest.main()
