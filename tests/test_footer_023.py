#!/usr/bin/env python3
"""RFC-0.23: VERSION is stamped into board and cockpit HTML."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve


class Footer023(unittest.TestCase):
    def test_read_version_first_line(self):
        ver = serve.read_version()
        self.assertTrue(ver.startswith("v"), ver)

    def test_board_html_has_placeholder(self):
        html = Path(serve.ROOT / "board.html").read_text(encoding="utf-8")
        self.assertIn("__VERSION__", html)

    def test_stamp_replaces_placeholder(self):
        stamped = serve.stamp_html("x __VERSION__ y")
        self.assertNotIn("__VERSION__", stamped)
        self.assertIn(serve.read_version(), stamped)

    def test_board_page_contains_version(self):
        body = serve.page_bytes(serve.BOARD_HTML).decode("utf-8")
        self.assertIn(serve.read_version(), body)
        self.assertNotIn("__VERSION__", body)


if __name__ == "__main__":
    unittest.main()
