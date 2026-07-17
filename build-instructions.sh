#!/usr/bin/env bash
# Bundles SKILL.md + all command prompts into INSTRUCTIONS.md so Codex (or any
# non-Claude-Code client) can use the skill by pasting one file into context.
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
OUT="$REPO/INSTRUCTIONS.md"

{
  echo "# work-buddy — bundled instructions for Codex / non-Claude-Code clients"
  echo
  echo "This file is **generated** by build-instructions.sh. Do not edit by hand."
  echo "It concatenates SKILL.md and every commands/*.md so a Codex user can paste"
  echo "this single file into context and the model has the full skill."
  echo
  echo "Source files: SKILL.md + commands/{init,goals,morning,now,eod,weekly,kickstart}.md"
  echo
  echo "---"
  echo
  echo "## Router (from SKILL.md)"
  echo
  # Strip frontmatter from SKILL.md
  awk 'BEGIN{fm=0} /^---$/{fm++; next} fm<2{next} {print}' "$REPO/SKILL.md"
  echo
  for cmd in init goals morning now eod kickstart add catchup weekly report; do
    echo
    echo "---"
    echo
    echo "## Subcommand: $cmd (from commands/$cmd.md)"
    echo
    cat "$REPO/commands/$cmd.md"
    echo
  done
} > "$OUT"

echo "Wrote $OUT ($(wc -l < "$OUT") lines)"
