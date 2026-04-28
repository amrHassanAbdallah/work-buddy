# work-buddy catchup

Backfill unresolved past workdays. Use when the user skipped `eod` for one or more workdays and wants to retroactively close them out, including off-plan work.

**Tone**: low-pressure, memory-friendly. The user is reconstructing from memory days later. "From memory, no pressure — skip if you don't remember" should appear in every retrospective prompt.

## Step 1 — Detect unresolved workdays

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  unresolved-workdays --max-days 7
```

Returns a list of `{date, weekday, has_note, planned_unresolved, eod_done}` for workdays in the last 7 days that need attention. Already-closed days are skipped. Non-workdays (per `cfg.workdays`, default Mon–Fri) are skipped.

If the list is empty:
> "All caught up — no unresolved workdays in the last 7 days. Run `/work-buddy morning` for today."

Stop here.

## Step 2 — Summarize and confirm scope

If 1 day: just walk it.
If multiple: tell the user what's outstanding and ask scope.

> "I see N unresolved workday(s):
> - <Day1> — N items still planned, no eod
> - <Day2> — no note (might've worked off-record)
> ...
>
> Want to (a) walk through all of them, (b) just the most recent, or (c) skip and plan today?"

If (c): exit and recommend `/work-buddy morning`.
If (b): keep only the first entry.
If (a): proceed with all.

## Step 3 — For each day in scope, walk through it

For each day, ask in order:

### 3a — Did you work?

> "<Weekday> (<date>): did you work that day? (yes / off / lightly)"

If "off": skip — don't write a note (don't fabricate planned items). Move on.
If "lightly" or "yes": continue.

### 3b — If `has_note` is true: walk planned items

For each unchecked planned task (from parse-daily on the date):

> "Task: <text> [goal: <id or none>] — done / missed / cancelled? (from memory, no pressure — skip if unsure)"

Same semantics as `eod`:
- done → move to `done` with `checked: true`
- missed → move to `missed`
- cancelled → drop
- skip → leave in `planned` for now

### 3c — Off-plan work (the "what else did you do?" prompt)

This is the unique value of catchup. Always ask:

> "Anything else you actually worked on that <Weekday> that wasn't on the plan? List one per line — I'll mark them as off-plan completed work. (Skip with Enter if nothing comes to mind.)"

For each line entered, ask:
> "'<text>' — does this connect to a goal? (perf-q2 · growth-distsys · ... or skip)"

Build each as a `done` task with `off_plan: true`:
```json
{"text": "<text>", "checked": true, "goal_id": "<id or null>", "off_plan": true, "raw": ""}
```

### 3d — Mood / energy / reflection (retrospective)

Single low-friction prompt:
> "Roughly how did <Weekday> feel? One word + energy 1–5 if you remember (e.g. `productive 4`), or skip."

Plus:
> "One-line takeaway from <Weekday>? (skip if blank)"

Set `energy_eod` from the energy number (treat as eod since this is retrospective). Leave `energy` (morning energy) untouched.

## Step 4 — Write each day's note

For each day, build the full JSON (preserving existing `mood`, `energy`, `kickstarts`, `raw_sections`, etc. from the parse) with the catchup updates merged in. Use the heredoc + `--from-file` pattern:

```bash
cat > /tmp/wb-catchup-payload.json <<'PAYLOAD'
<full json>
PAYLOAD

python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  write-daily --path "<that-day-path>" --from-file /tmp/wb-catchup-payload.json
```

If the day didn't have a note (`has_note: false`) but the user said they worked, render today's-template-style content for that date first. The simplest path: build the JSON directly with the date set and pass to `write-daily` (it creates the file if missing).

## Step 5 — Summary

Print:

> "Caught up on N day(s):
> - <Day1>: <done_count> done (<off_plan_count> off-plan), <missed_count> missed
> - <Day2>: ...
>
> Now: `/work-buddy morning` to plan today."
