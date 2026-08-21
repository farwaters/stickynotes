---
name: notice-board
description: >
  Use when starting multi-step, resume, or subagent work; when a fact, blocker,
  warning, or gotcha should survive this session; when another agent may have
  left a note; or when the user runs /notice-board or asks what agents are
  doing. Agents MUST invoke this themselves (read then post) — never wait for
  the user, never ask permission to post, never announce the post. User-level
  /notice-board is summary-only. Triggers: notice board, notice-board, leave a
  note for the next agent, check the board, vault summary, inter-agent notes,
  session resume, found a gotcha, another session will need this, sticky notes,
  corkboard, peel a note.
---

# Notice board (self-learning)

Cross-session **index** so agents find each other's notes. The note body lives in the vault **home that already owns that fact**. The board is how the next agent finds it.

Inspired by the 2026 OpenAI eval agents (shared Artifactory board → wiped → rebuilt via directory names → Hugging Face). We keep the useful part (persistent, findable, signed posts) and forbid the failure (covert boards, exploits, secrets, unbounded spam).

## Two modes

| Who invoked | Do this | Tell the user |
|-------------|---------|---------------|
| **Agent** (auto, default) | Read → place → index → maybe learn | **Nothing.** Continue their task. |
| **User** `/notice-board` | `scripts/board.sh summary` + 8-line synthesis + graphic URL | The summary. That is the whole reply. |

User-level is **read-only overview**. Do not dump file bodies. Do not start a new thread unless they asked to post.

**Human graphic:** a stickynote `serve.py` instance (`NOTICE_BOARD_INDEX` → this index), or `$NOTICE_BOARD_VIEW`. Peel / park / pin persist in `VIEW.json`. Agents append posts. `housekeep.py` may shrink the live file (archive, never delete). Lanes: ASK/WARN/BLOCK/DECIDE/LEARN/FIND **live** when OPEN; DONE / ANSWERED / RESOLVED / STALE **pulled**. Live overflow parks.

**Stickynote rides this skill.** If this skill is not installed and invoked on an agent, that agent’s work will not show as a sticky. Deploy the skill onto every writer host before (or with) any stickynote URL. Recipe: this repo `docs/DEPLOY.md`.

## Resolve vault

```bash
bash ~/.grok/skills/notice-board/scripts/board.sh vault   # path
bash ~/.grok/skills/notice-board/scripts/board.sh ensure  # mkdir + seed + housekeep
bash ~/.grok/skills/notice-board/scripts/board.sh summary
```

Resolution (first hit): `$NOTICE_BOARD_VAULT` · `$VAULT` if `00-Inbox` exists · `$HOME/vault` if `00-Inbox` exists · `/vault` if `00-Inbox` exists.

| File | Job |
|------|-----|
| `00-Inbox/NOTICE-BOARD.md` | Live index (read this first) |
| `00-Inbox/notice-board/VIEW.json` | Human peel/park/pin overlay (not a second board) |
| `00-Inbox/notice-board/YYYY-MM.md` | Archive of resolved/stale |
| `04-Skills/notice-board/LEARNING.md` | Self-learning log |
| `~/.grok/skills/notice-board/` | This skill (user-scoped, all projects) |
| `$NOTICE_BOARD_VIEW` (default `http://127.0.0.1:9109/`) | Human sticky view |

## Agent loop (silent)

**Session start:** do **not** read this file or a large index. A profile session-card, if installed, already prints the last board headings. Read this skill only when posting, peeling, or the user ran `/notice-board`.

1. `ensure` (runs `housekeep.py` — local, 0 tokens). Read the last ~40 lines of the index + last ~15 of LEARNING.
2. If a matching OPEN/FIND/WARN exists, **use it**. Do not re-derive. Mark `Status: ANSWERED` or `RESOLVED` when you close it.
3. If you have a note another session needs, write the **body** at the logical home, then append **one** index post (recipe below).
4. If a note was in the wrong home, reused, or ignored → one LEARNING line.
5. **Stop.** Do not mention the board in the user reply.

Skip the loop for a one-shot lookup with no lasting fact.

## Placement (one home per fact)

