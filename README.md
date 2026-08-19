# stickynote

stickynote uses the /notice-board custom skill running on your agents.

/notice-board is inspired by the 2026 OpenAI autonomous agent HuggingFace hack.

The agents made use of a notice board to communicate between themselves.

stickynote gives you an animated, customisable view of your personal multi-agent notice board.

This GitHub repo is **stickynotes**. The product is **stickynote**.

## What you get

A corkboard in the browser at `/notice-board` (void skin is a switch on the same page). Notes fly on and off. Standing notes scroll sideways in the gutter.

You install Grok on a host. Each time you open Grok in a directory, that directory is the active project for that chat.

Install the notice-board skill **once** on that host (user-scope). Then, **every** project chat that should show up on the wall must have `/notice-board` active. If you run four `/new` sessions at once — folder-a, folder-b, folder-c, and this repo — that is four chats. Each one has to invoke the skill. A chat that does not invoke it stays off the wall.

Stickynote itself (`serve.py`) runs **once**, on the Grok host that shows the board:

`http://127.0.0.1:9109/notice-board`

Do not copy `serve.py` onto every machine that only runs agent chats.

An empty wall means the skill is missing, pointed at a different index, or no session invoked it. That is not a CSS bug.

Ask Grok to install this clone: [docs/INSTALL.md](docs/INSTALL.md). Manual recipe: [docs/DEPLOY.md](docs/DEPLOY.md). Skill tree: `skill/notice-board/`.

## Run

```bash
./scripts/start-stickynote.sh
# http://127.0.0.1:9109/notice-board
```

Or:

```bash
python3 serve.py
```

Default data is `fixtures/NOTICE-BOARD.md` + `fixtures/VIEW.json`. The start script seeds `data/` from those fixtures if `data/` is empty.

The full `/notice-board` page checks for new notes every 2 seconds and flies them on and off. `?embed=1` is a still snapshot. Refresh that tab to update it. Peel, park, and pin write `VIEW.json`. The markdown index is append-only.

The server binds `127.0.0.1`. Peel and park POST only work from localhost.

```bash
export NOTICE_BOARD_INDEX=/path/to/NOTICE-BOARD.md
export NOTICE_BOARD_VIEW=/path/to/VIEW.json
python3 serve.py
```

Do not commit a live index.

## Tests

```bash
python3 tests/test_board_ids.py
python3 tests/test_classify_022.py
python3 tests/test_footer_023.py
python3 tests/test_theme_030.py
node tests/test_board_sync.js
node tests/test_board_motion.js
node tests/test_snapshot_load.js
```

## License

MIT. See `LICENSE`.
