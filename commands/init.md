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
