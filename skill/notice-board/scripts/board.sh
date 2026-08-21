#!/usr/bin/env bash
# notice-board — resolve vault paths and print the user-level summary.
# Usage: board.sh vault|index|learn|archive|ensure|summary|housekeep
set -euo pipefail

resolve_vault() {
  if [ -n "${NOTICE_BOARD_VAULT:-}" ] && [ -d "${NOTICE_BOARD_VAULT}/00-Inbox" ]; then
    printf '%s\n' "$NOTICE_BOARD_VAULT"
    return 0
  fi
  if [ -n "${VAULT:-}" ] && [ -d "${VAULT}/00-Inbox" ]; then
    printf '%s\n' "$VAULT"
    return 0
  fi
  if [ -d "${HOME}/vault/00-Inbox" ]; then
    printf '%s\n' "${HOME}/vault"
    return 0
  fi
  if [ -d /vault/00-Inbox ]; then
    printf '%s\n' "/vault"
    return 0
  fi
  echo "notice-board: cannot resolve vault (set NOTICE_BOARD_VAULT)" >&2
  return 1
}

VAULT="$(resolve_vault)"
INBOX="$VAULT/00-Inbox"
INDEX="$INBOX/NOTICE-BOARD.md"
ARCH="$INBOX/notice-board"
LEARN="$VAULT/04-Skills/notice-board/LEARNING.md"
VIEW="${NOTICE_BOARD_VIEW:-http://127.0.0.1:9109/}"

count_status() {
  local st="$1"
  if [ -f "$INDEX" ]; then
    grep -cE "^- Status: ${st}[[:space:]]*$" "$INDEX" 2>/dev/null || true
  else
    echo 0
  fi
}

housekeep_quiet() {
  local hk
  hk="$(cd "$(dirname "$0")" && pwd)/housekeep.py"
  if [ -f "$hk" ]; then
    python3 "$hk" --index "$INDEX" --arch "$ARCH" --quiet || true
  fi
}

seed_if_missing() {
  mkdir -p "$ARCH" "$VAULT/04-Skills/notice-board" "$VAULT/Daily"
  if [ ! -f "$INDEX" ]; then
    cat > "$INDEX" <<'EOF'
# NOTICE-BOARD

Cap: ≤40 OPEN. Bodies live at Home:. This file is the index.

---
EOF
  fi
  if [ ! -f "$LEARN" ]; then
    cat > "$LEARN" <<'EOF'
# Notice-board learning log

```
## YYYY-MM-DD
- What:
- Home used:
- Reused later: yes | no | unknown
- Next change:
```
EOF
  fi
}

cmd="${1:-summary}"
case "$cmd" in
  vault)   printf '%s\n' "$VAULT" ;;
  index)   printf '%s\n' "$INDEX" ;;
  learn)   printf '%s\n' "$LEARN" ;;
  archive) printf '%s\n' "$ARCH" ;;
  housekeep)
    mkdir -p "$ARCH"
    python3 "$(cd "$(dirname "$0")" && pwd)/housekeep.py" --index "$INDEX" --arch "$ARCH"
    ;;
  ensure)
    seed_if_missing
    housekeep_quiet
    printf '%s\n' "$INDEX"
    ;;
  summary)
    seed_if_missing
    housekeep_quiet

    printf '# Notice board summary\n'
    printf 'Vault: %s\n' "$VAULT"
    printf 'Index: %s\n' "$INDEX"
    printf 'Learning: %s\n' "$LEARN"
    printf 'View: %s\n' "$VIEW"
    printf 'Host: %s\n' "$(hostname -s 2>/dev/null || hostname)"
    printf '\n'
    printf 'Open: %s · Answered: %s · Resolved: %s · Stale: %s\n' \
      "$(count_status OPEN)" \
      "$(count_status ANSWERED)" \
      "$(count_status RESOLVED)" \
      "$(count_status STALE)"
    printf '\n## Headings\n'
    grep -n '^## \[' "$INDEX" | tail -n 24 || echo "(none)"
    printf '\n## Open (slug · kind · from)\n'
    if grep -q 'Status: OPEN' "$INDEX" 2>/dev/null; then
      awk '
        /^## \[/ { kind=$3; slug=$5; from="" }
        /^- From:/ {
          from=$0
          sub(/^- From:[[:space:]]*/, "", from)
        }
        /^- Status: OPEN[[:space:]]*$/ {
          printf "%s · %s · %s\n", slug, kind, from
        }
      ' "$INDEX"
    else
      echo "(none)"
    fi
    printf '\n## Learning (tail)\n'
    if [ -f "$LEARN" ]; then
      tail -n 16 "$LEARN"
    else
      echo "(no learning log)"
    fi
    ;;
  *)
    echo "usage: board.sh vault|index|learn|archive|ensure|summary|housekeep" >&2
    exit 2
    ;;
esac
