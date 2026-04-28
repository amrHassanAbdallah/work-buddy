#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$SKILL_DIR"
ln -sfn "$REPO_DIR" "$SKILL_DIR/work-buddy"

echo "Installed work-buddy → $SKILL_DIR/work-buddy"
echo "Restart Claude Code, then run: /work-buddy init"
