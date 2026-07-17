# work-buddy — bundled instructions for Codex / non-Claude-Code clients

This file is **generated** by build-instructions.sh. Do not edit by hand.
It concatenates SKILL.md and every commands/*.md so a Codex user can paste
this single file into context and the model has the full skill.

Source files: SKILL.md + commands/{init,goals,morning,now,eod,weekly,kickstart}.md

---

## Router (from SKILL.md)


# work-buddy router

You are the work-buddy skill router. Parse the first argument and dispatch to the matching subcommand prompt.

## Config pre-flight (run before every subcommand except `init`)

Resolve the config path:
```
CONFIG=$HOME/.claude/skills/work-buddy/config.json
```

Check both conditions:
1. Config file exists: `test -f "$CONFIG"`
2. vault_path inside config resolves to an existing directory

Run:
```bash
python3 -c "
import json, pathlib, sys
cfg_path = pathlib.Path.home() / '.claude' / 'skills' / 'work-buddy' / 'config.json'
if not cfg_path.exists():
    sys.exit(1)
cfg = json.loads(cfg_path.read_text())
vp = pathlib.Path(cfg.get('vault_path', ''))
sys.exit(0 if vp.exists() else 2)
"
echo "exit:$?"
```

- Exit 0 → proceed with the requested subcommand.
- Exit 1 or 2 → tell the user config is missing or vault path is invalid, then run the `init` subcommand (read `commands/init.md`).

## Unresolved-days pre-flight (run before `morning`, `now`, `add`, `kickstart`, and the no-argument path)

This is the in-tool safety net for the common "I forgot to log a day" problem: it surfaces the moment the user opens the tool, regardless of which command they reached for. Skip it for `init`, `goals`, `catchup` (it *is* the catchup flow), and `weekly` (it has its own review).

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py \
  --config ~/.claude/skills/work-buddy/config.json \
  reminder-status
```

Returns `{"needs_reminder": bool, "unresolved": [...], "message": str}`. If `needs_reminder` is true, surface **once**, low-pressure, then continue with whatever the user asked for:

> "Before we dive in — <message>. Want to `/work-buddy catchup` first, or keep going?"

Do not block. If the user keeps going, proceed with the requested subcommand. `morning`'s own Step 0 covers the same ground, so if you're routing to `morning`, let it handle this and don't double-prompt.

## Routing

The skill is invoked as `/work-buddy [subcommand]`.

### No argument

Check if today's daily note exists:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py \
  --config ~/.claude/skills/work-buddy/config.json \
  today-path
```
Then: `test -f "<path>" && echo "exists" || echo "missing"`

- Missing → run `morning` subcommand.
- Exists → run `now` subcommand.

### Known subcommands

| Argument | Prompt file to read and execute |
|----------|---------------------------------|
| `init`   | `commands/init.md`              |
| `goals`  | `commands/goals.md`             |
| `morning`| `commands/morning.md`           |
| `now`    | `commands/now.md`               |
| `eod`    | `commands/eod.md`               |
| `weekly` | `commands/weekly.md`            |
| `report` | `commands/report.md`            |
| `kickstart` | `commands/kickstart.md`      |
| `add`    | `commands/add.md`               |
| `catchup`| `commands/catchup.md`           |

Read the corresponding `commands/<sub>.md` file and follow its instructions exactly.

### Unknown argument

Print:
> "Unknown subcommand: '<arg>'
> 
> Available subcommands:
> - `/work-buddy init`    — First-time setup: configure vault path
> - `/work-buddy goals`   — Review and edit quarterly goals
> - `/work-buddy morning` — Plan your day (carry-overs + new tasks)
> - `/work-buddy now`     — What to work on right now (one task)
> - `/work-buddy eod`     — End-of-day review: mark done/missed, log wins
> - `/work-buddy weekly`  — Weekly review and reflection
> - `/work-buddy report`  — Draft a manager-facing weekly impact update (what shipped, tied to goals)
> - `/work-buddy kickstart` — Tired/stuck? Picks a tiny, valuable first move and explains why it matters
> - `/work-buddy add`      — Quick mid-day task append with goal-link prompt
> - `/work-buddy catchup`  — Backfill missed eod days (incl. off-plan work you did)
> 
> Run with no argument to auto-detect: morning if today has no plan, now if it does."

## Helper script location

All `wb.py` invocations use:
```
~/.claude/skills/work-buddy/helpers/wb.py
```
with `--config ~/.claude/skills/work-buddy/config.json`.


---

## Subcommand: init (from commands/init.md)

# work-buddy init

You are setting up work-buddy for the first time.

## Step 1 — Vault path

Ask the user:
> "What is the absolute path to your Obsidian vault? (e.g. /Users/you/Documents/Obsidian/MyVault)"

Validate that the path exists on disk using the Bash tool:
```bash
test -d "<path>" && echo "exists" || echo "missing"
```
If missing, tell the user it doesn't exist and ask again. Repeat until valid.

## Step 2 — Subdirectory name

Ask:
> "What subdirectory should work-buddy use inside the vault? (default: work-buddy)"

Accept blank to use the default `work-buddy`.

## Step 3 — Run init-vault

Run:
```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py \
  init-vault \
  --vault-path "<vault_path>" \
  --subdir "<subdir>"
```

This will:
- Create `<vault>/<subdir>/Goals/`, `Daily/`, and `Weekly/` directories.
- Copy `templates/quarterly.md` to `<vault>/<subdir>/Goals/Quarterly.md` if it doesn't exist.
- Write `~/.claude/skills/work-buddy/config.json`.

The command outputs JSON:
```json
{"status": "ok", "config_path": "...", "work_dir": "..."}
```

If it errors, show the error and ask the user to fix the input.

## Step 4 — Confirm and next steps

Tell the user:
> "Setup complete. Your work-buddy vault is at <work_dir>.
> 
> Next steps:
> 1. Run `/work-buddy goals` to define your quarterly goals.
> 2. Run `/work-buddy morning` to plan your first day."


---

## Subcommand: goals (from commands/goals.md)

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

Write the JSON to a temp file via single-quoted heredoc (avoids shell-escape problems if any goal title contains apostrophes/quotes), then call `write-goals --from-file`:

```bash
cat > /tmp/wb-goals-payload.json <<'PAYLOAD'
<json here>
PAYLOAD

python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  write-goals --path "<quarterly_md_path>" --from-file /tmp/wb-goals-payload.json
```

**Never use `echo '<json>' | ...`** — quotes inside titles or notes will break the pipe.

Output is `{"status": "ok", "path": "..."}`.

## Step 5 — Confirm

Show the final goal list and say:
> "Goals saved. Run `/work-buddy morning` to plan your day using these goals."


---

## Subcommand: morning (from commands/morning.md)

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


---

## Subcommand: now (from commands/now.md)

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


---

## Subcommand: eod (from commands/eod.md)

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

### Impact capture (done tasks only)

This is what makes the weekly **manager report** strong. For each task marked **done** — especially goal-linked ones — ask one optional, low-friction question while it's fresh:

> "One line — what did this ship or who did it unblock? (Enter to skip)"

If the user answers, set the task's `impact` field to that text (a free-text outcome statement, e.g. "unblocked Marketplace's integration"). If they skip, leave `impact` null — never fabricate impact.

Then, if the work involved another team, capture it:

> "Any other team involved? (e.g. devops, geo-data — Enter to skip)"

Set the task's `with_teams` field to a list of the named teams (lowercase, hyphenated). This surfaces cross-team work in the report and seeds dependency tracking.

Keep both prompts genuinely optional — a fast "Enter, Enter" must stay frictionless. Don't nag; ask once per done task.

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

Each task object carries: `text`, `checked`, `goal_id`, `off_plan`, `with_teams` (list, e.g. `["devops"]`), `impact` (free-text outcome or null), `raw`. Preserve `with_teams`/`impact` you didn't change; set them from the impact-capture step above. `write-daily` re-emits them inline as `[with: ...]` and `— impact: ...` so they round-trip.

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


---

## Subcommand: kickstart (from commands/kickstart.md)

# work-buddy kickstart

You are helping a user who is tired, low-energy, unmotivated, or just stuck. Your job is to lower the activation energy to start *one* valuable task, and to remind them why it matters.

## Step 0 — Log the kickstart attempt

Before anything else, increment the kickstart counter on today's daily note. This will create today's note from the template if it doesn't exist yet:

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json bump-kickstart
```

Returns `{"kickstarts": N, "path": "...", "created": bool}`. If `kickstarts >= 4` for today, gently note: "This is your <Nth> kickstart today — that's a real signal. Worth flagging in your weekly review and maybe with your manager." Then continue.


**Tone rules — read these before doing anything:**
- Acknowledge the state. Don't pretend it's a normal day.
- Be specific. Generic encouragement ("you got this!") is forbidden — it sounds hollow and the user will tune it out.
- Frame the tiny step as physical and concrete. Not "start working on X" — instead: "open the file `foo.py` and read the top function. That's it."
- Always give explicit permission to stop after the tiny step. Removing the obligation to continue is what makes starting easy.
- If momentum kicks in, the user can invoke `/work-buddy now` themselves. Don't assume they will.

## Step 1 — Brief check-in

Ask:
> "What's the vibe — tired, scattered, no motivation, or just stuck staring at the list? Tell me in a sentence (or skip)."

Listen but do not analyze. Just acknowledge in one short line: "Got it — let's make this tiny."

## Step 2 — Load today's plan (or fall back)

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json today-path
```

If today's note exists, run `parse-daily` on it and use unchecked items in `planned`.

If today's note does NOT exist, run `latest-prior-daily` and parse that. Pull unchecked `planned` + items in `missed`. Tell the user: "No plan for today yet — picking from yesterday's carry-overs. We'll do `/work-buddy morning` properly later."

If there's nothing to pull from at all (fresh user, no plans yet), parse `Goals/Quarterly.md` and synthesize 2–3 candidate first-moves directly from goal `target` text. Skip to Step 4.

## Step 3 — Load goals for meaning + impact

Derive Quarterly.md path from config (same recipe as `morning.md`), then:

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  parse-goals --path "<quarterly_path>"
```

Build a map `goal_id → {title, impact, type, target, notes}`.

## Step 4 — Pick the candidate

Score each candidate task:
1. Tasks with a `goal_id` resolving to a real goal beat unlinked tasks.
2. Among linked tasks, sort by `impact` descending.
3. Tiebreak by carry-over status (carry-overs first — they've been waiting).

Pick the top one.

If the top two are tied on impact AND both linked, briefly ask:
> "Two candidates — which feels less heavy right now?
> A) <task A>
> B) <task B>"

Otherwise just commit to the pick. Don't paralyze them with options.

## Step 5 — Decompose to a 2-minute starter

This is the hard part. You must invent the smallest physical action that makes any progress on the picked task. Use judgment based on the task text.

Examples of good 2-minute starters:
- Task "Investigate cache hit ratio drop" → "Open Grafana, look at the cache panel for 60 seconds. Don't fix anything. Just look."
- Task "Write design doc for retry logic" → "Open a new doc. Type one sentence: what problem this solves. Just that sentence."
- Task "Review Sara's PR" → "Open the PR, read the description, scroll the diff once. No comments yet."
- Task "Fix flaky test in auth_test.py" → "Run the test 3 times. Watch which line flakes. That's it."

Rules for the starter:
- It must be physical (open, type, run, read, scroll) — never abstract ("think about", "consider").
- It must be completable in ≤5 minutes.
- It must produce *some* artifact or observation (so it counts as real progress).
- Do NOT chain multiple steps. One starter only.

Output it as:

> **The starter:** <one sentence describing the physical action>
>
> Time budget: 2 minutes. When that's done, you have full permission to stop.

## Step 6 — Surface why this matters

Look up the picked task's `goal_id`. If linked:

> **Why this matters:** This task supports **<goal title>** — your target there was *"<goal.target>"*.
>
> <One sentence on the connection — be specific. e.g. "Even a 60-second look at the cache panel rules out half the hypotheses, which gets you closer to that p95 number." Use goal.notes if present for extra context.>

If `type: growth`, also add:
> This is a growth goal, not a delivery one — the value is in the practice, not just the output.

If the task has NO `goal_id`:

> **Heads up:** this task isn't linked to a goal. That's part of why it feels heavy — there's no thread back to anything you're trying to grow toward.
>
> Two options:
> 1. Do it anyway as maintenance work (totally valid — not everything needs a goal).
> 2. Tell me which goal it actually serves and I'll link it.

Wait for an answer before proceeding. If they pick (2), perform the link mutation:

1. Re-parse today's note: `parse-daily --path "$TODAY_PATH"`.
2. Walk the parsed `planned` array (and `missed` if the task came from there) to find the entry whose `text` matches the picked task. Set its `goal_id` to the chosen goal id.
3. Pass the *entire parsed JSON* (including `raw_sections`, `mood`, `energy`, `energy_eod`, `kickstarts`) to `write-daily` via heredoc + `--from-file` (never `echo`, to avoid shell-escape issues with quotes/apostrophes):
   ```bash
   cat > /tmp/wb-kickstart-payload.json <<'PAYLOAD'
   <full parsed json with mutated goal_id>
   PAYLOAD

   python3 ~/.claude/skills/work-buddy/helpers/wb.py \
     --config ~/.claude/skills/work-buddy/config.json \
     write-daily --path "$TODAY_PATH" --from-file /tmp/wb-kickstart-payload.json
   ```
4. Confirm: "Linked to <goal title>. Now: <starter>"

Do NOT clobber the file by writing only the fields you care about — pass everything through so kickstart count, custom sections, etc. are preserved.

## Step 7 — Permission and exit

Close with:

> Do just the starter. That's the whole deal. If momentum carries you further, run `/work-buddy now` for the next task. If not, you've already moved the needle today — log it with `/work-buddy eod` later, or just tell me "done" and I'll add it to today's wins now.

## Step 8 — Optional immediate logging

If the user replies "done", "did it", "ok", or anything similar indicating they completed the starter (be lenient in interpretation):

1. Re-parse today's note (it definitely exists — Step 0 created it). Run `parse-daily --path "$TODAY_PATH"`.
2. Append to the parsed `wins` array:
   ```json
   {"text": "Kickstart: <starter description>", "checked": true, "goal_id": "<linked goal or null>", "raw": ""}
   ```
   (Leave `raw` empty — `write-daily` regenerates it.)
3. Pass the *full parsed JSON* (including `raw_sections`, mood, energy, energy_eod, kickstarts) into `write-daily` via the same heredoc + `--from-file` pattern shown above.
4. Reply: "Logged. That counts. Rest if you need to."

Do NOT push them to do another task. The whole point of this command is that finishing the starter = success.


---

## Subcommand: add (from commands/add.md)

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


---

## Subcommand: catchup (from commands/catchup.md)

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


---

## Subcommand: weekly (from commands/weekly.md)

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


---

## Subcommand: report (from commands/report.md)

# work-buddy report

Generate a **manager-facing weekly impact update** from the week's logged work — an impact-framed digest the user reviews and sends to their manager (1:1, Slack, review doc). This is the outward-facing counterpart to `weekly`, which is an inward self-review.

**Why this exists**: logged work that never reaches the manager shows up as a rating gap ("I did Exceed work, I was scored Meet"). This turns the same daily notes into the impact story — what shipped, tied to which goal, plus cross-team / beyond-scope work that's easy to overlook.

**Tone**: confident and factual, not boastful. Impact statements ("shipped X → unblocked Y"), not task dumps. Never invent impact the notes don't support — if a task has no logged impact, state what shipped plainly.

## Step 1 — Build the report

Default to the current ISO week. Accept an optional `--week`/`--year` if the user asks for a past week.

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  manager-report
```

Returns:

```json
{
  "year": 2026, "week": 29, "monday": "...", "sunday": "...",
  "summary": {"shipped": N, "goals_advanced": N, "cross_team": N},
  "highest_impact": [{"text", "goal_id", "goal_title", "impact", "off_plan"}],
  "beyond_scope":   [ ... ],   // off-plan / cross-team completed work
  "other":          [ ... ],   // linked-but-lower-impact and unlinked done work
  "wins":           [ ... ],
  "per_goal":       [{"id","title","impact","done","planned","missed","progress_pct"}],
  "markdown": "<paste-ready draft>"
}
```

The `markdown` field is a ready draft. You may present it as-is, or (better) refine the wording using the structured buckets — turn bare task text into impact statements where the daily notes give you enough to do so honestly.

## Step 2 — Refine into impact statements

For each `highest_impact` and `beyond_scope` entry, tighten the phrasing:

- Prefer outcome framing: "Shipped the AV order-creation flow across RH & Geo" beats "Did AV flow task".
- If the task text already implies who/what it unblocked, keep it. **Do not fabricate** downstream impact that isn't in the notes.
- Keep `beyond_scope` prominent — the cross-team / off-plan work is exactly what managers miss.

Present the refined draft to the user and ask:

> "Here's your Week <NN> impact draft. Want to (a) tweak anything, (b) save it to your vault, or (c) both?"

## Step 3 — Save the draft (on request)

If the user wants it saved, write to `Manager-Updates/<year>-W<NN>.md` under the vault work dir. Resolve the base path from config:

```bash
python3 ~/.claude/skills/work-buddy/helpers/wb.py --config ~/.claude/skills/work-buddy/config.json \
  iso-week
```

Build the directory as `<vault_path>/<subdir>/Manager-Updates/` and write the (possibly refined) markdown there. Create the directory if missing. Confirm the path back to the user.

## Step 4 — Delivery

**Draft-only by default.** Do not send anything automatically. After saving, tell the user how to deliver it themselves:

> "Saved → <path>. Paste it into your 1:1 doc or Slack when ready."

**Slack push is opt-in and gated.** Only if the user has explicitly enabled it (a `slack_webhook` in config AND they ask to send this week's report), confirm the exact content first:

> "Ready to post this week's impact update to Slack. Here's exactly what will be sent: <draft>. Send it? (yes/no)"

Only on an explicit "yes" do you deliver. Never post without showing the final text and getting confirmation in the same turn.

## Notes

- Empty week (nothing completed) produces a valid "no completed work logged this week" draft — surface it honestly rather than padding.
- This never mutates daily notes; it only reads them and writes a separate `Manager-Updates/` file.

