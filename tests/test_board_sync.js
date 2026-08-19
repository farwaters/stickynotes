#!/usr/bin/env node
/** Client store must key by heading id, not slug. */
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "board.html"), "utf8");
if (!/function noteKey\s*\(/.test(html) || !/const k = noteKey\(n\)/.test(html) || !/store\.get\(k\)/.test(html) || /seen\.add\(n\.slug\)/.test(html)) {
  console.error("FAIL board.html still keys the store by slug");
  process.exit(1);
}

function noteKey(n) {
  return n.id || ((n.ts || "") + "::" + (n.slug || ""));
}

function sync(store, notes) {
  const seen = new Set();
  const events = [];
  for (const n of notes) {
    const k = noteKey(n);
    if (!k || k === "::") continue;
    seen.add(k);
    const rec = store.get(k);
    if (!rec) {
      store.set(k, { note: n });
      events.push("arrive:" + k);
      continue;
    }
    if (rec.note.lane !== n.lane) events.push("lane:" + rec.note.lane + ">" + n.lane);
    if (rec.note.body !== n.body) events.push("body:" + k);
    rec.note = n;
  }
  for (const [k, rec] of store) {
    if (!seen.has(k)) {
      events.push("peel:" + k);
      store.delete(k);
    }
  }
  return events;
}

const poll1 = [
  { id: "t1::s", slug: "s", ts: "t1", lane: "pulled", body: "done" },
  { id: "t2::s", slug: "s", ts: "t2", lane: "pulled", body: "answered" },
  { id: "t3::s", slug: "s", ts: "t3", lane: "live", body: "ask" },
  { id: "t4::n", slug: "n", ts: "t4", lane: "live", body: "next" }
];
const poll2 = poll1.map((n) => ({ ...n }));
poll2.push({ id: "t5::x", slug: "x", ts: "t5", lane: "live", body: "new" });

const store = new Map();
const first = sync(store, poll1);
if (store.size !== 4) {
  console.error("FAIL first poll store", store.size);
  process.exit(1);
}
if (!first.every((e) => e.startsWith("arrive:"))) {
  console.error("FAIL first poll should only arrive", first);
  process.exit(1);
}
const second = sync(store, poll2);
if (store.size !== 5) {
  console.error("FAIL second poll store", store.size);
  process.exit(1);
}
if (second.join() !== "arrive:t5::x") {
  console.error("FAIL reused slug must not remount; only new heading arrives", second);
  process.exit(1);
}
const slugStore = new Map();
function slugKey(n) { return n.slug; }
function badSync(notes) {
  const ev = [];
  for (const n of notes) {
    const rec = slugStore.get(n.slug);
    if (!rec) slugStore.set(n.slug, { note: n });
    else {
      if (rec.note.lane !== n.lane) ev.push("lane:" + rec.note.lane + ">" + n.lane);
      rec.note = n;
    }
  }
  return ev;
}
const bad = badSync(poll1);
if (!bad.some((e) => e.includes("pulled>live") || e.includes(">"))) {
  console.error("FAIL fixture no longer reproduces slug collapse", bad);
  process.exit(1);
}
console.log("ok", store.size, "notes; no lane thrash on reused slug");
