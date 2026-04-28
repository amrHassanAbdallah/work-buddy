#!/usr/bin/env python3
"""
wb.py — work-buddy helper CLI
Pure stdlib Python 3. All subcommands output JSON to stdout.

Usage:
  wb.py [--config PATH] <subcommand> [options]

Subcommands:
  today-path               Print the absolute path for today's daily note (file need not exist)
  date-path --date YYYY-MM-DD
                           Print the absolute path for a given date's daily note
  weekly-path [--year Y --week W]
                           Print the path for the ISO week note (defaults to current week)
  latest-prior-daily [--max-days N]
                           Print the most recent prior daily note path (null if none found)
  iso-week [--date YYYY-MM-DD]
                           Print {"year": int, "week": int} for date (default: today)
  week-range --year Y --week W
                           Print {"monday": "YYYY-MM-DD", "sunday": "YYYY-MM-DD"}
  parse-daily --path PATH  Parse a daily note, return JSON
  parse-goals --path PATH  Parse Quarterly.md, return JSON list of goals
  render-daily --date YYYY-MM-DD
                           Render daily template for date, print markdown string
  write-daily --path PATH  Read JSON from stdin, write daily note to PATH
  write-goals --path PATH  Read JSON from stdin, write goals note to PATH
  init-vault --vault-path PATH [--subdir NAME]
                           Create vault subdirs, copy quarterly template, write config.json

JSON shapes:
  Task:     {"text": str, "checked": bool, "goal_id": str|null, "raw": str}
  Goal:     {"id": str, "title": str, "impact": int, "type": str, "target": str, "notes": str}
  parse-daily returns:
    {
      "date": "YYYY-MM-DD",
      "iso_week": str,
      "planned": [Task],
      "done": [Task],
      "missed": [Task],
      "wins": [Task],
      "reflection": str,
      "raw_sections": {section_name: str}
    }
  write-daily stdin:  same shape as parse-daily output (path via --path flag)
  write-goals stdin:  {"goals": [Goal]}
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = Path.home() / ".claude" / "skills" / "work-buddy" / "config.json"


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return json.load(f)


def vault_work_dir(cfg: dict) -> Path:
    return Path(cfg["vault_path"]) / cfg.get("subdir", "work-buddy")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def today_path(cfg: dict) -> Path:
    today = datetime.date.today()
    return vault_work_dir(cfg) / "Daily" / f"{today.isoformat()}.md"


def date_path(cfg: dict, date: datetime.date) -> Path:
    return vault_work_dir(cfg) / "Daily" / f"{date.isoformat()}.md"


def weekly_path(cfg: dict, iso_year: int, iso_week: int) -> Path:
    return vault_work_dir(cfg) / "Weekly" / f"{iso_year}-W{iso_week:02d}.md"


def latest_prior_daily(cfg: dict, max_lookback_days: int = 5) -> "Path | None":
    today = datetime.date.today()
    for offset in range(1, max_lookback_days + 1):
        candidate = today - datetime.timedelta(days=offset)
        p = date_path(cfg, candidate)
        if p.exists():
            return p
    return None


def iso_week_for(date: datetime.date) -> tuple:
    cal = date.isocalendar()
    return cal[0], cal[1]  # (year, week)


def week_range(iso_year: int, iso_week: int) -> tuple:
    monday = datetime.date.fromisocalendar(iso_year, iso_week, 1)
    sunday = datetime.date.fromisocalendar(iso_year, iso_week, 7)
    return monday, sunday


# ---------------------------------------------------------------------------
# Task parsing
# ---------------------------------------------------------------------------

TASK_RE = re.compile(r"^- \[( |x)\] (.+)$")
GOAL_ID_RE = re.compile(r"→\s*([a-z0-9-]+)\s*$")


def parse_task(line: str) -> "dict | None":
    m = TASK_RE.match(line.rstrip())
    if not m:
        return None
    checked = m.group(1) == "x"
    text_raw = m.group(2)
    goal_m = GOAL_ID_RE.search(text_raw)
    goal_id = goal_m.group(1) if goal_m else None
    text = GOAL_ID_RE.sub("", text_raw).rstrip(" →").rstrip()
    return {
        "text": text,
        "checked": checked,
        "goal_id": goal_id,
        "raw": line.rstrip(),
    }


# ---------------------------------------------------------------------------
# Daily note parsing
# ---------------------------------------------------------------------------

SECTION_HEADERS = {"Planned", "Done", "Missed", "Wins", "Reflection"}

FRONTMATTER_RE = re.compile(r"^---\s*$")


def _split_sections(content: str) -> dict:
    """Split markdown into {section_name: body_text} dict.
    Frontmatter (--- ... ---) is stored as '__frontmatter__'.
    Text before any heading is '__preamble__'.
    """
    lines = content.splitlines()
    sections: dict = {}
    current = "__preamble__"
    buffer: list = []
    in_frontmatter = False
    frontmatter_done = False
    i = 0

    while i < len(lines):
        line = lines[i]
        # Handle frontmatter
        if i == 0 and FRONTMATTER_RE.match(line):
            in_frontmatter = True
            buffer = []
            i += 1
            continue
        if in_frontmatter:
            if FRONTMATTER_RE.match(line):
                in_frontmatter = False
                frontmatter_done = True
                sections["__frontmatter__"] = "\n".join(buffer)
                buffer = []
                current = "__preamble__"
            else:
                buffer.append(line)
            i += 1
            continue
        # Heading detection
        heading_m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_m:
            sections[current] = "\n".join(buffer).strip()
            buffer = []
            current = heading_m.group(2).strip()
        else:
            buffer.append(line)
        i += 1

    sections[current] = "\n".join(buffer).strip()
    return sections


def _extract_frontmatter_value(fm: str, key: str) -> str:
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return ""


def parse_daily(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    sections = _split_sections(content)

    fm = sections.get("__frontmatter__", "")
    date_str = _extract_frontmatter_value(fm, "date")
    iso_week = _extract_frontmatter_value(fm, "week")

    def extract_tasks(section_name: str) -> list:
        body = sections.get(section_name, "")
        tasks = []
        for line in body.splitlines():
            t = parse_task(line)
            if t:
                tasks.append(t)
        return tasks

    reflection_body = sections.get("Reflection", "")
    # Strip HTML comments from reflection
    reflection = re.sub(r"<!--.*?-->", "", reflection_body, flags=re.DOTALL).strip()

    return {
        "date": date_str,
        "iso_week": iso_week,
        "planned": extract_tasks("Planned"),
        "done": extract_tasks("Done"),
        "missed": extract_tasks("Missed"),
        "wins": extract_tasks("Wins"),
        "reflection": reflection,
        "raw_sections": {k: v for k, v in sections.items() if not k.startswith("__")},
    }


# ---------------------------------------------------------------------------
# Goals parsing
# ---------------------------------------------------------------------------

def parse_goals(path: Path) -> list:
    content = path.read_text(encoding="utf-8")
    goals = []
    current: "dict | None" = None

    for line in content.splitlines():
        # New goal heading: ## G1: Title or ## Title
        heading_m = re.match(r"^##\s+(.+)$", line)
        if heading_m:
            if current is not None:
                goals.append(current)
            title = heading_m.group(1).strip()
            # Strip leading G\d+:\s*
            title_clean = re.sub(r"^G\d+:\s*", "", title)
            current = {"id": "", "title": title_clean, "impact": 0, "type": "", "target": "", "notes": ""}
            continue

        if current is None:
            continue

        # Key-value lines: - key: value
        kv_m = re.match(r"^\s*-\s+(id|impact|type|target|notes):\s*(.*)$", line)
        if kv_m:
            key = kv_m.group(1)
            val = kv_m.group(2).strip()
            if key == "impact":
                try:
                    current["impact"] = int(val)
                except ValueError:
                    current["impact"] = 0
            else:
                current[key] = val

    if current is not None:
        goals.append(current)

    return goals


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def templates_dir() -> Path:
    # helpers/wb.py -> helpers/ -> work-buddy/ -> templates/
    return Path(__file__).resolve().parent.parent / "templates"


def render_daily(date: datetime.date) -> str:
    tpl_path = templates_dir() / "daily.md"
    tpl = tpl_path.read_text(encoding="utf-8")
    iso_year, iso_week = iso_week_for(date)
    date_human = date.strftime("%A, %B %d, %Y")
    result = tpl
    result = result.replace("{{date}}", date.isoformat())
    result = result.replace("{{iso_week}}", f"{iso_year}-W{iso_week:02d}")
    result = result.replace("{{date_human}}", date_human)
    return result


def render_weekly(iso_year: int, iso_week: int, ctx: dict) -> str:
    tpl_path = templates_dir() / "weekly.md"
    tpl = tpl_path.read_text(encoding="utf-8")
    monday, sunday = week_range(iso_year, iso_week)
    result = tpl
    result = result.replace("{{iso_week}}", f"{iso_year}-W{iso_week:02d}")
    result = result.replace("{{monday}}", monday.isoformat())
    result = result.replace("{{sunday}}", sunday.isoformat())
    result = result.replace("{{done_count}}", str(ctx.get("done_count", 0)))
    result = result.replace("{{missed_count}}", str(ctx.get("missed_count", 0)))
    result = result.replace("{{wins_count}}", str(ctx.get("wins_count", 0)))
    result = result.replace("{{per_goal_table}}", ctx.get("per_goal_table", ""))
    result = result.replace("{{top_wins}}", ctx.get("top_wins", ""))
    result = result.replace("{{blockers}}", ctx.get("blockers", ""))
    return result


# ---------------------------------------------------------------------------
# Daily note writing
# ---------------------------------------------------------------------------

def _tasks_to_md(tasks: list) -> str:
    """Always rebuild from fields so checked-state and goal-id changes round-trip."""
    lines = []
    for t in tasks:
        box = "x" if t.get("checked") else " "
        text = t.get("text", "").rstrip()
        goal_id = t.get("goal_id")
        suffix = f" → {goal_id}" if goal_id else ""
        lines.append(f"- [{box}] {text}{suffix}")
    return "\n".join(lines)


def write_daily(data: dict, path: Path) -> None:
    """Write a daily note from parsed data structure back to markdown."""
    path.parent.mkdir(parents=True, exist_ok=True)
    date_str = data.get("date", "")
    iso_week = data.get("iso_week", "")
    planned = data.get("planned", [])
    done = data.get("done", [])
    missed = data.get("missed", [])
    wins = data.get("wins", [])
    reflection = data.get("reflection", "")

    # Parse date for human-readable header
    try:
        d = datetime.date.fromisoformat(date_str)
        date_human = d.strftime("%A, %B %d, %Y")
    except (ValueError, TypeError):
        date_human = date_str

    lines = [
        "---",
        f"date: {date_str}",
        f"week: {iso_week}",
        "---",
        "",
        f"# {date_human}",
        "",
        "## Planned",
    ]

    if planned:
        lines.append(_tasks_to_md(planned))
    else:
        lines.append("<!-- carried-over items appear here, then new items -->")

    lines += ["", "## Done"]
    if done:
        lines.append(_tasks_to_md(done))

    lines += ["", "## Missed"]
    if missed:
        lines.append(_tasks_to_md(missed))

    lines += ["", "## Wins"]
    if wins:
        lines.append(_tasks_to_md(wins))

    lines += ["", "## Reflection"]
    if reflection:
        lines.append(reflection)
    else:
        lines.append("<!-- one line: what I learned today -->")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_goals(data: dict, path: Path) -> None:
    """Write goals from JSON structure back to Quarterly.md format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    goals = data.get("goals", [])

    # Try to detect quarter from existing file or use placeholder
    quarter = data.get("quarter", "Q? YYYY")

    lines = [
        f"# Quarterly goals — {quarter}",
        "",
        "> Each goal: short id, impact 1–5, type delivery|growth, a measurable target.",
    ]

    for i, g in enumerate(goals, 1):
        title = g.get("title", "")
        lines += [
            "",
            f"## G{i}: {title}",
            f"- id: {g.get('id', '')}",
            f"- impact: {g.get('impact', 3)}",
            f"- type: {g.get('type', 'delivery')}",
            f"- target: {g.get('target', '')}",
            f"- notes: {g.get('notes', '')}",
        ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# init-vault
# ---------------------------------------------------------------------------

def init_vault(vault_path: str, subdir: str, config_path: Path) -> None:
    vp = Path(vault_path)
    if not vp.exists():
        raise FileNotFoundError(f"Vault path does not exist: {vault_path}")

    work_dir = vp / subdir
    for d in ("Goals", "Daily", "Weekly"):
        (work_dir / d).mkdir(parents=True, exist_ok=True)

    quarterly_dest = work_dir / "Goals" / "Quarterly.md"
    if not quarterly_dest.exists():
        quarterly_src = templates_dir() / "quarterly.md"
        shutil.copy(quarterly_src, quarterly_dest)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().astimezone()
    config = {
        "vault_path": str(vp.resolve()),
        "subdir": subdir,
        "created_at": now.isoformat(),
        "tz": str(now.tzinfo) if now.tzinfo else "",
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "config_path": str(config_path), "work_dir": str(work_dir)}))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def get_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wb.py", description="work-buddy helper")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.json")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("today-path")

    dp = sub.add_parser("date-path")
    dp.add_argument("--date", required=True)

    wp = sub.add_parser("weekly-path")
    wp.add_argument("--year", type=int)
    wp.add_argument("--week", type=int)

    lpd = sub.add_parser("latest-prior-daily")
    lpd.add_argument("--max-days", type=int, default=5)

    iw = sub.add_parser("iso-week")
    iw.add_argument("--date")

    wr = sub.add_parser("week-range")
    wr.add_argument("--year", type=int, required=True)
    wr.add_argument("--week", type=int, required=True)

    pd = sub.add_parser("parse-daily")
    pd.add_argument("--path", required=True)

    pg = sub.add_parser("parse-goals")
    pg.add_argument("--path", required=True)

    rd = sub.add_parser("render-daily")
    rd.add_argument("--date")

    wd = sub.add_parser("write-daily")
    wd.add_argument("--path", required=True)

    wg = sub.add_parser("write-goals")
    wg.add_argument("--path", required=True)

    iv = sub.add_parser("init-vault")
    iv.add_argument("--vault-path", required=True)
    iv.add_argument("--subdir", default="work-buddy")

    return p


