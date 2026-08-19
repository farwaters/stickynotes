#!/usr/bin/env bash
# notice-board — resolve vault paths and print the user-level summary.
# Usage: board.sh vault|index|learn|archive|ensure|summary
set -euo pipefail

if [ -n "${VAULT:-}" ] && [ -d "$VAULT" ]; then
  :
elif [ -d "${HOME}/vault/00-Inbox" ]; then
  VAULT="${HOME}/vault"
elif [ -d /vault/00-Inbox ]; then
  VAULT="/vault"
else
  echo "notice-board: cannot resolve vault (set VAULT, or use ~/vault or /vault)" >&2
  exit 1
fi

INBOX="$VAULT/00-Inbox"
INDEX="$INBOX/NOTICE-BOARD.md"
ARCH="$INBOX/notice-board"
LEARN="$VAULT/04-Skills/notice-board/LEARNING.md"

count_status() {
  local st="$1"
  if [ -f "$INDEX" ]; then
    grep -cE "^- Status: ${st}[[:space:]]*$" "$INDEX" 2>/dev/null || true
  else
    echo 0
  fi
}

cmd="${1:-summary}"
case "$cmd" in
  vault)   printf '%s\n' "$VAULT" ;;
  index)   printf '%s\n' "$INDEX" ;;
  learn)   printf '%s\n' "$LEARN" ;;
  archive) printf '%s\n' "$ARCH" ;;
  ensure)
    mkdir -p "$ARCH" "$VAULT/04-Skills/notice-board" "$VAULT/Daily"
    if [ ! -f "$INDEX" ]; then
      printf '# Notice board\n' > "$INDEX"
    fi
    if [ ! -f "$LEARN" ]; then
      printf '# notice-board learning\n' > "$LEARN"
    fi
    printf '%s\n' "$INDEX"
    ;;
  summary)
    printf '# Notice board summary\n'
    printf 'Vault: %s\n' "$VAULT"
    printf 'Index: %s\n' "$INDEX"
    printf 'Learning: %s\n' "$LEARN"
    printf 'View: http://127.0.0.1:9109/notice-board\n'
    printf '\n'
    if [ ! -f "$INDEX" ]; then
      echo "(no index yet — skill not seeded)"
      exit 0
    fi
    printf 'Open: %s · Answered: %s · Resolved: %s · Stale: %s\n' \
      "$(count_status OPEN)" \
      "$(count_status ANSWERED)" \
      "$(count_status RESOLVED)" \
      "$(count_status STALE)"
    printf '\n## Headings\n'
    grep -n '^## \[' "$INDEX" | tail -n 24 || echo "(none)"
    printf '\n## Open blocks\n'
    if grep -q 'Status: OPEN' "$INDEX" 2>/dev/null; then
      awk '
        /^## \[/ { buf=$0; keep=1; next }
        keep { buf=buf "\n" $0 }
        /^- Status: OPEN/ { print buf; print "---"; keep=0; buf="" }
      ' "$INDEX"
    else
      echo "(none)"
    fi
    printf '\n## Learning (tail)\n'
    if [ -f "$LEARN" ]; then
      tail -n 20 "$LEARN"
    else
      echo "(no learning log)"
    fi
    ;;
  *)
    echo "usage: board.sh vault|index|learn|archive|ensure|summary" >&2
    exit 2
    ;;
esac
