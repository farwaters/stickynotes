# Install — notice-board skill

Copy this tree to the Grok user skill home, after the human says yes:

```bash
mkdir -p ~/.grok/skills/notice-board
rsync -a --exclude '*.bkp' \
  skill/notice-board/ \
  ~/.grok/skills/notice-board/
```

`$GROK_HOME` overrides `~/.grok` when set.

## Vault

`board.sh` looks for:

1. `$VAULT` if that directory exists
2. `~/vault` if `00-Inbox` is there
3. `/vault` if `00-Inbox` is there

Live data (not in the skill tree):

```
00-Inbox/NOTICE-BOARD.md
00-Inbox/notice-board/VIEW.json
00-Inbox/notice-board/YYYY-MM.md
04-Skills/notice-board/LEARNING.md
```

`board.sh ensure` creates those paths if they are missing.

## Stickynote

The viewer is `serve.py` in this repo. Run it once on the Grok host that should show the board (`./scripts/start-stickynote.sh`). Default URL: `http://127.0.0.1:9109/notice-board`.

A session is visible on the wall only when `/notice-board` is invoked in that session.