def main() -> None:
    parser = get_parser()
    args = parser.parse_args()
    config_path = Path(args.config)

    def load_cfg():
        return load_config(config_path)

    if args.cmd is None:
        parser.print_help()
        sys.exit(0)

    if args.cmd == "today-path":
        cfg = load_cfg()
        print(json.dumps({"path": str(today_path(cfg))}))

    elif args.cmd == "date-path":
        cfg = load_cfg()
        d = datetime.date.fromisoformat(args.date)
        print(json.dumps({"path": str(date_path(cfg, d))}))

    elif args.cmd == "weekly-path":
        cfg = load_cfg()
        if args.year and args.week:
            y, w = args.year, args.week
        else:
            y, w = iso_week_for(datetime.date.today())
        print(json.dumps({"path": str(weekly_path(cfg, y, w))}))

    elif args.cmd == "latest-prior-daily":
        cfg = load_cfg()
        p = latest_prior_daily(cfg, args.max_days)
        if p is None:
            print(json.dumps({"path": None}))
        else:
            print(json.dumps({"path": str(p)}))

    elif args.cmd == "iso-week":
        if args.date:
            d = datetime.date.fromisoformat(args.date)
        else:
            d = datetime.date.today()
        y, w = iso_week_for(d)
        print(json.dumps({"year": y, "week": w}))

    elif args.cmd == "week-range":
        monday, sunday = week_range(args.year, args.week)
        print(json.dumps({"monday": monday.isoformat(), "sunday": sunday.isoformat()}))

    elif args.cmd == "parse-daily":
        result = parse_daily(Path(args.path))
        print(json.dumps(result, ensure_ascii=False))

    elif args.cmd == "parse-goals":
        result = parse_goals(Path(args.path))
        print(json.dumps(result, ensure_ascii=False))

    elif args.cmd == "render-daily":
        if args.date:
            d = datetime.date.fromisoformat(args.date)
        else:
            d = datetime.date.today()
        print(render_daily(d))

    elif args.cmd == "write-daily":
        data = json.load(sys.stdin)
        write_daily(data, Path(args.path))
        print(json.dumps({"status": "ok", "path": args.path}))

    elif args.cmd == "write-goals":
        data = json.load(sys.stdin)
        write_goals(data, Path(args.path))
        print(json.dumps({"status": "ok", "path": args.path}))

    elif args.cmd == "init-vault":
        init_vault(args.vault_path, args.subdir, config_path)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
