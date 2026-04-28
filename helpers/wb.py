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
    The H1 page title is stored as '__title__' (not a section).
    Only H2/H3 headings become sections.
    """
    lines = content.splitlines()
    sections: dict = {}
    current = "__preamble__"
    current_level = 0
    buffer: list = []
    in_frontmatter = False
    i = 0

    def flush():
        if current.startswith("__") or current_level >= 2:
            sections[current] = "\n".join(buffer).strip()

    while i < len(lines):
        line = lines[i]
        if i == 0 and FRONTMATTER_RE.match(line):
            in_frontmatter = True
            buffer = []
            i += 1
            continue
        if in_frontmatter:
            if FRONTMATTER_RE.match(line):
                in_frontmatter = False
                sections["__frontmatter__"] = "\n".join(buffer)
                buffer = []
                current = "__preamble__"
                current_level = 0
            else:
                buffer.append(line)
            i += 1
            continue
        heading_m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_m:
            flush()
            buffer = []
            level = len(heading_m.group(1))
            name = heading_m.group(2).strip()
            if level == 1:
                sections["__title__"] = name
                current = "__title_body__"
                current_level = 1
            else:
                current = name
                current_level = level
        else:
            buffer.append(line)
        i += 1

    flush()
    return sections


def _extract_frontmatter_value(fm: str, key: str) -> str:
    for line in fm.splitlines():
        m = re.match(rf"^{re.escape(key)}:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return ""


def _to_int_or_none(s: str):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def parse_daily(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    sections = _split_sections(content)

    fm = sections.get("__frontmatter__", "")
    date_str = _extract_frontmatter_value(fm, "date")
    iso_week = _extract_frontmatter_value(fm, "week")
    mood = _extract_frontmatter_value(fm, "mood")
    energy = _to_int_or_none(_extract_frontmatter_value(fm, "energy"))
    energy_eod = _to_int_or_none(_extract_frontmatter_value(fm, "energy_eod"))
    kickstarts_raw = _extract_frontmatter_value(fm, "kickstarts")
    kickstarts = _to_int_or_none(kickstarts_raw) or 0

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
        "mood": mood,
        "energy": energy,
        "energy_eod": energy_eod,
        "kickstarts": kickstarts,
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

    # Filter out placeholder/invalid goals so morning, weekly, kickstart never
    # treat the unfilled template as real data. Valid goal must have:
    # - id matching ^[a-z0-9-]+$
    # - non-placeholder title (anything not literally containing angle brackets)
    valid_id = re.compile(r"^[a-z0-9-]+$")
    cleaned = []
    for g in goals:
        if not valid_id.match(g.get("id", "") or ""):
            continue
        title = g.get("title", "") or ""
        if title.startswith("<") and title.endswith(">"):
            continue
        if title in ("...",):
            continue
        cleaned.append(g)
    return cleaned


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
    mood = data.get("mood", "") or ""
    energy = data.get("energy")
    energy_eod = data.get("energy_eod")
    kickstarts = data.get("kickstarts", 0) or 0
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
        f"mood: {mood}",
        f"energy: {energy if energy is not None else ''}",
        f"energy_eod: {energy_eod if energy_eod is not None else ''}",
        f"kickstarts: {kickstarts}",
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

    # Preserve any user-added sections that aren't part of the canonical set.
    # Caller passes raw_sections from parse_daily through unchanged.
    known = {"Planned", "Done", "Missed", "Wins", "Reflection"}
    extras = data.get("raw_sections") or {}
    for name, body in extras.items():
        if name in known or name.startswith("__"):
            continue
        if not body and not name:
            continue
        lines += ["", f"## {name}"]
        if body:
            lines.append(body)

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
# Kickstart counter
# ---------------------------------------------------------------------------

def bump_kickstart(cfg: dict, path: Path) -> dict:
    """Increment kickstarts on the daily note at path. Create the file from
    template if it doesn't exist. Returns {kickstarts, path, created}."""
    created = False
    if not path.exists():
        # Create from template using today's date (path implies date)
        # path filename is YYYY-MM-DD.md
        try:
            d = datetime.date.fromisoformat(path.stem)
        except ValueError:
            d = datetime.date.today()
        rendered = render_daily(d)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        created = True

    parsed = parse_daily(path)
    parsed["kickstarts"] = (parsed.get("kickstarts") or 0) + 1
    write_daily(parsed, path)
    return {"kickstarts": parsed["kickstarts"], "path": str(path), "created": created}


