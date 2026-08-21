#!/usr/bin/env python3
"""Mechanical compact — no LLM. Run from scripts/: python3 test_housekeep.py"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load():
    spec = importlib.util.spec_from_file_location("housekeep", HERE / "housekeep.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["housekeep"] = mod
    spec.loader.exec_module(mod)
    return mod


TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 8, 21, 18, 0, tzinfo=TZ)


def post(ts: str, kind: str, slug: str, status: str, home: str = "/tmp/home.md") -> str:
    return (
        f"## [{ts}] {kind} | {slug}\n"
        f"- From: proj @ host\n"
        f"- Home: {home}\n"
        f"- Status: {status}\n"
        f"- Body: note\n"
    )


HEADER = "# NOTICE-BOARD\n\nCap: ≤40 OPEN.\n\n---\n\n"


class Housekeep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hk = load()

    def run_compact(self, body: str, now=NOW):
        return self.hk.compact(HEADER + body, now=now)

    def test_already_closed_status_is_archived(self):
        live, arch, st = self.run_compact(
            post("2026-08-21T10:00+02", "DONE", "already-done", "DONE")
            + post("2026-08-21T11:00+02", "WARN", "stay", "OPEN")
        )
        self.assertIn("| already-done", arch)
        self.assertNotIn("| already-done", live)
        self.assertIn("stay", live)
        self.assertTrue(st["changed"])

    def test_done_kind_open_is_archived(self):
        live, arch, st = self.run_compact(
            post("2026-08-21T10:00+02", "DONE", "finished-job", "OPEN")
        )
        self.assertEqual(st["archived"], 1)
        self.assertNotIn("finished-job", live)
        self.assertIn("finished-job", arch)
        self.assertIn("- Status: DONE", arch)

    def test_superseded_slug_closed(self):
        body = post("2026-08-20T10:00+02", "FIND", "same-slug", "OPEN") + "\n" + post(
            "2026-08-21T10:00+02", "DONE", "same-slug", "DONE"
        )
        live, arch, st = self.run_compact(body)
        self.assertEqual(st["live_open"], 0)
        self.assertIn("- Status: ANSWERED", arch)
        self.assertEqual(arch.count("same-slug"), 2)

    def test_stale_find_after_14d_warn_stays(self):
        old = (NOW - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M+02")
        fresh = NOW.strftime("%Y-%m-%dT%H:%M+02")
        body = post(old, "FIND", "old-find", "OPEN") + "\n" + post(
            old, "WARN", "standing-warn", "OPEN"
        ) + "\n" + post(fresh, "FIND", "new-find", "OPEN")
        live, arch, st = self.run_compact(body)
        self.assertIn("standing-warn", live)
        self.assertIn("new-find", live)
        self.assertIn("old-find", arch)
        self.assertIn("- Status: STALE", arch)

    def test_cap_archives_oldest_find_keeps_warn(self):
        parts = [post("2026-08-21T10:00+02", "WARN", "keep-warn", "OPEN")]
        for i in range(45):
            ts = f"2026-08-20T{i // 60:02d}:{i % 60:02d}+02"
            parts.append(post(ts, "FIND", f"find-{i:02d}", "OPEN"))
        live, arch, st = self.run_compact("\n".join(parts))
        self.assertLessEqual(st["live_open"], 40)
        self.assertIn("keep-warn", live)
        self.assertGreaterEqual(st["archived"], 6)

    def test_probe_slug_archived(self):
        live, arch, st = self.run_compact(
            post("2026-08-21T12:00+02", "FIND", "fly-probe-99", "OPEN")
        )
        self.assertIn("fly-probe-99", arch)
        self.assertNotIn("fly-probe-99", live.split("## [")[-1] if "## [" in live else live)
        self.assertEqual(st["live_open"], 0)

    def test_redact_keys_home(self):
        live, arch, st = self.run_compact(
            post(
                "2026-08-21T10:00+02",
                "WARN",
                "rotate-pw",
                "OPEN",
                home="/vault/05-Keys/secret.hosting",
            )
        )
        self.assertNotIn("05-Keys", live)
        self.assertIn("rotate-pw", live)
        self.assertIn("redacted", live.lower())

    def test_noop_second_pass(self):
        body = post("2026-08-21T10:00+02", "WARN", "only-warn", "OPEN")
        live1, arch1, st1 = self.run_compact(body)
        live2, arch2, st2 = self.hk.compact(live1, now=NOW)
        self.assertEqual(st2["archived"], 0)
        self.assertEqual(st2["changed"], False)
        self.assertEqual(arch2, "")

    def test_no_loss_counts(self):
        body = (
            post("2026-08-21T10:00+02", "DONE", "a", "OPEN")
            + post("2026-08-21T11:00+02", "FIND", "b", "OPEN")
            + post("2026-08-21T12:00+02", "WARN", "c", "OPEN")
        )
        live, arch, st = self.run_compact(body)
        n_live = live.count("## [")
        n_arch = arch.count("## [")
        self.assertEqual(n_live + n_arch, 3)


class HousekeepCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hk = load()

    def test_writes_archive_and_skips_backup_on_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "NOTICE-BOARD.md"
            arch = root / "notice-board"
            arch.mkdir()
            index.write_text(
                HEADER + post("2026-08-21T10:00+02", "WARN", "stay", "OPEN"),
                encoding="utf-8",
            )
            st = self.hk.run(index=index, arch_dir=arch, now=NOW, quiet=True)
            self.assertFalse(st["changed"])
            self.assertEqual(len(list(root.glob("*.bkp"))), 0)

    def test_cli_archives_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "NOTICE-BOARD.md"
            arch = root / "notice-board"
            arch.mkdir()
            index.write_text(
                HEADER
                + post("2026-08-21T10:00+02", "DONE", "job", "OPEN")
                + post("2026-08-21T11:00+02", "WARN", "stay", "OPEN"),
                encoding="utf-8",
            )
            st = self.hk.run(index=index, arch_dir=arch, now=NOW, quiet=True)
            self.assertTrue(st["changed"])
            live = index.read_text(encoding="utf-8")
            month = (arch / "2026-08.md").read_text(encoding="utf-8")
            self.assertIn("stay", live)
            self.assertNotIn("| job", live)
            self.assertIn("| job", month)
            self.assertTrue(list(root.glob("NOTICE-BOARD.md*.bkp")))


if __name__ == "__main__":
    unittest.main()
