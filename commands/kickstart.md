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
