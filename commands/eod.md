# work-buddy eod

You are helping the user close out their day.

## Step 1 — Load today's note

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json today-path
```
Returns `{"path": "..."}`. Check it exists:
```bash
test -f "<TODAY_PATH>" && echo "exists" || echo "missing"
```

If missing:
> "No plan found for today. Did you run `/work-buddy morning`?"

## Step 2 — Parse today's note

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-daily --path "<TODAY_PATH>"
```

Returns `{date, iso_week, planned, done, missed, wins, reflection}`.

Start with the existing `done`, `missed`, `wins` arrays — the user may have already completed some reviews.

Collect the unresolved tasks: tasks from `planned` that are not already in `done` or `missed`. Match by `raw` string.

## Step 3 — Review each unresolved planned task

For each unresolved task in `planned`, ask:
> "Task: <task text> [goal: <goal_id or none>]
> Status? (done / missed / partial / cancelled)"

Accept single letters: d=done, m=missed, p=partial, c=cancelled.

- **done** → move to `done` list with `checked: true`
- **missed** → move to `missed` list with `checked: false`
- **partial** → move to `missed` list, append ` (partial)` to text if not already there
- **cancelled** → drop entirely (do not add to any list)

If the user says "done" for a task, also ask:
> "Was this a notable win? (y/n)"
If yes, add it to `wins` as well.

## Step 4 — Reflection

Ask:
> "One-line reflection — what did you learn today? (press Enter to skip)"

Store the response in `reflection`.

## Step 4.5 — End-of-day energy

Ask:
> "Energy at end of day, 1–5? (or skip)"

Capture as integer 1–5 or null. Store as `energy_eod` in the JSON. Preserve the existing `mood`, `energy`, and `kickstarts` from the parsed note — do not overwrite them.

## Step 5 — Additional wins

Ask:
> "Any other wins to log? (separate by newlines, or press Enter to skip)"

For each win text entered, add `{"text": "<text>", "checked": true, "goal_id": null, "raw": "- [x] <text>"}` to `wins`.

## Step 6 — Write the updated note

Build the updated JSON, preserving frontmatter fields AND any custom sections:
```json
{
  "date": "<date>",
  "iso_week": "<iso_week>",
  "mood": "<preserve existing>",
  "energy": <preserve existing>,
  "energy_eod": <from step 4.5 or null>,
  "kickstarts": <preserve existing count>,
  "planned": [tasks still unresolved],
  "done": [tasks moved to done],
  "missed": [tasks moved to missed],
  "wins": [win items],
  "reflection": "<reflection text>",
  "raw_sections": <pass through from parse-daily — preserves user-added sections like ## Notes>
}
```

Note: `planned` should contain only unchecked (unresolved) tasks after processing. Completed tasks move out of `planned` into `done`/`missed`.

Write the JSON to a temp file with a single-quoted heredoc, then call `write-daily --from-file` (avoids any shell-escape issues with apostrophes / quotes in task text):

```bash
cat > /tmp/wb-eod-payload.json <<'PAYLOAD'
<json here>
PAYLOAD

python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  write-daily --path "<TODAY_PATH>" --from-file /tmp/wb-eod-payload.json
```

**Never use `echo '<json>' | ...`** — apostrophes/quotes inside task text break the pipe.

## Step 7 — Print summary

Count: done tasks, missed tasks, wins.

Print:
> "Day closed. <done_count> done · <missed_count> missed · <wins_count> wins
> 
> Missed tasks will carry over to tomorrow's plan.
> Run `/work-buddy weekly` on Friday to review your week."
