# work-buddy

A Claude Code skill that helps you plan your day, track tasks against quarterly goals, and reflect weekly — all stored as plain markdown in your Obsidian vault.

See [DESIGN.md](./DESIGN.md) for the full design document.

## Install

**Claude Code:**
```bash
./install.sh
```
Symlinks the repo into `~/.claude/skills/work-buddy`. Restart Claude Code.

**Codex:**
```bash
./install-codex.sh
```
Runs `install.sh` first (the helper script lives in the same canonical place either way), then symlinks the bundled `INSTRUCTIONS.md` into `~/.codex/prompts/work-buddy.md`. Both clients share the same config and vault.

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
| `/work-buddy add` | Quick mid-day task append, prompts for goal link |
| `/work-buddy catchup` | Backfill workdays you missed `eod` on — captures both planned-but-unreviewed work and **off-plan work you actually did** |

Running `/work-buddy` with no argument auto-selects `morning` (if today has no plan) or `now` (if it does).

## What gets tracked

- **Tasks** linked to quarterly goals (impact-ranked), with an `[off-plan]` marker for work you did that wasn't on the plan.
- **Mood + energy** in each daily note's frontmatter (optional, low-friction).
- **Kickstart usage** — counts how many times you needed a tiny-step nudge per day.
- **Manager-discussion items** — auto-generated weekly from blockers, stalled goals, growth wins, workload signals, goal alignment, and **off-plan ratio** (≥40% of completed work being off-plan flags a clarity/reactivity convo).

`/work-buddy morning` will detect unresolved past workdays and offer to catch up before planning today. `/work-buddy now` will gently suggest `/work-buddy kickstart` if recent signals look low (e.g. yesterday energy ≤2, 0 tasks done, or the same task carried 3+ days).

**Workdays** default Mon–Fri. Override with `"workdays": [1,2,3,4,5,6]` (ISO weekday: 1=Mon..7=Sun) in `~/.claude/skills/work-buddy/config.json`. Catchup respects this so non-workdays never get flagged.

## Vault layout

```
<vault>/work-buddy/
├── Goals/Quarterly.md   ← source of truth for goals
├── Daily/YYYY-MM-DD.md  ← one file per day
└── Weekly/YYYY-Wnn.md   ← one file per week
```

## Requirements

- Python 3.9+ (stdlib only, no dependencies — uses `date.fromisocalendar`)
- macOS or Linux

## Tests

```bash
python3 -m unittest tests.test_wb -v
```

23 tests covering parse/write round-trip, custom-section preservation, goal filtering, kickstart-signal gating, weekly aggregator thresholds, and CLI `--from-file` integration. No external deps — stdlib `unittest`.

## Codex / non-Claude-Code clients

Run `./build-instructions.sh` to regenerate `INSTRUCTIONS.md`, which bundles the router and every subcommand into one file. Paste it into Codex context and the model has the full skill.

Re-run after editing any `commands/*.md` or `SKILL.md`.

## Notes / known limits

- **Slash-command args**: `/work-buddy morning` should work directly. If your client doesn't pass the trailing token through to the skill cleanly, just say `morning` (or the subcommand name) as the first thing after invoking the skill.
- **Custom Obsidian sections** (`## Notes`, `## Links`, etc.) you add to a daily note **are preserved** across `eod`/`morning` rewrites — they're parsed into `raw_sections` and re-emitted after `## Reflection`.
- **Don't rename** the canonical H2 headings (`## Planned`, `## Done`, `## Missed`, `## Wins`, `## Reflection`) — the parser matches on exact name. Adding new H2s is fine; renaming the existing ones breaks parsing.
- **Indented checkboxes are not parsed** (no nesting). Keep tasks at column 0.
