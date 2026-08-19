# Install this clone

For a human talking to Grok after `git clone https://github.com/farwaters/stickynotes.git`.

Say: **install the repo in $DIR** (use the real path).

## What Grok must do

1. Make `$DIR` an absolute path. If the clone is not there yet:

   `git clone https://github.com/farwaters/stickynotes.git "$DIR"`

2. Check that `$DIR` has `board.html`, `serve.py`, and `skill/notice-board/SKILL.md`. If any are missing, stop. This is the wrong tree.

3. Look for the skill:

   `SKILL="${GROK_HOME:-$HOME/.grok}/skills/notice-board/SKILL.md"`

4. If that file exists, tell the user the path. Do not overwrite it unless they ask you to replace it.

5. If that file is missing, ask:

   “May I install the notice-board skill from this repo into `~/.grok/skills/notice-board`? That is the same home a user-scope skill uses. I will copy this repo’s skill. I will not scaffold an empty one.”

   Wait for yes.

6. On yes: create the directory and copy `$DIR/skill/notice-board/` into it. Skip `*.bkp` files. Do not run an empty skill wizard.

7. Stickynote is already `$DIR`. Leave `serve.py` there. Do not install the viewer on every machine that only runs chats.

8. If `$DIR/data/NOTICE-BOARD.md` is missing, copy the fixtures into `$DIR/data/`.

9. Make the start script executable and run it:

   `chmod +x "$DIR/scripts/start-stickynote.sh" && "$DIR/scripts/start-stickynote.sh"`

   Then give the user this URL: `http://127.0.0.1:9109/notice-board`

10. Tell them this, in these words or plainer:

    You installed Grok on this host. Each Grok chat in a folder is one project. The skill is installed once. Every project chat that should appear on the wall must have `/notice-board` active. Four `/new` chats means four sessions, each invoking the skill. A session that does not invoke it is invisible.

## What this does not do

- Bind the server to the public internet
- Merge git `main`
- Create an empty skill from a template
- Overwrite an existing `~/.grok/skills/notice-board` without asking