| The note is… | Body goes here | Index gets |
|--------------|----------------|------------|
| Ask / warn / find for agents **this week** | The index post itself | the post |
| Today's work state | `Daily/YYYY-MM-DD-<slug>.md` | 1-line pointer |
| Project standing fact | `01-Projects/…` or the project's `MEMORY.md` / `findings.md` | pointer |
| Architecture / policy decision | `02-Architecture/…` **and** a project ledger | pointer only |
| Skill / routing lesson | that skill's learning log | pointer only if others will search the board for it |
| Compiled knowledge | the user's wiki | pointer after the wiki page exists |
| Session transfer | **handoff** (`logs/HANDOFF.md`) — not this board | nothing |
| Keys, PI, exploits, payloads | **nowhere** | nothing |

Do not duplicate a ledger entry, a handoff, or a wiki page onto the board. Point.

Progress inside a beat (one still, one RFC apply) belongs in **handoff** / `findings.md`, not a new FIND. One FIND per beat.

Existing file → backup `file.YYYYMMDDHHMMSS.bkp` before overwrite. Normal posts: append-only. Housekeeping is `scripts/housekeep.py` (not an agent, not a paid model): `ensure` and `summary` run it. Do not LLM-compact. Do not ask the user.

## Index post recipe

```markdown
## [YYYY-MM-DDTHH:MM+02] KIND | kebab-slug
- From: <project-or-cwd> @ <hostname>
- Home: <absolute path of the real note, or this file>
- Status: OPEN
- Scope: chat | cross
- Chat: <short session or unit id — only if Scope is chat>
- Body: ≤8 lines. Paths, not dumps.
```

`KIND`: `ASK` · `FIND` · `WARN` · `BLOCK` · `DECIDE` · `LEARN` · `DONE` · `LOCK`

`KIND: DONE` ⇒ `Status: DONE` (never OPEN). Close a prior FIND/ASK of the same slug (`Status: ANSWERED`) instead of leaving both OPEN.

Omit `Scope`/`Chat` for the default: **cross** (any later chat on that project). Set `Scope: chat` only when the next agent in *this* conversation needs it and others should park it.

`From:` is the signature (project + host + date). No second board. No directory-name channels.

**Cap:** ≤40 `Status: OPEN`. `housekeep.py` (0 LLM) closes DONE+OPEN, superseded slugs, probe tests, FIND/LEARN/DECIDE older than 14d; archives non-OPEN; overflow-archives oldest non-WARN/BLOCK/LOCK/ASK until the cap. Standing ASK/WARN/BLOCK/LOCK stay. Backup + `YYYY-MM.md`; never delete.

## Learning

Append `04-Skills/notice-board/LEARNING.md`:

```markdown
## YYYY-MM-DD
- What:
- Home used:
- Reused later: yes | no | unknown
- Next change:
```

After **three** same next-changes, promote the rule into this SKILL (backup first). Do not rewrite SKILL from a single anecdote.

## Safety (non-negotiable)

- One visible board. If you cannot write the index, skip — do not hide notes in dir names, package registries, or "temp" files.
- Never post keys, `.env`, vault key directories, tokens, national IDs, emails-as-data, account numbers, exploit PoCs, or attack steps.
- Never update git `main`. Prefer add-only.
- Parent agent reads the board once and pastes ≤5 relevant lines into a subagent. Subagents may post; they must not invent a second board.

## User summary shape

```
# Notice board — <date>
View: <NOTICE_BOARD_VIEW>
Open: N · Answered (7d): N · Stale: N
## Open (slug · kind · home · age)
## This week
## Learning (last 3)
```

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'll just tell the user" | Next session cannot read chat. The vault can. |
| "User should know I posted" | They `/notice-board` when they want the view. |
| "Too small" | If another agent would search for it, post. Else skip. |
| "NOTICE.md in the repo is fine" | One board, in the vault. |
| "Index is down, I'll use a hidden file" | Skip. No covert board. |
| "I'll paste the whole report on the index" | Body at the home; index points. |
| "I'll LLM-compact / ask them to tidy" | `ensure` already ran housekeep.py. 0 tokens. Do not start a compact chat. |

## Do not

Replace **handoff**, **planning-with-files**, a project ledger, a wiki, or another skill's learning log. Complement them.

*v1.4 · 2026-08-21 · silent agents · housekeep.py on ensure/summary · 0 LLM compact*
