# work-buddy

A skill for Claude Code (and Codex) that helps an engineer plan their day, track what's done vs. missed, prioritize by goal-impact, and reflect weekly — all stored as plain markdown in an Obsidian vault.

## Goals

1. Never forget what was planned, what was missed, what got done.
2. Make daily decisions about *what to work on next* based on goal-impact, not vibes.
3. Capture wins and growth weekly so progress is visible.
4. Stay portable — pure markdown in Obsidian, Claude Code skill is just the brain.

## Non-goals (v1)

- No Slack/email integration.
- No Jira/GitHub/Linear pulling.
- No automated cron — leave a sample line for the user to enable later.
- No multi-user.

---

## Repository layout

This repo *is* the skill. Install by symlinking or copying into `~/.claude/skills/work-buddy/`.

```
work-buddy/
├── README.md                    # install + usage
├── DESIGN.md                    # this doc
├── SKILL.md                     # Claude Code skill entry point
├── INSTRUCTIONS.md              # Codex-readable mirror of SKILL.md
├── install.sh                   # symlinks repo into ~/.claude/skills/work-buddy
├── config.example.json
├── commands/
│   ├── init.md                  # /work-buddy init
│   ├── goals.md                 # /work-buddy goals
│   ├── morning.md               # /work-buddy morning
│   ├── now.md                   # /work-buddy now
│   ├── eod.md                   # /work-buddy eod
│   └── weekly.md                # /work-buddy weekly
├── templates/
│   ├── daily.md
│   ├── weekly.md
│   ├── goal.md
│   └── quarterly.md
├── helpers/
│   └── wb.py                    # date math, file resolution, carry-over logic
└── cron-suggested.txt
```

## Vault layout (created in user's Obsidian vault)

```
<vault>/
├── work-buddy/
│   ├── Goals/
│   │   └── Quarterly.md         # source of truth for goals + impact
│   ├── Daily/
│   │   └── 2026-04-28.md
│   └── Weekly/
│       └── 2026-W18.md
```

The skill never writes outside `<vault>/work-buddy/`.

---

## Config

`~/.claude/skills/work-buddy/config.json` (gitignored):

```json
{
  "vault_path": "/Users/amr/Documents/Obsidian/MyVault",
  "subdir": "work-buddy",
  "created_at": "2026-04-28T09:30:00+03:00",
  "tz": "Africa/Cairo"
}
```

If the file is missing or `vault_path` doesn't exist, every subcommand short-circuits to `init`.

---

## Subcommands

The skill is invoked as `/work-buddy <subcommand>`. The router is `SKILL.md`; each subcommand has its own prompt file under `commands/`.

### `/work-buddy init`

1. Ask user for their Obsidian vault absolute path. Validate it exists.
2. Optional: ask for a subdirectory name (default `work-buddy`).
3. Create `<vault>/<subdir>/{Goals,Daily,Weekly}/`.
4. Copy `templates/quarterly.md` into `<vault>/<subdir>/Goals/Quarterly.md` if it doesn't exist.
5. Write config.json.
6. Print next steps: "Run `/work-buddy goals` to define your quarterly goals, then `/work-buddy morning` tomorrow."

### `/work-buddy goals`

- Open `Goals/Quarterly.md` for review/edit.
- If empty (only template), walk the user through adding 3–5 goals.
- Each goal entry:
  ```markdown
  ## G1: Ship API caching layer
  - id: perf-q2
  - impact: 5
  - type: delivery   # delivery | growth
  - target: end of Q2 — p95 latency < 200ms
  - notes: ...
  ```
- Validate: every goal has `id`, `impact` (1-5), `type`.

### `/work-buddy morning`

1. Resolve "yesterday" — most recent prior daily note (skip weekends if `tz` workweek; v1 just looks at last 3 days max).
2. Read yesterday's note → extract unchecked items from *Planned*.
3. Create today's note from `templates/daily.md` if missing.
4. Pre-fill *Carried over from yesterday* with unchecked items.
5. Ask user: "What else are you planning today?" — capture as new tasks.
6. For each task, prompt the user to link a goal id (`→ perf-q2`). Optional but encouraged.
7. Rank tasks: sort by `(goal.impact desc, urgency asc)`. Surface top 3 as "Focus today".
8. Write the note.

### `/work-buddy now`

- Read today's note.
- From unchecked tasks in *Planned* (incl. carry-overs), pick the highest `impact`.
- If multiple tied, ask "which feels most urgent?".
- Output one task. Just one.

### `/work-buddy eod`

1. Read today's note.
2. For each task in *Planned*, ask: done / missed / partial / cancelled.
3. Move accordingly into *Done*, *Missed*, *Wins* (user-flagged), drop cancelled.
4. Prompt: "One-line reflection — what did you learn today?"
5. Prompt: "Any wins to log?" — appended to *Wins*.
6. Write the note. Print summary: `3 done · 1 missed · 2 wins`.

### `/work-buddy weekly`

1. Determine ISO week. List daily notes in that range.
2. Aggregate:
   - Total done / missed / wins.
   - Per-goal progress: `# done tasks linked to goal / # planned tasks linked to goal`.
   - Top wins (verbatim).
   - Missed-task patterns (same task carried over 3+ days = blocker candidate).
