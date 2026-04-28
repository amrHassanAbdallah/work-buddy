# work-buddy goals

You are helping the user review and edit their quarterly goals.

## Step 1 — Locate Quarterly.md

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-goals \
  --path "$(python3 -c "
import json, pathlib
cfg = json.loads(pathlib.Path('$HOME/.claude/skills/work-buddy/config.json').read_text())
print(pathlib.Path(cfg['vault_path']) / cfg.get('subdir','work-buddy') / 'Goals' / 'Quarterly.md')
")"
```

The output is a JSON array of goals:
```json
[
  {"id": "perf-q2", "title": "Ship API caching layer", "impact": 5, "type": "delivery", "target": "p95 latency < 200ms by end of Q2", "notes": ""},
  ...
]
```

## Step 2 — Check if goals exist

If the array is empty or all entries have placeholder values (id is empty or `<slug>`), the file is unfilled. Tell the user:
> "Your Quarterly.md is still blank. Let's add your goals for this quarter."

If goals exist, show them as a numbered list:
```
1. [impact:5] perf-q2 — Ship API caching layer (delivery)
   Target: p95 latency < 200ms by end of Q2
```
Ask: "Would you like to add a new goal, edit an existing one, or are you done?"

## Step 3 — Add goals interactively (if needed)

For each new goal, ask in sequence:
1. "Goal title?" (short phrase)
2. "Short slug/id? (lowercase, hyphens only, e.g. perf-q2)"
3. "Impact score? (1=low, 5=critical)"
4. "Type? delivery or growth"
5. "Measurable target by end of quarter?"
6. "Any notes? (optional, press Enter to skip)"

Validate:
- `id` must match `^[a-z0-9-]+$`
- `impact` must be 1–5
- `type` must be `delivery` or `growth`

Repeat until the user says done. Aim for 3–5 goals total.

## Step 4 — Write goals back

Build the JSON structure:
```json
{
  "quarter": "Q2 2026",
  "goals": [
    {"id": "perf-q2", "title": "Ship API caching layer", "impact": 5, "type": "delivery", "target": "p95 < 200ms", "notes": ""},
    ...
  ]
}
```

Pipe it to `write-goals`:
```bash
echo '<json>' | python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  write-goals \
  --path "<quarterly_md_path>"
```

Output is `{"status": "ok", "path": "..."}`.

## Step 5 — Confirm

Show the final goal list and say:
> "Goals saved. Run `/work-buddy morning` to plan your day using these goals."
