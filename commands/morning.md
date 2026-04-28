# work-buddy morning

You are helping the user plan their day.

## Step 1 — Resolve paths

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json today-path
```
Returns `{"path": "/path/to/Daily/YYYY-MM-DD.md"}`. Store as `TODAY_PATH`.

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json latest-prior-daily
```
Returns `{"path": "/path/to/prior.md"}` or `{"path": null}`. Store as `PRIOR_PATH`.

## Step 2 — Load goals for impact lookup

Derive the Quarterly.md path from config:
```bash
python3 -c "
import json, pathlib
cfg = json.loads(pathlib.Path('$HOME/.claude/skills/work-buddy/config.json').read_text())
print(pathlib.Path(cfg['vault_path']) / cfg.get('subdir','work-buddy') / 'Goals' / 'Quarterly.md')
"
```

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-goals --path "<quarterly_path>"
```
Returns an array of `{"id", "title", "impact", "type", "target", "notes"}`. Build an `id → impact` lookup map.

## Step 3 — Extract carry-overs from yesterday

If `PRIOR_PATH` is not null:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-daily --path "<PRIOR_PATH>"
```
Returns:
```json
{
  "date": "YYYY-MM-DD",
  "iso_week": "YYYY-Wnn",
  "planned": [{"text": "...", "checked": false, "goal_id": "perf-q2", "raw": "- [ ] ..."}],
  "done": [...],
  "missed": [...],
  "wins": [...],
  "reflection": "..."
}
```

Carry-overs = items in `planned` where `checked == false`.
Also include items in `missed` from yesterday.
Deduplicate by `raw` string.

If no prior note, carry-overs = [].

## Step 4 — Create today's note if missing

Check if `TODAY_PATH` exists:
```bash
test -f "<TODAY_PATH>" && echo "exists" || echo "missing"
```

If missing, render it:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  render-daily
```
This prints the filled daily template to stdout. Write it to `TODAY_PATH`:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  render-daily > "<TODAY_PATH>"
```

## Step 5 — Show carry-overs and ask for new tasks

If carry-overs exist, show them:
> "Carried over from yesterday:
> - [ ] Investigate cache hit ratio drop → perf-q2
> - [ ] Update runbook"

Ask:
> "What else are you planning today? List your tasks (one per line, or say 'done' when finished)."

Collect new tasks. For each new task, ask:
> "Which goal does '<task>' support? Enter a goal id from your list, or press Enter to skip."

Show the available goal ids as a hint: e.g. `(perf-q2 · growth-distsys · team-hiring)`

Format each task as:
- With goal: `- [ ] <text> → <goal_id>`
- Without goal: `- [ ] <text>`

## Step 6 — Rank and select focus tasks

Combine carry-overs + new tasks. For each, look up `impact` from the goals map (default 0 if no goal link).

Sort by:
1. `impact` descending
2. Tasks with goal links before unlinked tasks
3. Carry-overs before new tasks (tiebreak)

Pick the top 3 as "Focus today".

## Step 7 — Write today's note

Build the JSON:
```json
{
  "date": "YYYY-MM-DD",
  "iso_week": "YYYY-Wnn",
  "planned": [all tasks as Task objects],
  "done": [],
  "missed": [],
  "wins": [],
  "reflection": ""
}
```

Run:
```bash
echo '<json>' | python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  write-daily --path "<TODAY_PATH>"
```

## Step 8 — Output summary

Print:
> "Today's plan saved to <TODAY_PATH>
> 
> Focus today (by goal impact):
> 1. <task 1>
> 2. <task 2>
> 3. <task 3>
> 
> Run `/work-buddy now` anytime to get your next task. Run `/work-buddy eod` at end of day."
