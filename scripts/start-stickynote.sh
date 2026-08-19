#!/usr/bin/env bash
# Start stickynote on 127.0.0.1:9109. Seeds data/ from fixtures if missing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PORT="${PORT:-9109}"
export STICKYNOTE_BIND="${STICKYNOTE_BIND:-127.0.0.1}"
mkdir -p "$ROOT/data"
if [ ! -f "$ROOT/data/NOTICE-BOARD.md" ]; then
  cp "$ROOT/fixtures/NOTICE-BOARD.md" "$ROOT/data/NOTICE-BOARD.md"
fi
if [ ! -f "$ROOT/data/VIEW.json" ]; then
  cp "$ROOT/fixtures/VIEW.json" "$ROOT/data/VIEW.json"
fi
export NOTICE_BOARD_INDEX="${NOTICE_BOARD_INDEX:-$ROOT/data/NOTICE-BOARD.md}"
export NOTICE_BOARD_VIEW="${NOTICE_BOARD_VIEW:-$ROOT/data/VIEW.json}"
echo "stickynote http://127.0.0.1:${PORT}/notice-board" >&2
exec python3 "$ROOT/serve.py"
