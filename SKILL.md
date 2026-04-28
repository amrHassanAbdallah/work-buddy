---
name: work-buddy
description: Work planning, daily notes, and Obsidian work tracking. Triggers on requests to plan your day, morning standup prep, end-of-day review, weekly reflection, goal tracking, or anything involving daily/weekly notes in Obsidian. Use this skill for /work-buddy commands.
---

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
> 
> Run with no argument to auto-detect: morning if today has no plan, now if it does."

## Helper script location

All `wb.py` invocations use:
```
~/.claude/skills/work-buddy/helpers/wb.py
```
with `--config ~/.claude/skills/work-buddy/config.json`.
