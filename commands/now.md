# work-buddy now

You are helping the user decide what to work on right now.

## Step 0 — Kickstart signal check

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json kickstart-signals
```

Returns `{"suggest": bool, "reasons": [str]}`. If `suggest` is true, surface gently *once* before picking:

> "(Quick note: <reason 1>. If you'd rather start tiny instead of just-the-next-thing, try `/work-buddy kickstart`. Otherwise:)"

Then continue. Do NOT block waiting for a response — proceed to pick the task; the user can interrupt if they want kickstart.

## Step 1 — Load today's note

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json today-path
```
Returns `{"path": "..."}`. Check if the file exists:
```bash
test -f "<TODAY_PATH>" && echo "exists" || echo "missing"
```

If missing, tell the user:
> "No plan for today yet. Run `/work-buddy morning` first to create today's plan."

## Step 2 — Parse today's note

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-daily --path "<TODAY_PATH>"
```

Extract `planned` tasks where `checked == false`. These are the remaining tasks.

If all tasks are checked (or `planned` is empty):
> "Everything on your list is done. Great work! Consider running `/work-buddy eod` to close out the day."

## Step 3 — Load goals for impact lookup

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
Build an `id → impact` map from the result.

## Step 4 — Pick one task

From the unchecked tasks in `planned`:
1. Assign each task its `impact` score (from `goal_id` lookup; default 0 if no goal).
2. Find the maximum impact score.
3. Collect all tasks with that maximum score.

If there is exactly one top-impact task, output it directly.

If there are multiple tied tasks, ask:
> "These tasks are tied (impact: <N>). Which feels most urgent right now?
> 1. <task A>
> 2. <task B>
> ..."

Wait for the user to pick a number.

## Step 5 — Output one task

Output exactly one task:
> "Work on this next:
> 
> **<task text>**  <if goal linked: (→ <goal_id>)>
> 
> Run `/work-buddy eod` when you're done for the day."
