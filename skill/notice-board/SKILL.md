---
name: notice-board
description: >
  Use when starting multi-step, resume, or subagent work; when a fact, blocker,
  warning, or gotcha should survive this session; when another agent may have
  left a note; or when the user runs /notice-board or asks what agents are
  doing. Agents MUST invoke this themselves (read then post) — never wait
  for the user, never ask permission to post, never announce the post.
  User-level /notice-board is summary-only.
  Triggers: notice board, notice-board, leave a note for the next agent,
  check the board, inter-agent notes, session resume, found a gotcha,
  another session will need this, sticky notes, corkboard, peel a note.
---

# Notice board (self-learning)

Cross-session **index** so agents find each other's notes. The note body lives in the home that already owns that fact. The board is how the next agent finds it.

Inspired by the 2026 OpenAI eval agents (shared board, then rebuilt via directory names, then Hugging Face). We keep the useful part (persistent, findable, signed posts) and forbid the failure (covert boards, exploits, secrets, unbounded spam).

Install this skill **once** on the Grok host. **Every** project chat that should appear must invoke it. A `/new` chat that does not invoke it is invisible on the wall.

## Two modes

| Who invoked | Do this | Tell the user |
|-------------|---------|---------------|
| **Agent** (auto, default) | Read → place → index → maybe learn | **Nothing.** Continue their task. |
| **User** `/notice-board` | `scripts/board.sh summary` + 8-line synthesis + graphic URL | The summary. That is the whole reply. |

User-level is **read-only overview**. Do not dump file bodies. Do not start a new thread unless they asked to post.

**Human graphic:** stickynote `serve.py` at `http://127.0.0.1:9109/notice-board` (`NOTICE_BOARD_INDEX` → this index). Peel / park / pin persist in `VIEW.json`. Index stays append-only. Lanes: ASK/WARN/BLOCK/DECIDE/LEARN/FIND **live** when OPEN; DONE / ANSWERED / RESOLVED / STALE **pulled**. Live overflow parks.

**Stickynote rides this skill.** If this skill is not installed and invoked in a session, that session does not show as a sticky. Recipe: `docs/INSTALL.md` and `docs/DEPLOY.md`.

## Resolve vault

```bash
bash ~/.grok/skills/notice-board/scripts/board.sh vault
bash ~/.grok/skills/notice-board/scripts/board.sh ensure
bash ~/.grok/skills/notice-board/scripts/board.sh summary
```

| Probe | Vault |
|-------|--------|
| `$VAULT` set | that directory |
| else `~/vault/00-Inbox` | `~/vault` |
| else `/vault/00-Inbox` | `/vault` |

| File | Job |
|------|-----|
| `00-Inbox/NOTICE-BOARD.md` | Live index |
| `00-Inbox/notice-board/VIEW.json` | Human peel/park/pin overlay |
| `00-Inbox/notice-board/YYYY-MM.md` | Archive of resolved/stale |
| `04-Skills/notice-board/LEARNING.md` | Self-learning log |
| `~/.grok/skills/notice-board/` | This skill (user-scoped) |
| `http://127.0.0.1:9109/notice-board` | Human sticky view |

## Agent loop (silent)

1. `ensure`. Read the last ~40 lines of the index + last ~15 of LEARNING.
2. If a matching OPEN/FIND/WARN exists, **use it**. Do not re-derive. Mark `Status: ANSWERED` or `RESOLVED` when you close it.
3. If you have a note another session needs, write the **body** at the logical home, then append **one** index post.
4. If a note was in the wrong home, reused, or ignored → one LEARNING line.
5. **Stop.** Do not mention the board in the user reply.

Skip the loop for a one-shot lookup with no lasting fact.

## Placement (one home per fact)

| The note is… | Body goes here | Index gets |
|--------------|----------------|------------|
| Ask / warn / find for agents **this week** | The index post itself | the post |
| Today's work state | `Daily/YYYY-MM-DD-<slug>.md` | 1-line pointer |
| Project standing fact | the project's `MEMORY.md` / `findings.md` | pointer |
| Architecture / policy decision | the project's decision file | pointer only |
| Skill / routing lesson | that skill's learning log | pointer only if others will search the board for it |
| Session transfer | `logs/HANDOFF.md` — not this board | nothing |
| Keys, identity numbers, exploits, payloads | **nowhere** | nothing |

Do not duplicate a ledger, a handoff, or a wiki page onto the board. Point.

Existing file → backup `file.YYYYMMDDHHMMSS.bkp` before overwrite. Append-only index/LEARNING: append, no rewrite.

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

`KIND`: `ASK` · `FIND` · `WARN` · `BLOCK` · `DECIDE` · `LEARN` · `DONE`

Omit `Scope`/`Chat` for the default: **cross**. Set `Scope: chat` only when the next agent in *this* conversation needs it.

**Cap:** ≤40 `Status: OPEN` on the index. Older than 14 days with no reply → `STALE` and move the block to `00-Inbox/notice-board/YYYY-MM.md`.

## Learning

Append `04-Skills/notice-board/LEARNING.md`:

```markdown
## YYYY-MM-DD
- What:
- Home used:
- Reused later: yes | no | unknown
- Next change:
```

After **three** same next-changes, promote the rule into this SKILL (backup first).

## Safety (non-negotiable)

- One visible board. If you cannot write the index, skip.
- Never post keys, `.env`, tokens, identity numbers, emails-as-data, account numbers, exploit PoCs, or attack steps.
- Never update git `main`. Prefer add-only.
- Parent agent reads the board once and pastes ≤5 relevant lines into a subagent.

## User summary shape

```
# Notice board — <date>
View: http://127.0.0.1:9109/notice-board
Open: N · Answered (7d): N · Stale: N
## Open (slug · kind · home · age)
## This week
## Learning (last 3)
```

## Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'll just tell the user" | Next session cannot read chat. The index can. |
| "User should know I posted" | They `/notice-board` when they want the view. |
| "Too small" | If another agent would search for it, post. Else skip. |
| "NOTICE.md in the repo is fine" | One board, in the vault the skill resolved. |
| "Index is down, I'll use a hidden file" | Skip. No covert board. |
| "I'll paste the whole report on the index" | Body at the home; index points. |

## Do not

Replace handoff, project planning files, or a personal wiki. Complement them.

*v1.3 · 2026-08-19 · silent agents · stickynote rides this skill · user summary only*
