# work-buddy morning

You are helping the user plan their day.

## Step 0 — Check for unresolved past workdays

Before kickstart-signal check or anything else, see if the user skipped eod on any recent workdays:

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  unresolved-workdays --max-days 7
```

Returns a list (empty if all caught up). If non-empty, surface once:

> "Heads-up — N workday(s) since you last closed out:
> - <weekday> (<date>): <N items still planned> / <no note>
>
> Want to (a) catch me up via `/work-buddy catchup` (covers what you did, including off-plan stuff), (b) skip and just plan today, (c) one-day quick catchup on the most recent only?"

If (a): hand off to `commands/catchup.md`.
If (c): inline mini-catchup — walk only the most recent unresolved day using the prompts from `catchup.md` Step 3, then continue with morning.
If (b): proceed without backfill. Note that `kickstart-signals` may still flag low energy from the prior day, which is fine.

## Step 0.5 — Check kickstart signals

Before planning, check whether the user might be in a low-energy state where `/work-buddy kickstart` would serve them better:

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json kickstart-signals
```

Returns `{"suggest": bool, "reasons": [str]}`.

If `suggest` is true, surface this *once* before continuing:

> "Heads-up: signals from recent days are pointing low —
> - <reason 1>
> - <reason 2>
>
> Want to switch to `/work-buddy kickstart` (one tiny first move + why it matters), or push through with full morning planning?"

If the user says kickstart, hand off to `commands/kickstart.md`. Otherwise continue. Do NOT guilt-trip if they choose to push through.

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

## Step 6.5 — Quick mood + energy check (optional, low-friction)

Ask, in one short prompt:
> "Quick check before we save: one word for your mood, and energy 1–5? (e.g. `focused 4` — or skip)"

Parse the response. Accept formats like `focused 4`, `tired, 2`, `ok`, just `3`, etc. Empty/skip is fine.

Capture into:
- `mood`: the one-word string (or empty)
- `energy`: integer 1–5 (or null)

Do not nag. If they skip, skip.

## Step 7 — Write today's note

Build the JSON:
```json
{
  "date": "YYYY-MM-DD",
  "iso_week": "YYYY-Wnn",
  "mood": "<from step 6.5 or ''>",
  "energy": <int 1-5 or null>,
  "kickstarts": <preserve existing count if file already had one, else 0>,
  "planned": [all tasks as Task objects],
  "done": [],
  "missed": [],
  "wins": [],
  "reflection": ""
}
```

**Important**: if today's note already existed before this run (e.g. kickstart created it earlier), `parse-daily` it first and preserve **everything**: `kickstarts`, existing `wins`, `done`, `missed`, `mood`, `energy`, `energy_eod`, AND `raw_sections` (custom sections like `## Notes` the user added in Obsidian). Pass `raw_sections` through unchanged in the JSON sent to `write-daily` — `write-daily` re-emits unknown sections after Reflection so user content isn't lost.

Write the JSON to a temp file with a single-quoted heredoc (this prevents any shell-escape problems with apostrophes / quotes inside task text), then call `write-daily --from-file`:

```bash
cat > /tmp/wb-morning-payload.json <<'PAYLOAD'
<json here>
PAYLOAD

python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  write-daily --path "<TODAY_PATH>" --from-file /tmp/wb-morning-payload.json
```

**Never use `echo '<json>' | ...`** — task text containing `'` or `"` will break the pipe and either fail or corrupt the file.

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
