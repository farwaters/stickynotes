#!/usr/bin/env python3
"""Mechanical notice-board compact. 0 LLM tokens. Invoked by board.sh ensure/summary."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CAP = 40
STALE_DAYS = 14
KEEP_KINDS = frozenset({"ASK", "WARN", "BLOCK", "LOCK"})
CLOSED = frozenset({"ANSWERED", "RESOLVED", "STALE", "DONE"})
HEAD_RE = re.compile(r"^## \[([^\]]+)\]\s+(\S+)\s+\|\s+(\S+)\s*$", re.M)
PROBE_RE = re.compile(r"(?:^|-)(?:fly-)?probe(?:-|$)", re.I)
KEYS_RE = re.compile(r"^- Home:.*05-Keys.*$", re.M)
STATUS_RE = re.compile(r"^- Status:\s*\S+", re.M)

TZ2 = timezone(timedelta(hours=2))


@dataclass
class Post:
    raw: str
    ts: str
    kind: str
    slug: str
    status: str
    dt: datetime | None


def parse_ts(ts: str) -> datetime | None:
    raw = (ts or "").strip()
    if re.search(r"[+-]\d{2}$", raw):
        raw += ":00"
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def split_index(text: str) -> tuple[str, list[Post]]:
    parts = re.split(r"(?=^## \[)", text, flags=re.M)
    header = parts[0]
    posts: list[Post] = []
    for raw in parts[1:]:
        if not raw.strip():
            continue
        m = HEAD_RE.search(raw)
        if not m:
            continue
        sm = STATUS_RE.search(raw)
        status = sm.group(0).split(":", 1)[1].strip() if sm else "OPEN"
        posts.append(
            Post(
                raw=raw if raw.endswith("\n") else raw + "\n",
                ts=m.group(1),
                kind=m.group(2).upper(),
                slug=m.group(3),
                status=status,
                dt=parse_ts(m.group(1)),
            )
        )
    return header, posts


def set_status(p: Post, new: str) -> bool:
    if p.status == new:
        return False
    if STATUS_RE.search(p.raw):
        p.raw = STATUS_RE.sub(f"- Status: {new}", p.raw, count=1)
    else:
        p.raw = p.raw.rstrip() + f"\n- Status: {new}\n"
    p.status = new
    return True


def redact_keys(p: Post) -> bool:
    if "05-Keys" not in p.raw:
        return False
    p.raw = KEYS_RE.sub("- Home: (redacted — never post vault key paths)", p.raw, count=1)
    return True


def mark_archived(p: Post, day: str) -> None:
    if "- Archived:" not in p.raw:
        p.raw = p.raw.rstrip() + f"\n- Archived: {day} housekeep\n"


def compact(text: str, now: datetime | None = None) -> tuple[str, str, dict]:
    now = now or datetime.now(TZ2)
    header, posts = split_index(text)
    if not posts:
        return text, "", {"archived": 0, "live_open": 0, "changed": False}

    dirty = False
    by_slug: dict[str, list[Post]] = {}
    for p in posts:
        dirty = redact_keys(p) or dirty
        if p.kind == "DONE" and p.status != "DONE":
            dirty = set_status(p, "DONE") or dirty
        if PROBE_RE.search(p.slug) and p.status == "OPEN":
            dirty = set_status(p, "STALE") or dirty
        by_slug.setdefault(p.slug, []).append(p)

    for slug, group in by_slug.items():
        closed = any(g.kind == "DONE" or g.status in CLOSED for g in group)
        if closed:
            for g in group:
                if g.status == "OPEN":
                    dirty = set_status(g, "ANSWERED") or dirty
        opens = [g for g in group if g.status == "OPEN"]
        if len(opens) > 1:
            opens.sort(key=lambda g: g.dt or datetime.min.replace(tzinfo=TZ2))
            for g in opens[:-1]:
                dirty = set_status(g, "ANSWERED") or dirty

    cutoff = now - timedelta(days=STALE_DAYS)
    for p in posts:
        if p.status != "OPEN" or p.kind in KEEP_KINDS:
            continue
        if p.dt is not None and p.dt < cutoff:
            dirty = set_status(p, "STALE") or dirty

    live_posts = [p for p in posts if p.status == "OPEN"]
    arch_posts = [p for p in posts if p.status != "OPEN"]
    if arch_posts:
        dirty = True

    overflow = [p for p in live_posts if p.kind not in KEEP_KINDS]
    overflow.sort(key=lambda p: p.dt or datetime.min.replace(tzinfo=TZ2))
    while len(live_posts) > CAP and overflow:
        p = overflow.pop(0)
        set_status(p, "STALE")
        dirty = True
        live_posts.remove(p)
        arch_posts.append(p)

    if not dirty:
        open_n = sum(1 for p in posts if p.status == "OPEN")
        return text, "", {"archived": 0, "live_open": open_n, "changed": False}

    day = now.strftime("%Y-%m-%d")
    for p in arch_posts:
        mark_archived(p, day)

    live_posts.sort(key=lambda p: p.dt or datetime.min.replace(tzinfo=TZ2))
    live = header.rstrip() + "\n\n" + "\n".join(p.raw.rstrip() + "\n" for p in live_posts)
    if not live.endswith("\n"):
        live += "\n"
    arch = "\n".join(p.raw.rstrip() + "\n" for p in arch_posts)
    return live, arch, {
        "archived": len(arch_posts),
        "live_open": len(live_posts),
        "changed": True,
    }


def _archive_header(month: str) -> str:
    return (
        f"# NOTICE-BOARD archive — {month}\n\n"
        "Moved off the live index by scripts/housekeep.py. Bodies stay at each Home:.\n\n---\n\n"
    )


def run(
    index: Path,
    arch_dir: Path,
    now: datetime | None = None,
    quiet: bool = False,
) -> dict:
    now = now or datetime.now(TZ2)
    text = index.read_text(encoding="utf-8")
    live, arch, st = compact(text, now=now)
    if not st["changed"]:
        return st
    arch_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d%H%M%S")
    bkp = index.with_name(f"{index.name}.{stamp}.VM1.bkp")
    shutil.copy2(index, bkp)
    bdir = arch_dir / "backups" / now.strftime("%Y-%m")
    for old in index.parent.glob(index.name + "*.bkp"):
        if old.resolve() == bkp.resolve():
            continue
        bdir.mkdir(parents=True, exist_ok=True)
        dest = bdir / old.name
        if dest.exists():
            dest = bdir / f"{old.name}.{stamp}"
        shutil.move(str(old), str(dest))
    month = now.strftime("%Y-%m")
    month_path = arch_dir / f"{month}.md"
    if arch:
        if month_path.is_file():
            prev = month_path.read_text(encoding="utf-8")
            month_path.write_text(prev.rstrip() + "\n\n" + arch, encoding="utf-8")
        else:
            month_path.write_text(_archive_header(month) + arch, encoding="utf-8")
    index.write_text(live, encoding="utf-8")
    log = arch_dir / "HOUSEKEEP.jsonl"
    rec = {
        "ts": now.isoformat(),
        "archived": st["archived"],
        "live_open": st["live_open"],
        "backup": str(bkp),
        "archive": str(month_path),
    }
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    if not quiet:
        print(f"housekeep: archived {st['archived']} · live OPEN {st['live_open']} · {bkp.name}")
    return st


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Notice-board mechanical compact (0 LLM).")
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--arch", type=Path, required=True)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not args.index.is_file():
        print(f"housekeep: no index {args.index}", file=sys.stderr)
        return 1
    if args.dry_run:
        live, arch, st = compact(args.index.read_text(encoding="utf-8"))
        if args.quiet:
            return 0
        print(f"dry-run: archived {st['archived']} · live OPEN {st['live_open']} · changed {st['changed']}")
        return 0
    lock_path = args.arch / "housekeep.lock"
    args.arch.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if not args.quiet:
            print("housekeep: locked, skip", file=sys.stderr)
        os.close(fd)
        return 0
    try:
        run(index=args.index, arch_dir=args.arch, quiet=args.quiet)
    finally:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