# ---------------------------------------------------------------------------
# Weekly aggregation + manager-discussion item synthesis
# ---------------------------------------------------------------------------

def _all_week_dates(year: int, week: int) -> list:
    monday, sunday = week_range(year, week)
    today = datetime.date.today()
    end = min(sunday, today)
    out = []
    d = monday
    while d <= end:
        out.append(d)
        d += datetime.timedelta(days=1)
    return out


def weekly_aggregate(cfg: dict, year: int, week: int, goals: list) -> dict:
    monday, sunday = week_range(year, week)
    days_data = []
    for d in _all_week_dates(year, week):
        p = date_path(cfg, d)
        if not p.exists():
            continue
        parsed = parse_daily(p)
        days_data.append(parsed)

    goal_by_id = {g["id"]: g for g in goals if g.get("id")}

    totals = {"done": 0, "missed": 0, "wins": 0, "kickstarts": 0, "days_logged": len(days_data)}
    energies = []
    moods = []
    per_goal: dict = {}

    # Track task occurrences for blocker detection: text -> set of dates seen unchecked
    blocker_track: dict = {}

    # For alignment drift
    total_tasks = 0
    unlinked_tasks = 0

    growth_wins = []

    for day in days_data:
        totals["done"] += len(day["done"])
        totals["missed"] += len(day["missed"])
        totals["wins"] += len(day["wins"])
        totals["kickstarts"] += day.get("kickstarts") or 0
        if day.get("energy") is not None:
            energies.append(day["energy"])
        if day.get("energy_eod") is not None:
            energies.append(day["energy_eod"])
        if day.get("mood"):
            moods.append(day["mood"])

        # Per-goal tally
        for section_name, section_tasks in (("planned", day["planned"]), ("done", day["done"]), ("missed", day["missed"])):
            for t in section_tasks:
                total_tasks += 1
                gid = t.get("goal_id")
                if not gid:
                    unlinked_tasks += 1
                    continue
                bucket = per_goal.setdefault(gid, {"planned": 0, "done": 0, "missed": 0})
                if section_name == "done":
                    bucket["done"] += 1
                elif section_name == "missed":
                    bucket["missed"] += 1
                else:
                    bucket["planned"] += 1

        # Blocker tracking — unchecked tasks in planned, plus tasks in missed
        unresolved = [t for t in day["planned"] if not t.get("checked")] + day["missed"]
        for t in unresolved:
            text = t.get("text", "").strip()
            if not text:
                continue
            blocker_track.setdefault(text, {"days": set(), "goal_id": t.get("goal_id")})
            blocker_track[text]["days"].add(day["date"])

        # Growth wins
        for w in day["wins"]:
            gid = w.get("goal_id")
            goal = goal_by_id.get(gid) if gid else None
            if goal and goal.get("type") == "growth":
                growth_wins.append({"text": w.get("text", ""), "goal_id": gid, "goal_title": goal.get("title", "")})

    energy_avg = round(sum(energies) / len(energies), 1) if energies else None

    # Per-goal output
    per_goal_out = []
    for gid, g in goal_by_id.items():
        bucket = per_goal.get(gid, {"planned": 0, "done": 0, "missed": 0})
        attempted = bucket["planned"] + bucket["done"] + bucket["missed"]
        pct = round(100 * bucket["done"] / attempted) if attempted else 0
        per_goal_out.append({
            "id": gid,
            "title": g.get("title", ""),
            "impact": g.get("impact", 0),
            "type": g.get("type", ""),
            "planned": bucket["planned"],
            "done": bucket["done"],
            "missed": bucket["missed"],
            "progress_pct": pct,
        })
    per_goal_out.sort(key=lambda x: -x["impact"])

    # Blockers — text appearing on 3+ distinct days
    blockers = []
    for text, info in blocker_track.items():
        if len(info["days"]) >= 3:
            blockers.append({"text": text, "days": len(info["days"]), "goal_id": info["goal_id"]})
    blockers.sort(key=lambda x: -x["days"])

    # Top wins
    top_wins = []
    seen_win_texts = set()
    for day in days_data:
        for w in day["wins"]:
            t = w.get("text", "").strip()
            if t and t not in seen_win_texts:
                seen_win_texts.add(t)
                top_wins.append(t)

    # Manager-discussion items
    manager_items = []

    for b in blockers:
        gid = b.get("goal_id")
        gctx = f" (goal: {goal_by_id[gid]['title']})" if gid and gid in goal_by_id else ""
        manager_items.append({
            "type": "blocker",
            "text": f"Stuck on \"{b['text']}\" for {b['days']} days{gctx} — could use help unblocking.",
        })

    for g in per_goal_out:
        if g["impact"] >= 4 and g["done"] == 0 and (g["planned"] + g["missed"]) >= 2:
            manager_items.append({
                "type": "stalled_goal",
                "text": f"{g['title']} (impact {g['impact']}) had 0 completions this week despite {g['planned'] + g['missed']} attempts. Want to pressure-test priority or scope.",
            })

    for gw in growth_wins[:5]:
        manager_items.append({
            "type": "growth_visibility",
            "text": f"Growth signal: \"{gw['text']}\" — connected to {gw['goal_title']}. Worth flagging for visibility.",
        })

    workload_signals = []
    if totals["kickstarts"] >= 4:
        workload_signals.append(f"needed kickstart {totals['kickstarts']}× this week")
    if energy_avg is not None and energy_avg <= 2.5:
        workload_signals.append(f"avg energy {energy_avg}/5")
    if workload_signals:
        manager_items.append({
            "type": "workload_signal",
            "text": "Energy/workload: " + ", ".join(workload_signals) + ". Worth a check-in on load and clarity.",
        })

    if total_tasks > 0:
        unlinked_pct = round(100 * unlinked_tasks / total_tasks)
        if unlinked_pct >= 30:
            manager_items.append({
                "type": "alignment_drift",
                "text": f"{unlinked_pct}% of tasks this week ({unlinked_tasks}/{total_tasks}) weren't linked to any quarterly goal. Worth revisiting priorities together.",
            })

    return {
        "year": year,
        "week": week,
        "monday": monday.isoformat(),
        "sunday": sunday.isoformat(),
        "days": [
            {
                "date": d["date"],
                "mood": d.get("mood") or "",
                "energy": d.get("energy"),
                "energy_eod": d.get("energy_eod"),
                "kickstarts": d.get("kickstarts") or 0,
                "done": len(d["done"]),
                "missed": len(d["missed"]),
                "wins": len(d["wins"]),
            }
            for d in days_data
        ],
        "totals": totals,
        "energy_avg": energy_avg,
        "moods": moods,
        "per_goal": per_goal_out,
        "top_wins": top_wins,
        "blockers": blockers,
        "manager_items": manager_items,
        "unlinked_pct": round(100 * unlinked_tasks / total_tasks) if total_tasks else 0,
    }


