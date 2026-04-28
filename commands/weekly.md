# work-buddy weekly

You are generating the weekly review.

## Step 1 — Determine the ISO week

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json iso-week
```
Returns `{"year": 2026, "week": 18}`. Store as `ISO_YEAR` and `ISO_WEEK`.

Get the week's date range:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  week-range --year <ISO_YEAR> --week <ISO_WEEK>
```
Returns `{"monday": "2026-04-27", "sunday": "2026-05-03"}`.

Get the weekly note path:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json weekly-path
```
Returns `{"path": "/path/to/Weekly/YYYY-Wnn.md"}`. Store as `WEEKLY_PATH`.

## Step 2 — Collect daily notes for the week

For each date from Monday to today (inclusive), compute the path:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  date-path --date <YYYY-MM-DD>
```
Returns `{"path": "..."}`. Check if the file exists, skip if missing.

For each existing daily note, run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-daily --path "<path>"
```

## Step 3 — Load goals

Derive Quarterly.md path from config and run:
```bash
python3 -c "
import json, pathlib
cfg = json.loads(pathlib.Path('$HOME/.claude/skills/work-buddy/config.json').read_text())
print(pathlib.Path(cfg['vault_path']) / cfg.get('subdir','work-buddy') / 'Goals' / 'Quarterly.md')
"
```
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-goals --path "<quarterly_path>"
```
Build `id → {title, impact}` map.

## Step 4 — Aggregate stats

From all parsed daily notes, compute:
- `done_count`: total tasks across all `done` arrays
- `missed_count`: total tasks across all `missed` arrays
- `wins_count`: total tasks across all `wins` arrays

Per-goal progress: for each goal id, count:
- `planned_count`: tasks in any `planned` array with that `goal_id` (including those moved to done/missed)
- `done_count_goal`: tasks in any `done` array with that `goal_id`

Render per_goal_table as markdown:
```
| Goal | Done | Planned | Progress |
|------|------|---------|----------|
| perf-q2 — Ship API caching layer | 4 | 6 | 67% |
```

Top wins: collect all `wins` items across the week. Keep the text of each, deduplicated.

Blocker detection: find task `text` values that appear in `missed` or `planned` (unchecked) across 3 or more distinct daily notes. List these as blockers.

## Step 5 — Prompt user for reflection

Ask:
> "Weekly reflection: How did this week go overall? (open-ended)"

Ask:
> "What got better this week? (growth, skills, process, relationships)"

## Step 6 — Write the weekly note

Build the context for the template:
```json
{
  "done_count": N,
  "missed_count": N,
  "wins_count": N,
  "per_goal_table": "| ... |",
  "top_wins": "- win 1\n- win 2",
  "blockers": "- blocker 1\n- blocker 2"
}
```

Write the file using the weekly template, filling in all `{{placeholder}}` values. Also append the user's reflection and growth responses to the `## Reflection` and `## Growth` sections.

Create the file at `WEEKLY_PATH` (create parent dir if needed):
```bash
mkdir -p "$(dirname <WEEKLY_PATH>)"
```

Use Python to write the file with the filled content — you can generate the markdown directly from the template placeholders.

## Step 7 — Print summary

Print a one-screen summary:
> "Week <ISO_YEAR>-W<ISO_WEEK> (<monday> → <sunday>)
> 
> Done: <done_count> · Missed: <missed_count> · Wins: <wins_count>
> 
> Goal progress:
> <per_goal_table>
> 
> Blockers: <blockers or 'none'>
> 
> Weekly note saved to: <WEEKLY_PATH>"
