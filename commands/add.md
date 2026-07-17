# work-buddy add

Quick mid-day task append. Use this when the user wants to add an item without going through the full `morning` flow.

## Step 1 — Capture the task text

If the user invoked with arguments after `add` (e.g. `/work-buddy add Investigate flaky test`), use that text. Otherwise ask:

> "What's the task? (one line)"

## Step 2 — Auto-prompt for a goal link

Always ask, even if the user already typed `→ <id>` inline (then confirm or override):

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-goals --path "$HOME/$(python3 -c 'import json,pathlib;c=json.loads(pathlib.Path.home().joinpath(".claude/skills/work-buddy/config.json").read_text());print(pathlib.Path(c["vault_path"]).joinpath(c.get("subdir","work-buddy"),"Goals/Quarterly.md").relative_to(pathlib.Path.home()))')"
```

(Or simpler: derive the path the same way every other command does.)

Show the available goal ids as a hint:
> "Which goal does this support? (perf-q2 · growth-distsys · team-hiring) — type the id, or press Enter to skip."

If the user skips, `goal_id` is null.

## Step 3 — Off-plan?

Ask only if relevant (the user said something like "I just did this" rather than "I'm going to do this"). Otherwise default to off-plan=false.

> "Was this work already done off-plan, or is it on the to-do list?"

If "already done off-plan": pass `--off-plan` and the helper will mark it. (Note: in v1, `append-task` only adds to `planned`. For "already done off-plan" items, prefer logging via `eod` or `catchup`, where they go directly into `done`.)

## Step 3.5 — Cross-team? (optional)

If the task obviously depends on or involves another team, capture it — this seeds the manager report's cross-team surfacing:

> "Another team involved? (e.g. devops, geo-data — Enter to skip)"

Pass named teams via `--with` (comma-separated). Skip freely.

## Step 4 — Append

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  append-task --text "<task text>" --goal "<goal_id or omit>" --with "<team1,team2 or omit>"
```

Returns `{"status": "ok", "path": "...", "created": bool, "planned_count": N}`.

## Step 5 — Confirm

> "Added. Today now has <planned_count> planned items. Run `/work-buddy now` for the next move."
