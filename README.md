# work-buddy

A Claude Code skill that helps you plan your day, track tasks against quarterly goals, and reflect weekly — all stored as plain markdown in your Obsidian vault.

See [DESIGN.md](./DESIGN.md) for the full design document.

## Install

```bash
./install.sh
```

This symlinks the repo into `~/.claude/skills/work-buddy`. Restart Claude Code after running it.

## First run

```
/work-buddy init     ← set your vault path, create directories
/work-buddy goals    ← define your 3–5 quarterly goals
/work-buddy morning  ← plan your first day
```

## Commands

| Command | What it does |
|---------|-------------|
| `/work-buddy init` | First-time setup: point to your Obsidian vault |
| `/work-buddy goals` | Review and edit quarterly goals in `Goals/Quarterly.md` |
| `/work-buddy morning` | Plan your day: carry-overs from yesterday + new tasks, ranked by goal impact |
| `/work-buddy now` | Get one task to work on right now (highest impact, unchecked) |
| `/work-buddy eod` | End-of-day review: mark tasks done/missed, log wins and reflection |
| `/work-buddy weekly` | Weekly review: aggregates, goal progress, blockers, reflection |
| `/work-buddy kickstart` | Tired or stuck? Picks a tiny, valuable first move, explains why it matters, grants permission to stop after it |

Running `/work-buddy` with no argument auto-selects `morning` (if today has no plan) or `now` (if it does).

## What gets tracked

- **Tasks** linked to quarterly goals (impact-ranked).
- **Mood + energy** in each daily note's frontmatter (optional, low-friction).
- **Kickstart usage** — counts how many times you needed a tiny-step nudge per day.
- **Manager-discussion items** — auto-generated weekly from blockers, stalled goals, growth wins, workload signals, and goal alignment.

`/work-buddy morning` and `/work-buddy now` will gently suggest `/work-buddy kickstart` if recent signals look low (e.g. yesterday energy ≤2, 0 tasks done, or the same task carried 3+ days).

## Vault layout

```
<vault>/work-buddy/
├── Goals/Quarterly.md   ← source of truth for goals
├── Daily/YYYY-MM-DD.md  ← one file per day
└── Weekly/YYYY-Wnn.md   ← one file per week
```

## Requirements

- Python 3 (stdlib only, no dependencies)
- macOS or Linux