3. Prompt user for weekly reflection (open-ended) + "what got better this week?" (growth).
4. Write `Weekly/<YYYY>-W<nn>.md` from `templates/weekly.md` with the aggregates filled.
5. Print a one-screen summary.

---

## Templates

### `templates/daily.md`

```markdown
---
date: {{date}}
week: {{iso_week}}
---

# {{date_human}}

## Planned
<!-- carried-over items appear here, then new items -->

## Done

## Missed

## Wins

## Reflection
<!-- one line: what I learned today -->
```

### `templates/weekly.md`

```markdown
---
week: {{iso_week}}
range: {{monday}} → {{sunday}}
---

# Week {{iso_week}}

## Stats
- Done: {{done_count}}
- Missed: {{missed_count}}
- Wins: {{wins_count}}

## Goal progress
{{per_goal_table}}

## Top wins
{{top_wins}}

## Blockers (carried 3+ days)
{{blockers}}

## Reflection

## Growth — what got better this week
```

### `templates/quarterly.md`

```markdown
# Quarterly goals — {{quarter}}

> Each goal: short id, impact 1–5, type delivery|growth, a measurable target.

## G1: <title>
- id: <slug>
- impact: 3
- type: delivery
- target: <measurable outcome by end of quarter>
- notes:

## G2: ...
```

### `templates/goal.md`

Used when adding a single goal interactively.

```markdown
## G{{n}}: {{title}}
- id: {{id}}
- impact: {{impact}}
- type: {{type}}
- target: {{target}}
- notes:
```

---

## Task line format

Tasks in daily notes are standard markdown checkboxes with an optional goal pointer:

```markdown
- [ ] Investigate cache hit ratio drop → perf-q2
- [x] Pair with Sara on retry logic → growth-distsys
- [ ] Untagged chore (no goal link)
```

The `→ <id>` suffix is the only metadata. Parser regex: `→\s*([a-z0-9-]+)\s*$`.

---

## Helper script `helpers/wb.py`

Pure-stdlib Python 3. Exposes:

- `today_path(config) -> Path`
- `date_path(config, date) -> Path`
- `weekly_path(config, iso_year, iso_week) -> Path`
- `latest_prior_daily(config, max_lookback_days=5) -> Path | None`
- `parse_daily(path) -> {planned: [Task], done: [...], missed: [...], wins: [...], reflection: str}`
- `parse_goals(path) -> [{id, title, impact, type, target}]`
- `render_daily(template_path, ctx) -> str`
- `iso_week_for(date) -> (year, week)`
- `week_range(year, week) -> (monday, sunday)`

Each subcommand prompt invokes `wb.py` via shell, gets JSON back, then drives the conversation.

`Task` shape:
```python
{"text": str, "checked": bool, "goal_id": str | None, "raw": str}
```

The skill itself does the LLM-y parts (prompting user, prioritizing, summarizing). `wb.py` is purely deterministic file I/O + parsing.

---

## SKILL.md (Claude Code entry point)

Frontmatter declares the skill; body is a router that reads the user's argument and dispatches to the matching `commands/<sub>.md`. Routing rules:

- No arg → run `morning` if today's note doesn't exist, else `now`.
- Unknown arg → list subcommands.
- Before any subcommand except `init`, verify `config.json` exists; if not, run `init` first.

## INSTRUCTIONS.md (Codex)

Same content as SKILL.md, formatted as plain instructions (no Claude Code-specific frontmatter). The user references this manually when running Codex.

---

## Install

`install.sh` does:

```bash
mkdir -p "$HOME/.claude/skills"
ln -sfn "$(pwd)" "$HOME/.claude/skills/work-buddy"
echo "Installed. Restart Claude Code, then run /work-buddy init"
```

A symlink so edits in the repo are live.

---

## cron-suggested.txt

For when the user is ready to add automation:

```
# Weekday 09:00 — open today's plan in your editor (one example, user adapts)
0 9 * * 1-5 osascript -e 'display notification "Time to plan today" with title "work-buddy"'

# Friday 17:00 — nudge for weekly review
0 17 * * 5 osascript -e 'display notification "Run /work-buddy weekly" with title "work-buddy"'
```

Not installed. Just documentation.

---

## Test plan (manual, v1)

1. Fresh install → `/work-buddy morning` triggers init.
2. Init with bogus path → re-prompts.
3. Init with valid path → creates dirs + Goals/Quarterly.md.
4. `/work-buddy goals` → can add goals; saved correctly.
5. `/work-buddy morning` on day 1 → no carry-over, just new tasks.
6. `/work-buddy eod` → marks tasks, writes Done/Missed/Wins.
7. `/work-buddy morning` on day 2 → yesterday's missed items appear in Planned.
8. `/work-buddy now` → returns single highest-impact task.
9. After 5+ daily notes, `/work-buddy weekly` → produces accurate aggregates.
10. Tasks with no goal link still work; just don't contribute to goal progress.

---

## Future (post-v1)

- Slack webhook nudges via cron.
- Pull done items from git commits / merged PRs.
- Quarterly review subcommand.
- Multi-vault support.
- Mobile-friendly via Obsidian Sync (already works — vault is plain MD).
