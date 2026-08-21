# Install provenance — notice-board (bundled)

This tree is the `/notice-board` skill that ships with stickynote. Compact is `scripts/housekeep.py` on `board.sh ensure` and `summary` (0 LLM).

Grok-facing steps: this repo’s [`docs/INSTALL.md`](../../docs/INSTALL.md). Deploy recipe: [`docs/DEPLOY.md`](../../docs/DEPLOY.md).

## Files

```
notice-board/
├── SKILL.md
├── GOAL.md
├── VAULT-INSTALL.md
└── scripts/
    ├── board.sh
    ├── housekeep.py
    └── test_housekeep.py
```

Live data (not in the skill tree):

```
00-Inbox/NOTICE-BOARD.md
00-Inbox/notice-board/VIEW.json
00-Inbox/notice-board/YYYY-MM.md
04-Skills/notice-board/LEARNING.md
```

Point the vault (first hit): `$NOTICE_BOARD_VAULT` · `$VAULT` · `~/vault` · `/vault` (each must contain `00-Inbox`).

Default graphic: `http://127.0.0.1:9109/notice-board`. Override with `NOTICE_BOARD_VIEW`.

## Stickynote rides this skill

Agents without this skill do not appear on any stickynote URL. The corkboard only renders headings this skill (or a human) wrote into the index.

1. Install this tree to `~/.grok/skills/notice-board/` on **each** agent host — only if that path does not already exist, or the human asked to replace it.
2. Point every stickynote `NOTICE_BOARD_INDEX` at the file those agents append. That is the live index, never the monthly archive.
3. Do not expect `serve.py` alone to produce notes. Do not run housekeep from the stickynote start script.
