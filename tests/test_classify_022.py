#!/usr/bin/env python3
"""RFC-0.22: gutter, discard, restick, hide, hex-off-bar, 4h afterglow."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)

OPEN = """# index
## [2026-08-18T10:00+02] ASK | sample-ask-note
- From: Redwood @ host
- Status: OPEN
- Scope: cross
- Body: live ask
## [2026-08-18T09:00+02] DONE | sample-done-note
- From: Redwood @ host
- Status: OPEN
- Body: agent closed
## [2026-08-18T08:00+02] ASK | hex-from-chat
- From: 01a0116b @ host
- Chat: 01a0116b
- Status: OPEN
- Scope: chat
- Body: notice-board only
## [2026-08-18T07:00+02] DECIDE | other-open
- From: Beacon @ host
- Status: OPEN
- Body: other live
"""


def _notes(view=None):
    return serve.classify_notes(serve.parse_index(OPEN), view or {}, NOW)


class Classify022(unittest.TestCase):
    def test_user_guttered_is_gutter_not_pulled(self):
        out = _notes({"guttered": {"sample-ask-note": NOW.isoformat()}})
        by = {n["slug"]: n for n in out}
        self.assertEqual(by["sample-ask-note"]["lane"], "gutter")
        self.assertEqual(by["sample-done-note"]["lane"], "pulled")

    def test_legacy_peeled_aliases_gutter(self):
        out = _notes({"peeled": {"sample-ask-note": NOW.isoformat()}})
        by = {n["slug"]: n for n in out}
        self.assertEqual(by["sample-ask-note"]["lane"], "gutter")

    def test_agent_done_stays_pulled_even_if_guttered(self):
        out = _notes({"guttered": {"sample-done-note": NOW.isoformat()}})
        by = {n["slug"]: n for n in out}
        self.assertEqual(by["sample-done-note"]["lane"], "pulled")

    def test_discarded_slug_omitted(self):
        out = _notes({"discarded": {"sample-ask-note": NOW.isoformat()}})
        slugs = {n["slug"] for n in out}
        self.assertNotIn("sample-ask-note", slugs)
        self.assertIn("sample-done-note", slugs)

    def test_hex_project_not_on_active_bar(self):
        projects = serve.active_projects(_notes({}), {}, NOW)
        self.assertIn("Redwood", projects)
        self.assertIn("Beacon", projects)
        self.assertNotIn("01a0116b", projects)
        self.assertFalse(any(p.startswith("chat:") for p in projects))

    def test_afterglow_4h_keeps_project_5h_drops(self):
        parked = _notes({"parked": {"sample-ask-note": NOW.isoformat()}})
        glow_ok = {"afterglow": {"Redwood": (NOW - timedelta(hours=3, minutes=50)).isoformat()}}
        glow_old = {"afterglow": {"Redwood": (NOW - timedelta(hours=5)).isoformat()}}
        # no live Redwood (ask is parked); Beacon still live
        self.assertIn("Redwood", serve.active_projects(parked, glow_ok, NOW))
        self.assertNotIn("Redwood", serve.active_projects(parked, glow_old, NOW))
        self.assertIn("Beacon", serve.active_projects(parked, glow_old, NOW))

    def test_hidden_project_leaves_the_bar(self):
        view = {"hidden_projects": {"Redwood": NOW.isoformat()}}
        projects = serve.active_projects(_notes(view), view, NOW)
        self.assertNotIn("Redwood", projects)
        self.assertIn("Beacon", projects)

    def test_is_hex_chat(self):
        self.assertTrue(serve.is_hex_chat("01a0116b"))
        self.assertTrue(serve.is_hex_chat("chat:01a0116b"))
        self.assertTrue(serve.is_hex_chat("01a01164-ee71-7380-859f-fe7cc1daa582"))
        self.assertFalse(serve.is_hex_chat("Redwood"))
        self.assertFalse(serve.is_hex_chat("stickynote"))


class Actions022(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.index = self.td / "NOTICE-BOARD.md"
        self.view = self.td / "VIEW.json"
        self.index.write_text(OPEN, encoding="utf-8")
        self.view.write_text(
            json.dumps({"peeled": {}, "parked": {}, "pinned": {}}), encoding="utf-8"
        )
        self._old = {
            k: os.environ.get(k)
            for k in ("NOTICE_BOARD_INDEX", "NOTICE_BOARD_VIEW")
        }
        os.environ["NOTICE_BOARD_INDEX"] = str(self.index)
        os.environ["NOTICE_BOARD_VIEW"] = str(self.view)

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_peel_puts_ask_in_gutter(self):
        r = serve.apply_board_action("sample-ask-note", "peel")
        self.assertTrue(r.get("ok"))
        by = {n["slug"]: n for n in r["notes"]}
        self.assertEqual(by["sample-ask-note"]["lane"], "gutter")
        self.assertIn("Redwood", r["projects"])

    def test_restick_appends_heading_and_returns_live(self):
        serve.apply_board_action("sample-ask-note", "peel")
        before = self.index.read_text(encoding="utf-8").count("## [")
        r = serve.apply_board_action("sample-ask-note", "restick")
        self.assertTrue(r.get("ok"))
        after = self.index.read_text(encoding="utf-8")
        self.assertEqual(after.count("## ["), before + 1)
        live = [n for n in r["notes"] if n["slug"] == "sample-ask-note" and n["lane"] == "live"]
        self.assertTrue(live)
        self.assertFalse(any(n["lane"] == "gutter" and n["slug"] == "sample-ask-note" for n in r["notes"]))

    def test_restick_rejects_agent_done(self):
        r = serve.apply_board_action("sample-done-note", "restick")
        self.assertFalse(r.get("ok"))

    def test_discard_omits_after_reload(self):
        serve.apply_board_action("sample-ask-note", "peel")
        r = serve.apply_board_action("sample-ask-note", "discard")
        slugs = {n["slug"] for n in r["notes"]}
        self.assertNotIn("sample-ask-note", slugs)

    def test_hide_project_drops_chip(self):
        r = serve.apply_board_action("Redwood", "hide")
        self.assertTrue(r.get("ok"))
        self.assertNotIn("Redwood", r["projects"])
        self.assertIn("Beacon", r["projects"])


if __name__ == "__main__":
    unittest.main()
