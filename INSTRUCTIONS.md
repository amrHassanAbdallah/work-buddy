# work-buddy — Codex instructions

This document is the Codex-readable version of the work-buddy skill. Reference it manually when running Codex by including it in your context.

## What this skill does

work-buddy helps you plan your day, track what's done vs. missed, prioritize by goal-impact, and reflect weekly — all stored as plain markdown in an Obsidian vault.

## Setup

Before using any subcommand, ensure `~/.claude/skills/work-buddy/config.json` exists and `vault_path` points to a real directory. If not, run `init` first.

Config file location: `~/.claude/skills/work-buddy/config.json`

```json
{
  "vault_path": "/Users/you/Documents/Obsidian/MyVault",
  "subdir": "work-buddy",
  "created_at": "2026-04-28T09:30:00+03:00",
  "tz": "Africa/Cairo"
}
```

Helper script: `~/.claude/skills/work-buddy/helpers/wb.py`

All `wb.py` calls: `python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json <subcommand>`

## Routing

The entry point is `SKILL.md`. For Codex usage, dispatch manually:

- No argument → check if today's note exists (`today-path`); if missing run `morning`, else run `now`.
- Known subcommand → read and follow `commands/<subcommand>.md`.
- Unknown subcommand → list available subcommands.

## Subcommands

### init
Read `commands/init.md`. Ask for vault path, validate it exists, run `wb.py init-vault`, confirm success.

### goals
Read `commands/goals.md`. Parse `Goals/Quarterly.md`, show existing goals, walk user through adding/editing goals, write back.

### morning
Read `commands/morning.md`. Load yesterday's unchecked tasks as carry-overs, ask for new tasks + goal links, rank by impact, write today's daily note.

### now
Read `commands/now.md`. Parse today's note, find highest-impact unchecked task, output exactly one task.

### eod
Read `commands/eod.md`. Walk through each planned task (done/missed/partial/cancelled), capture reflection and wins, write updated note.

### weekly
Read `commands/weekly.md`. Aggregate all daily notes for the current ISO week, compute stats and goal progress, detect blockers, prompt for reflection, write weekly note.

### kickstart
Read `commands/kickstart.md`. For low-energy / unmotivated moments: pick one valuable task, decompose it to a 2-minute physical starter, surface why it matters via the linked goal's target, and grant explicit permission to stop after the starter.

## wb.py subcommand reference

```
today-path                       → {"path": "..."}
date-path --date YYYY-MM-DD      → {"path": "..."}
weekly-path [--year Y --week W]  → {"path": "..."}
latest-prior-daily [--max-days N]→ {"path": "..." | null}
iso-week [--date YYYY-MM-DD]     → {"year": int, "week": int}
week-range --year Y --week W     → {"monday": "YYYY-MM-DD", "sunday": "YYYY-MM-DD"}
parse-daily --path PATH          → {date, iso_week, planned, done, missed, wins, reflection, raw_sections}
parse-goals --path PATH          → [{id, title, impact, type, target, notes}]
render-daily [--date YYYY-MM-DD] → markdown string (stdout)
write-daily --path PATH          → reads JSON from stdin, writes file, returns {"status":"ok","path":"..."}
write-goals --path PATH          → reads JSON from stdin, writes file, returns {"status":"ok","path":"..."}
init-vault --vault-path P [--subdir S] → creates dirs + config, returns {"status":"ok",...}
```

## Task format

```markdown
- [ ] Investigate cache hit ratio drop → perf-q2
- [x] Pair with Sara on retry logic → growth-distsys
- [ ] Untagged chore (no goal link)
```

Goal id suffix regex: `→\s*([a-z0-9-]+)\s*$`

## Task JSON shape

```json
{"text": "Investigate cache hit ratio drop", "checked": false, "goal_id": "perf-q2", "raw": "- [ ] Investigate cache hit ratio drop → perf-q2"}
```

## Goal JSON shape

```json
{"id": "perf-q2", "title": "Ship API caching layer", "impact": 5, "type": "delivery", "target": "p95 < 200ms by end of Q2", "notes": ""}
```