# ---------------------------------------------------------------------------
# Signal detection for proactive kickstart suggestion
# ---------------------------------------------------------------------------

def kickstart_signals(cfg: dict) -> dict:
    """Look at recent state and decide whether to suggest /work-buddy kickstart.

    Returns {"suggest": bool, "reasons": [str]}.
    Reasons trigger when:
    - Most recent prior daily had energy <= 2 (morning OR eod)
    - Most recent prior daily had >=3 planned tasks but 0 done
    - Same task carried (in planned unchecked or missed) across last 3 days
    - Today already has >=3 kickstarts logged (pattern of struggling — recommend rest, but flag)
    """
    reasons = []

    # Today
    tp = today_path(cfg)
    if tp.exists():
        td = parse_daily(tp)
        if (td.get("kickstarts") or 0) >= 3:
            reasons.append(f"Already used kickstart {td['kickstarts']}× today — consider rest, not another sprint.")

    # Yesterday signals
    prior = latest_prior_daily(cfg, max_lookback_days=3)
    if prior:
        pd = parse_daily(prior)
        e = pd.get("energy")
        e_eod = pd.get("energy_eod")
        if e is not None and e <= 2:
            reasons.append(f"Yesterday's morning energy was {e}/5.")
        if e_eod is not None and e_eod <= 2:
            reasons.append(f"Yesterday ended at energy {e_eod}/5.")
        # Only treat "0 done" as a signal if we have evidence eod actually ran.
        # Otherwise a user who runs morning but skips eod gets this flag every day.
        eod_ran = (
            e_eod is not None
            or bool((pd.get("reflection") or "").strip())
            or len(pd["missed"]) > 0
            or len(pd["done"]) > 0
        )
        if eod_ran and len(pd["planned"]) + len(pd["missed"]) >= 3 and len(pd["done"]) == 0:
            reasons.append("Yesterday: 0 tasks completed.")

    # Carry-over chain detection — look back up to 5 days
    today = datetime.date.today()
    text_days: dict = {}
    for offset in range(1, 6):
        d = today - datetime.timedelta(days=offset)
        p = date_path(cfg, d)
        if not p.exists():
            continue
        pd = parse_daily(p)
        for t in pd["missed"] + [t for t in pd["planned"] if not t.get("checked")]:
            text = t.get("text", "").strip()
            if text:
                text_days.setdefault(text, set()).add(d.isoformat())
    for text, days in text_days.items():
        if len(days) >= 3:
            reasons.append(f"\"{text[:60]}\" has been carried/missed {len(days)} days running.")
            break  # one example is enough

    return {"suggest": len(reasons) > 0, "reasons": reasons}


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
    wd.add_argument("--from-file", help="Read JSON payload from file instead of stdin")

    wg = sub.add_parser("write-goals")
    wg.add_argument("--path", required=True)
    wg.add_argument("--from-file", help="Read JSON payload from file instead of stdin")

    iv = sub.add_parser("init-vault")
    iv.add_argument("--vault-path", required=True)
    iv.add_argument("--subdir", default="work-buddy")

    bk = sub.add_parser("bump-kickstart")
    bk.add_argument("--path", help="Path to today's daily note (defaults to today-path)")

    wa = sub.add_parser("weekly-aggregate")
    wa.add_argument("--year", type=int)
    wa.add_argument("--week", type=int)

    sub.add_parser("kickstart-signals")

    return p


