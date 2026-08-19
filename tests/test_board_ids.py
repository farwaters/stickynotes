#!/usr/bin/env python3
"""Heading instances must keep distinct ids when slugs are reused."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from serve import classify_notes, parse_index

SAMPLE = """# index
## [2026-08-15T09:12+02] DONE | alphane-ep06-p6-008
- From: Alphane @ host
- Status: OPEN
- Body: newer done
## [2026-08-15T08:57+02] ASK | alphane-ep06-p6-008
- From: Alphane @ host
- Status: ANSWERED
- Body: mid answered
## [2026-08-15T08:34+02] ASK | alphane-ep06-p6-008
- From: Alphane @ host
- Status: OPEN
- Body: older ask still live
## [2026-08-15T09:12+02] ASK | alphane-ep06-p6-009
- From: Alphane @ host
- Status: OPEN
- Body: next 009
"""


class BoardIds(unittest.TestCase):
    def test_reused_slug_gets_distinct_stable_ids(self):
        a = parse_index(SAMPLE)
        b = parse_index(SAMPLE)
        eights = [n for n in a if n["slug"] == "alphane-ep06-p6-008"]
        self.assertEqual(len(eights), 3)
        ids = [n["id"] for n in eights]
        self.assertEqual(len(set(ids)), 3, "each heading is its own note")
        self.assertEqual([n["id"] for n in a], [n["id"] for n in b])

    def test_classify_keeps_every_heading_and_its_id(self):
        now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        out = classify_notes(parse_index(SAMPLE), {}, now)
        ids = [n["id"] for n in out]
        self.assertEqual(len(ids), len(set(ids)))
        by_body = {n["body"]: n for n in out}
        self.assertEqual(by_body["newer done"]["lane"], "pulled")
        self.assertEqual(by_body["mid answered"]["lane"], "pulled")
        self.assertEqual(by_body["older ask still live"]["lane"], "live")
        self.assertEqual(by_body["next 009"]["lane"], "live")

    def test_appended_heading_is_new_id_old_ids_hold(self):
        extra = SAMPLE + (
            "## [2026-08-15T11:10+02] ASK | appear-probe-note\n"
            "- Status: OPEN\n"
            "- Body: just posted\n"
        )
        before = {n["id"] for n in parse_index(SAMPLE)}
        after = parse_index(extra)
        ids = [n["id"] for n in after]
        self.assertIn("2026-08-15T11:10+02::appear-probe-note", ids)
        self.assertTrue(before.issubset(set(ids)))
        self.assertEqual(len(ids), len(before) + 1)

    def test_dashboard_live_includes_decide_learn_find(self):
        text = """
## [2026-08-15T11:16+02] DECIDE | alphane-shadow-board
- From: Alphane @ host
- Status: OPEN
- Body: shadow
## [2026-08-15T11:09+02] LEARN | notice-board-heading-ids
- From: GrokBuild @ host
- Status: OPEN
- Body: ids
## [2026-08-15T11:00+02] FIND | wiki-catalog
- From: GrokBuild @ host
- Status: OPEN
- Body: find
## [2026-08-15T10:00+02] DONE | old-done
- From: GrokBuild @ host
- Status: OPEN
- Body: done
"""
        out = classify_notes(
            parse_index(text), {}, datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        )
        lane = {n["slug"]: n["lane"] for n in out}
        self.assertEqual(lane["alphane-shadow-board"], "live")
        self.assertEqual(lane["notice-board-heading-ids"], "live")
        self.assertEqual(lane["wiki-catalog"], "live")
        self.assertEqual(lane["old-done"], "pulled")

    def test_slug_key_would_collapse_but_id_does_not(self):
        notes = classify_notes(
            parse_index(SAMPLE), {}, datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        )
        slug_store = {}
        id_store = {}
        for n in notes:
            slug_store[n["slug"]] = n["lane"]
            id_store[n["id"]] = n["lane"]
        self.assertEqual(len(slug_store), 2, "slug key hides heading instances")
        self.assertEqual(len(id_store), 4)


if __name__ == "__main__":
    unittest.main()
