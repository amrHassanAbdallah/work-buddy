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