def _load_json_input(args) -> dict:
    """Load JSON payload either from --from-file or from stdin.
    Prefer --from-file from prompts to avoid shell-escape footguns when
    payloads contain quotes/apostrophes/special chars."""
    src = getattr(args, "from_file", None)
    if src:
        with open(src, encoding="utf-8") as f:
            return json.load(f)
    return json.load(sys.stdin)


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
        data = _load_json_input(args)
        write_daily(data, Path(args.path))
        print(json.dumps({"status": "ok", "path": args.path}))

    elif args.cmd == "write-goals":
        data = _load_json_input(args)
        write_goals(data, Path(args.path))
        print(json.dumps({"status": "ok", "path": args.path}))

    elif args.cmd == "init-vault":
        init_vault(args.vault_path, args.subdir, config_path)

    elif args.cmd == "bump-kickstart":
        cfg = load_cfg()
        path = Path(args.path) if args.path else today_path(cfg)
        result = bump_kickstart(cfg, path)
        print(json.dumps(result))

    elif args.cmd == "weekly-aggregate":
        cfg = load_cfg()
        if args.year and args.week:
            y, w = args.year, args.week
        else:
            y, w = iso_week_for(datetime.date.today())
        # Goals path
        goals_path = vault_work_dir(cfg) / "Goals" / "Quarterly.md"
        goals = parse_goals(goals_path) if goals_path.exists() else []
        result = weekly_aggregate(cfg, y, w, goals)
        print(json.dumps(result, ensure_ascii=False))

    elif args.cmd == "kickstart-signals":
        cfg = load_cfg()
        print(json.dumps(kickstart_signals(cfg), ensure_ascii=False))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
