#!/usr/bin/env node
/** Full /notice-board polls; embed + cockpit stay a snapshot. */
const fs = require("fs");
const path = require("path");
const board = fs.readFileSync(path.join(__dirname, "..", "board.html"), "utf8");
const cockpitPath = path.join(__dirname, "..", "cockpit.html");
const fails = [];

if (fs.existsSync(cockpitPath)) {
  const cockpit = fs.readFileSync(cockpitPath, "utf8");
  if (/setInterval\s*\(\s*loadNotes\s*,/.test(cockpit)) {
    fails.push("cockpit still polls loadNotes()");
  }
}
if (!/setInterval\s*\(\s*load\s*,/.test(board)) {
  fails.push("board.html must setInterval(load");
}
const intervalAt = board.search(/setInterval\s*\(\s*load\s*,/);
if (intervalAt >= 0) {
  const window = board.slice(Math.max(0, intervalAt - 280), intervalAt + 80);
  if (!/classList\.contains\(\s*["']embed["']\s*\)/.test(window) &&
      !/!document\.documentElement\.classList\.contains\(\s*["']embed["']\s*\)/.test(board)) {
    fails.push("board poll is not guarded so embed skips the timer");
  }
}
if (/refresh to update/.test(board) && !/updates while open/.test(board)) {
  fails.push("full-page #sub still says refresh to update");
}
if (!/updates while open/.test(board)) {
  fails.push("full-page #sub must end with updates while open");
}

if (fails.length) {
  console.error("FAIL\n" + fails.join("\n"));
  process.exit(1);
}
console.log("ok poll on board only; cockpit snapshot");
