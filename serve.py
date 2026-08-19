#!/usr/bin/env python3
"""Standalone notice-board server. Stdlib only. Default :9109 + fixtures."""
from __future__ import annotations

import json
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", os.environ.get("STICKYNOTE_PORT", "9109")))
BOARD_HTML = ROOT / "board.html"
COCKPIT = ROOT / "cockpit.html"
HEAD_RE = re.compile(r"^## \[([^\]]+)\]\s+(\w+)\s+\|\s+(\S+)\s*$")
LIVE_KINDS = frozenset({"ASK", "WARN", "BLOCK", "DECIDE", "LEARN", "FIND"})
PEEL_STATUS = frozenset({"RESOLVED", "ANSWERED", "STALE"})
MAX_LIVE = 24
MAX_PULLED = 14
AFTERGLOW_S = 4 * 3600
VIEW_KEYS = (
    "peeled",
    "parked",
    "pinned",
    "guttered",
    "discarded",
    "hidden_projects",
    "project_pins",
    "afterglow",
)
USER_ACTIONS = frozenset({"peel", "park", "pin", "restick", "discard"})
BOARD_ACTIONS = USER_ACTIONS | frozenset({"hide", "unhide", "theme"})
THEMES = frozenset({"cork", "void"})
HEX_CHAT_RE = re.compile(
    r"^(?:chat:)?(?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[0-9a-f]{8,32}|01[0-9a-hjkmnp-tv-z]{24})$",
    re.I,
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_ts(raw) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_theme(raw) -> str:
    t = str(raw or "").strip().lower()
    return t if t in THEMES else "cork"


def board_paths() -> tuple[Path, Path]:
    index = Path(os.environ.get("NOTICE_BOARD_INDEX", ROOT / "fixtures" / "NOTICE-BOARD.md"))
    view = Path(os.environ.get("NOTICE_BOARD_VIEW", ROOT / "fixtures" / "VIEW.json"))
    return index, view


def read_version() -> str:
    line = (_read_text(ROOT / "VERSION").splitlines() or [""])[0].strip()
    return line or "v0"


def stamp_html(html: str) -> str:
    return html.replace("__VERSION__", read_version())


def page_bytes(path: Path) -> bytes:
    if not path.is_file():
        return b""
    return stamp_html(_read_text(path)).encode("utf-8")


def assign_note_ids(notes: list[dict]) -> list[dict]:
    seen: set[str] = set()
    for n in notes:
        base = f"{n.get('ts') or ''}::{n.get('slug') or ''}"
        nid = base
        i = 2
        while nid in seen:
            nid = f"{base}#{i}"
            i += 1
        seen.add(nid)
        n["id"] = nid
    return notes


def parse_index(text: str) -> list[dict]:
    notes: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = HEAD_RE.match(line)
        if m:
            if cur:
                notes.append(cur)
            cur = {
                "ts": m.group(1),
                "kind": m.group(2).upper(),
                "slug": m.group(3),
                "from": "",
                "home": "",
                "status": "",
                "chat": "",
                "scope": "",
                "body": "",
            }
            continue
        if not cur:
            continue
        if line.startswith("- From:"):
            cur["from"] = line[7:].strip()
        elif line.startswith("- Home:"):
            cur["home"] = line[7:].strip()
        elif line.startswith("- Status:"):
            cur["status"] = line[9:].strip()
        elif line.startswith("- Chat:"):
            cur["chat"] = line[7:].strip()
        elif line.startswith("- Scope:"):
            cur["scope"] = line[8:].strip()
        elif line.startswith("- Body:"):
            cur["body"] = line[7:].strip()
        elif cur.get("body") and (line.startswith("  ") or line.startswith("\t")):
            cur["body"] = (cur["body"] + " " + line.strip()).strip()
    if cur:
        notes.append(cur)
    return assign_note_ids(notes)


def project_of(frm: str) -> str:
    return (frm.split("@", 1)[0].strip() or "unknown")


def is_hex_chat(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return False
    if s.lower().startswith("chat:"):
        return True
    return bool(HEX_CHAT_RE.fullmatch(s))


def note_age_s(ts: str, now: datetime) -> float | None:
    raw = (ts or "").strip()
    if not raw:
        return None
    if re.search(r"[+-]\d{2}$", raw):
        raw = raw + ":00"
    dt = parse_ts(raw)
    if dt is None:
        return None
    return max(0.0, (now - dt).total_seconds())


def load_view(path: Path) -> dict:
    empty = {k: {} for k in VIEW_KEYS}
    if not path.is_file():
        return dict(empty)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(empty)
    if not isinstance(data, dict):
        return dict(empty)
    for key in VIEW_KEYS:
        if not isinstance(data.get(key), dict):
            data[key] = {}
    for slug, ts in data["peeled"].items():
        if slug not in data["guttered"] and slug not in data["discarded"]:
            data["guttered"][slug] = ts
    return data


def save_view(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        tag = "VM1." if "vault" in str(path) else ""
        bkp = path.with_name(path.name + "." + tag + stamp + ".bkp")
        try:
            bkp.write_bytes(path.read_bytes())
        except OSError:
            pass
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _guttered_slugs(view: dict) -> dict:
    guttered = dict(view.get("guttered") or {})
    discarded = view.get("discarded") or {}
    for slug, ts in (view.get("peeled") or {}).items():
        if slug not in guttered and slug not in discarded:
            guttered[slug] = ts
    return guttered


def classify_notes(raw: list[dict], view: dict, now: datetime) -> list[dict]:
    peeled = view.get("peeled") or {}
    parked = view.get("parked") or {}
    pinned = view.get("pinned") or {}
    guttered = _guttered_slugs(view)
    discarded = view.get("discarded") or {}
    hidden = view.get("hidden_projects") or {}
    out: list[dict] = []
    for n in raw:
        slug = n.get("slug") or ""
        kind = n.get("kind") or ""
        status = n.get("status") or ""
        frm = n.get("from") or ""
        chat = n.get("chat") or ""
        scope = (n.get("scope") or "").lower()
        if not scope:
            scope = "chat" if chat else "cross"
        if slug in discarded:
            continue
        agent_closed = status in PEEL_STATUS or kind == "DONE"
        if agent_closed:
            lane = "pulled"
        elif slug in guttered or slug in peeled:
            lane = "gutter"
        elif slug in pinned:
            lane = "live"
        elif slug in parked:
            lane = "parked"
        elif kind in LIVE_KINDS and status == "OPEN":
            lane = "live"
        elif status == "OPEN":
            lane = "parked"
        else:
            lane = "pulled"
        project = project_of(frm)
        if project in hidden and lane == "live":
            lane = "parked"
        age = note_age_s(n.get("ts") or "", now)
        out.append(
            {
                "id": n.get("id") or f"{n.get('ts') or ''}::{slug}",
                "slug": slug,
                "kind": kind,
                "status": status,
                "from": frm,
                "project": project,
                "chat": chat,
                "scope": scope,
                "home": n.get("home") or "",
                "body": n.get("body") or "",
                "ts": n.get("ts") or "",
                "lane": lane,
                "age_s": None if age is None else int(age),
            }
        )

    live = [n for n in out if n["lane"] == "live"]
    live.sort(key=lambda n: n.get("ts") or "", reverse=True)
    if len(live) > MAX_LIVE:
        overflow = set(n["id"] for n in live[MAX_LIVE:])
        for n in out:
            if n.get("id") in overflow and n["lane"] == "live":
                n["lane"] = "parked"

    pulled = [n for n in out if n["lane"] == "pulled"]
    overlay_keep = {n["slug"] for n in pulled if n["slug"] in peeled}
    rest = sorted(
        (n for n in pulled if n["slug"] not in overlay_keep),
        key=lambda n: n.get("ts") or "",
        reverse=True,
    )
    room = max(0, MAX_PULLED - len(overlay_keep))
    keep = overlay_keep | {n["slug"] for n in rest[:room]}
    out = [n for n in out if n["lane"] != "pulled" or n["slug"] in keep]
    out.sort(key=lambda n: (n.get("ts") or ""), reverse=True)
    return out


def _afterglow_ok(ts, now: datetime) -> bool:
    dt = parse_ts(ts)
    if dt is None:
        raw = str(ts or "").strip()
        if re.search(r"[+-]\d{2}$", raw):
            dt = parse_ts(raw + ":00")
    if dt is None:
        return False
    return 0 <= (now - dt).total_seconds() <= AFTERGLOW_S


def active_projects(notes: list[dict], view: dict, now: datetime) -> list[str]:
    hidden = view.get("hidden_projects") or {}
    pins = view.get("project_pins") or {}
    glow = view.get("afterglow") or {}
    active: set[str] = set()
    for n in notes:
        p = n.get("project") or ""
        if not p or is_hex_chat(p) or p in hidden:
            continue
        if n.get("lane") == "live" and n.get("status") == "OPEN":
            active.add(p)
    for p, ts in glow.items():
        if not p or is_hex_chat(p) or p in hidden:
            continue
        if _afterglow_ok(ts, now):
            active.add(p)
    for p in pins:
        if p and p not in hidden and not is_hex_chat(p):
            active.add(p)
    return sorted(active)


def public_urls() -> dict:
    base = f"http://127.0.0.1:{PORT}"
    return {
        "board": f"{base}/notice-board",
        "board_alias": f"{base}/board",
        "cockpit": f"{base}/",
    }


def board_payload() -> dict:
    index, view_path = board_paths()
    now = datetime.now(timezone.utc)
    view = load_view(view_path)
    notes = classify_notes(parse_index(_read_text(index)), view, now)
    projects = active_projects(notes, view, now)
    chats = sorted({n["chat"] for n in notes if n.get("chat") and not is_hex_chat(n["chat"])})
    counts = {
        "live": sum(1 for n in notes if n["lane"] == "live"),
        "parked": sum(1 for n in notes if n["lane"] == "parked"),
        "pulled": sum(1 for n in notes if n["lane"] == "pulled"),
        "gutter": sum(1 for n in notes if n["lane"] == "gutter"),
        "open": sum(1 for n in notes if n.get("status") == "OPEN"),
    }
    try:
        mtime = index.stat().st_mtime if index.is_file() else 0
    except OSError:
        mtime = 0
    return {
        "ok": True,
        "now": now.isoformat(),
        "index": str(index),
        "mtime": mtime,
        "counts": counts,
        "projects": projects,
        "chats": chats,
        "notes": notes,
        "theme": normalize_theme(view.get("theme")),
        "urls": public_urls(),
    }


def _agent_closed(note: dict) -> bool:
    return (note.get("kind") or "") == "DONE" or (note.get("status") or "") in PEEL_STATUS


def _notes_for_slug(index: Path, slug: str) -> list[dict]:
    return [n for n in parse_index(_read_text(index)) if (n.get("slug") or "") == slug]


def _project_for_slug(index: Path, slug: str) -> str:
    for n in reversed(_notes_for_slug(index, slug)):
        p = project_of(n.get("from") or "")
        if p:
            return p
    return ""


def append_restick(index: Path, src: dict, now: datetime) -> None:
    ts = now.astimezone(timezone(timedelta(hours=2))).strftime("%Y-%m-%dT%H:%M") + "+02"
    kind = src.get("kind") or "ASK"
    slug = src.get("slug") or "restick"
    lines = ["", f"## [{ts}] {kind} | {slug}", f"- From: {src.get('from') or 'stickynote @ host'}"]
    if src.get("home"):
        lines.append(f"- Home: {src['home']}")
    lines.append("- Status: OPEN")
    if src.get("scope"):
        lines.append(f"- Scope: {src['scope']}")
    if src.get("chat"):
        lines.append(f"- Chat: {src['chat']}")
    if src.get("body"):
        lines.append(f"- Body: {src['body']}")
    with index.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def apply_board_action(slug: str, action: str) -> dict:
    slug = (slug or "").strip()
    action = (action or "").strip().lower()
    if action not in BOARD_ACTIONS or (action != "theme" and not slug):
        return {"ok": False, "error": "need slug and action peel|park|pin|restick|discard|hide|unhide|theme"}
    index, view_path = board_paths()
    view = load_view(view_path)
    now = datetime.now(timezone.utc)
    stamp = now.isoformat()

    if action == "theme":
        view["theme"] = normalize_theme(slug)
        save_view(view_path, view)
        payload = board_payload()
        payload["applied"] = {"slug": view["theme"], "action": action}
        return payload

    if action == "hide":
        view["hidden_projects"][slug] = stamp
        view["project_pins"].pop(slug, None)
        save_view(view_path, view)
        payload = board_payload()
        payload["applied"] = {"slug": slug, "action": action}
        return payload
    if action == "unhide":
        view["hidden_projects"].pop(slug, None)
        save_view(view_path, view)
        payload = board_payload()
        payload["applied"] = {"slug": slug, "action": action}
        return payload

    matches = _notes_for_slug(index, slug)
    if action == "restick":
        if not matches or all(_agent_closed(n) for n in matches):
            return {"ok": False, "error": "agent-closed"}
        src = next((n for n in reversed(matches) if not _agent_closed(n)), matches[-1])
        for bucket in ("guttered", "peeled", "discarded", "parked"):
            view[bucket].pop(slug, None)
        append_restick(index, src, now)
    elif action == "discard":
        view["discarded"][slug] = stamp
        view["guttered"].pop(slug, None)
        view["peeled"].pop(slug, None)
    else:
        for bucket in ("peeled", "parked", "pinned", "guttered"):
            view[bucket].pop(slug, None)
        if action == "peel":
            view["guttered"][slug] = stamp
            view["peeled"][slug] = stamp
        elif action == "park":
            view["parked"][slug] = stamp
        else:
            view["pinned"][slug] = stamp

    if action in USER_ACTIONS:
        proj = _project_for_slug(index, slug)
        if proj:
            view["afterglow"][proj] = stamp

    save_view(view_path, view)
    payload = board_payload()
    payload["applied"] = {"slug": slug, "action": action}
    return payload


def status_stub() -> dict:
    # No vault keys, no wallet, no Prometheus. Cockpit fetch stays graceful.
    return {
        "ok": True,
        "you_are_on": "none",
        "last": {},
        "tokens_24h": {},
        "offload_7d": {},
        "t3_wallet": {},
        "services": {"board": True},
        "keys_present": {},
    }


def _send(handler: BaseHTTPRequestHandler, code: int, body: bytes, ctype: str) -> None:
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _local_ok(self) -> bool:
        host = self.client_address[0]
        return host in ("127.0.0.1", "::1", "localhost")

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/cockpit"):
            if COCKPIT.is_file():
                body = page_bytes(COCKPIT) or b"<p>missing cockpit.html</p>\n"
                _send(self, 200, body, "text/html; charset=utf-8")
            else:
                self.send_response(302)
                self.send_header("Location", "/notice-board")
                self.end_headers()
        elif path in ("/board", "/board.html", "/notice-board"):
            body = page_bytes(BOARD_HTML) or b"<p>missing board.html</p>\n"
            _send(self, 200, body, "text/html; charset=utf-8")
        elif path == "/api/board":
            _send(self, 200, json.dumps(board_payload(), indent=2).encode() + b"\n", "application/json; charset=utf-8")
        elif path in ("/api/status", "/status"):
            _send(self, 200, json.dumps(status_stub(), indent=2).encode() + b"\n", "application/json; charset=utf-8")
        elif path == "/health":
            _send(self, 200, b"ok\n", "text/plain")
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/board", "/api/wallet"):
            self.send_error(404)
            return
        if not self._local_ok():
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > 4096:
            self.send_error(400, "bad length")
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(400, "bad json")
            return
        if not isinstance(data, dict):
            self.send_error(400, "object required")
            return
        if path == "/api/wallet":
            result = {"ok": False, "error": "wallet not in this repo"}
        else:
            result = apply_board_action(str(data.get("slug") or ""), str(data.get("action") or ""))
        _send(self, 200, json.dumps(result, indent=2).encode() + b"\n", "application/json; charset=utf-8")


def main() -> None:
    host = os.environ.get("STICKYNOTE_BIND", "127.0.0.1")
    httpd = HTTPServer((host, PORT), Handler)
    print(f"stickynote http://127.0.0.1:{PORT}/notice-board  index={board_paths()[0]}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
