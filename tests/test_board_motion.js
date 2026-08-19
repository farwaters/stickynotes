#!/usr/bin/env node
/** RFC-0.22 + v2 motion: stage, gutter, fly-on/off, no hex chips, no scroll steal. */
const fs = require("fs");
const path = require("path");
const board = fs.readFileSync(path.join(__dirname, "..", "board.html"), "utf8");
const fails = [];

function need(re, msg) {
  if (!re.test(board)) fails.push(msg);
}
function forbid(re, msg) {
  if (re.test(board)) fails.push(msg);
}

need(/id="gutter"/, "missing #gutter");
need(/function mount\s*\(\s*el\s*,\s*n\s*,\s*\w+/, "mount(el, n, animate) missing");
need(/mount\(\s*el\s*,\s*n\s*,\s*true\s*\)/, "first/new notes must mount(..., true)");
need(/function peelOff/, "peelOff missing");
need(/classList\.add\(\s*["']leaving["']\s*\)/, "peelOff/act must add leaving");
need(/setTimeout\s*\([^,]+,\s*(3[5-9]\d|[4-9]\d{2,})/, "peel timeout must be >= 350ms");
need(/prefers-reduced-motion/, "prefers-reduced-motion branch missing");
need(/\.note\.arrive/, "arrive CSS missing");
need(/\.note\.leaving/, "leaving CSS missing");
need(/@keyframes drop/, "@keyframes drop missing");
need(/@keyframes peel/, "@keyframes peel missing");
need(/translate\(\s*var\(--from-x/, "fly-on must come from --from-x (wings)");
need(/id="skin-switch"|id="skin-toggle"/, "skin side-switch missing");
need(/data-theme/, "data-theme hook missing");
need(/stickynote-theme|action:\s*["']theme["']/, "theme persist missing");
need(/action:\s*["']restick["']|["']restick["']\s*,\s*["']restick["']|"restick"/, "restick control missing");
need(/["']discard["']/, "discard control missing");
need(/#parked[^{]*\{[^}]*nowrap/, "#parked must be a horizontal filmstrip");
need(/id="gutter"[\s\S]*id="parked-sec"/, "parked rail must live inside #gutter, not below the stage");
forbid(/#parked-sec\s*\{\s*overflow:\s*auto;\s*max-height:\s*28vh/, "parked must not be a 28vh wrap dump");
forbid(/scrollIntoView/, "scrollIntoView steals the frame");
forbid(/chats\.map\s*\(\s*c\s*=>\s*\[\s*["']chat:"/, "hex/chat chip farm still built from chats");
need(/classList\.contains\(\s*["']embed["']\s*\)/, "embed guard missing next to poll/interval");

if (fails.length) {
  console.error("FAIL\n" + fails.join("\n"));
  process.exit(1);
}
console.log("ok board motion + stage/gutter source");
