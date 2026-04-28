# work-buddy weekly

You are generating the weekly review.

## Step 1 — Aggregate the week

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json weekly-aggregate
```

Returns the full week summary as JSON:

```json
{
  "year": 2026,
  "week": 18,
  "monday": "2026-04-27",
  "sunday": "2026-05-03",
  "days": [
    {"date": "...", "mood": "...", "energy": 3, "energy_eod": 4, "kickstarts": 1, "done": 4, "missed": 0, "wins": 1}
  ],
  "totals": {"done": N, "missed": N, "wins": N, "kickstarts": N, "days_logged": N},
  "energy_avg": 3.2,
  "moods": ["focused", "tired", ...],
  "per_goal": [{"id", "title", "impact", "type", "planned", "done", "missed", "progress_pct"}],
  "top_wins": ["..."],
  "blockers": [{"text", "days", "goal_id"}],
  "manager_items": [{"type", "text"}],
  "unlinked_pct": 25
}
```

Also fetch the weekly note path:

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json weekly-path
```

## Step 2 — Render markdown sections

Build these from the JSON:

**mood_table** — markdown table:
```
| Day | Mood | Energy AM | Energy PM | Kickstarts | Done |
|-----|------|-----------|-----------|------------|------|
| Mon | tired | 2 | 2 | 1 | 0 |
```
Use `—` for missing values.

**per_goal_table** — markdown table:
```
| Goal | Impact | Done | Attempted | Progress |
|------|--------|------|-----------|----------|
| Ship API caching (perf-q2) | 5 | 4 | 6 | 67% |
```

**top_wins** — bulleted list of `top_wins` strings (or `_no wins logged_` if empty).

**blockers** — bulleted list, each: `- "<text>" — carried <N> days <(goal: <title>)>`. Or `_none — clean week_` if empty.

**manager_items** — grouped by type with friendly headings:

```
### Workload / energy
- <text>

### Stalled goals
- <text>

### Blockers to unblock
- <text>

### Wins worth visibility
- <text>

### Priority alignment
- <text>
```

Only include sections that have items. If `manager_items` is empty entirely, render `_nothing flagged this week — quiet good week or quiet bad week, you decide_`.

## Step 3 — Prompt for reflection

Ask:
> "Weekly reflection — how did this week actually go? (open-ended, one paragraph or one line — your call)"

Then:
> "What got better this week? Skill, habit, relationship, anything that grew."

## Step 4 — Compose and write the weekly note

Read `templates/weekly.md` and substitute placeholders:
- `{{iso_week}}` → `<year>-W<NN>` (zero-padded)
- `{{monday}}`, `{{sunday}}` → from JSON
- `{{done_count}}`, `{{missed_count}}`, `{{wins_count}}`, `{{kickstarts_count}}` → from `totals`
- `{{energy_avg}}` → `energy_avg` value or `—` if null
- `{{mood_table}}`, `{{per_goal_table}}`, `{{top_wins}}`, `{{blockers}}`, `{{manager_items}}` → rendered above

Append the user's reflection to `## Reflection`. Append the user's growth answer to `## Growth — what got better this week`.

Write the file at the weekly-path. Create the parent directory if needed.

## Step 5 — Print summary

Print a one-screen summary that highlights manager items first (those are actionable), then stats:

> "Week <year>-W<NN> review saved → <path>
>
> **To raise with your manager:** <count> items
> <bulleted manager_items, top 3>
>
> Stats: <done> done · <missed> missed · <wins> wins · <kickstarts> kickstarts · avg energy <avg>/5"
