#!/usr/bin/env bash
# Install work-buddy for Codex CLI (on-demand prompt loading).
#
# What this does:
# 1. Runs install.sh first so the canonical helper at
#    ~/.claude/skills/work-buddy/helpers/wb.py exists. The bundled prompt
#    references that path, so it must be in place even if you don't use
#    Claude Code (it's just a directory; nothing else needed).
# 2. Regenerates the bundled INSTRUCTIONS.md.
# 3. Symlinks INSTRUCTIONS.md into ~/.codex/prompts/work-buddy.md so you can
#    load it on demand from Codex via that prompt directory.
#
# Codex prompt-loading varies by version. If your Codex doesn't auto-discover
# ~/.codex/prompts/, paste the contents of the bundled file into context
# manually when you want to use the skill.

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"

echo "→ Step 1: Installing canonical helper at ~/.claude/skills/work-buddy"
"$REPO/install.sh"

echo
echo "→ Step 2: Regenerating bundled INSTRUCTIONS.md"
"$REPO/build-instructions.sh"

echo
echo "→ Step 3: Linking into ~/.codex/prompts"
mkdir -p "$HOME/.codex/prompts"
ln -sfn "$REPO/INSTRUCTIONS.md" "$HOME/.codex/prompts/work-buddy.md"

cat <<EOF

✓ Installed.

Codex usage:
  - Bundled prompt:  ~/.codex/prompts/work-buddy.md  →  $REPO/INSTRUCTIONS.md
  - Helper script:   ~/.claude/skills/work-buddy/helpers/wb.py
  - Config (shared): ~/.claude/skills/work-buddy/config.json

To use from Codex:
  - If your Codex auto-loads ~/.codex/prompts/, just say "load work-buddy"
    or invoke whatever your Codex slash convention uses.
  - Otherwise, paste the contents of ~/.codex/prompts/work-buddy.md into
    your Codex session and then say e.g. "work-buddy morning".

First-time setup is the same as Claude Code:
  - "work-buddy init" → set vault path
  - "work-buddy goals" → define quarterly goals
  - "work-buddy morning" → plan first day

EOF
