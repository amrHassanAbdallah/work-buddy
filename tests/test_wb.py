"""Tests for helpers/wb.py — stdlib unittest, no external deps.

Run from repo root:
    python3 -m unittest discover -s tests -v
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "helpers"))
import wb  # noqa: E402

WB_CLI = str(REPO / "helpers" / "wb.py")


def make_vault():
    vault = Path(tempfile.mkdtemp())
    work = vault / "work-buddy"
    (work / "Daily").mkdir(parents=True)
    (work / "Goals").mkdir(parents=True)
    (work / "Weekly").mkdir(parents=True)
    cfg_path = Path(tempfile.mkdtemp()) / "config.json"
    cfg_path.write_text(json.dumps({"vault_path": str(vault), "subdir": "work-buddy"}))
    cfg = json.loads(cfg_path.read_text())
    return cfg, cfg_path, work


def write_day(work, date, *, mood="", energy=None, energy_eod=None, kickstarts=0,
              planned=(), done=(), missed=(), wins=(), reflection="", extra_sections=None):
    iso = date.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    lines = [
        "---",
        f"date: {date.isoformat()}",
        f"week: {week}",
        f"mood: {mood}",
        f"energy: {energy if energy is not None else ''}",
        f"energy_eod: {energy_eod if energy_eod is not None else ''}",
        f"kickstarts: {kickstarts}",
        "---",
        "",
        f"# {date.strftime('%A, %B %d, %Y')}",
        "",
        "## Planned",
        *planned,
        "",
        "## Done",
        *done,
        "",
        "## Missed",
        *missed,
        "",
        "## Wins",
        *wins,
        "",
        "## Reflection",
        reflection,
    ]
    if extra_sections:
        for name, body in extra_sections.items():
            lines += ["", f"## {name}", body]
    p = work / "Daily" / f"{date.isoformat()}.md"
    p.write_text("\n".join(lines) + "\n")
    return p


# -----------------------------------------------------------------------------
# Pure-function unit tests
# -----------------------------------------------------------------------------

class TestParseTask(unittest.TestCase):
    def test_unchecked_with_goal(self):
        t = wb.parse_task("- [ ] Investigate cache → perf-q2")
        self.assertEqual(t["text"], "Investigate cache")
        self.assertFalse(t["checked"])
        self.assertEqual(t["goal_id"], "perf-q2")
        self.assertFalse(t["off_plan"])

    def test_checked_no_goal(self):
        t = wb.parse_task("- [x] Random chore")
        self.assertEqual(t["text"], "Random chore")
        self.assertTrue(t["checked"])
        self.assertIsNone(t["goal_id"])

    def test_non_task_returns_none(self):
        self.assertIsNone(wb.parse_task("just a line"))
        self.assertIsNone(wb.parse_task("- not a checkbox"))

    def test_off_plan_marker_before_goal(self):
        t = wb.parse_task("- [x] Random PR review [off-plan] → perf-q2")
        self.assertEqual(t["text"], "Random PR review")
        self.assertTrue(t["off_plan"])
        self.assertEqual(t["goal_id"], "perf-q2")

    def test_off_plan_marker_after_goal(self):
        # The off-plan marker is stripped before goal matching, so the goal link
        # survives regardless of marker order and the goal text is not left behind.
        t = wb.parse_task("- [x] Helped Sara debug → perf-q2 [off-plan]")
        self.assertTrue(t["off_plan"])
        self.assertEqual(t["goal_id"], "perf-q2")
        self.assertEqual(t["text"], "Helped Sara debug")

    def test_off_plan_no_goal(self):
        t = wb.parse_task("- [x] Unplanned chore [off-plan]")
        self.assertTrue(t["off_plan"])
        self.assertIsNone(t["goal_id"])
        self.assertEqual(t["text"], "Unplanned chore")

    def test_uppercase_checkbox_is_checked(self):
        t = wb.parse_task("- [X] Done via Obsidian → perf-q2")
        self.assertIsNotNone(t)
        self.assertTrue(t["checked"])
        self.assertEqual(t["text"], "Done via Obsidian")
        self.assertEqual(t["goal_id"], "perf-q2")

    def test_impact_note_and_with_team(self):
        t = wb.parse_task(
            "- [x] Shipped API [with: devops] → av-flow — impact: unblocked Marketplace")
        self.assertEqual(t["text"], "Shipped API")
        self.assertEqual(t["goal_id"], "av-flow")
        self.assertEqual(t["with_teams"], ["devops"])
        self.assertEqual(t["impact"], "unblocked Marketplace")
        self.assertFalse(t["off_plan"])

    def test_multiple_teams_and_off_plan_with_impact(self):
        t = wb.parse_task(
            "- [x] Ran launch [with: geo-data, geo-way] [off-plan] — impact: end to end")
        self.assertEqual(t["with_teams"], ["geo-data", "geo-way"])
        self.assertTrue(t["off_plan"])
        self.assertEqual(t["impact"], "end to end")
        self.assertEqual(t["text"], "Ran launch")

    def test_impact_note_with_apostrophe_survives(self):
        t = wb.parse_task("- [x] Fix → perf-q2 — impact: unblocked Sara's PR")
        self.assertEqual(t["impact"], "unblocked Sara's PR")
        self.assertEqual(t["goal_id"], "perf-q2")

    def test_new_fields_round_trip(self):
        line = "- [x] Shipped API [with: devops] → av-flow — impact: unblocked Marketplace"
        t1 = wb.parse_task(line)
        t2 = wb.parse_task(wb._tasks_to_md([t1]))
        for f in ("text", "checked", "goal_id", "off_plan", "with_teams", "impact"):
            self.assertEqual(t1[f], t2[f], f"field {f} did not round-trip")

    def test_bare_task_has_empty_new_fields(self):
        t = wb.parse_task("- [ ] Plain")
        self.assertEqual(t["with_teams"], [])
        self.assertIsNone(t["impact"])


class TestParseGoals(unittest.TestCase):
    def test_template_returns_empty(self):
        # Fresh template has placeholder ids like <slug>; should be filtered
        result = wb.parse_goals(REPO / "templates" / "quarterly.md")
        self.assertEqual(result, [])

    def test_real_goals_pass_filter(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("""# Quarterly goals — Q2

## G1: Real goal
- id: perf-q2
- impact: 5
- type: delivery
- target: p95 < 200ms

## G2: Bogus
- id: <slug>
- impact: 3
- type: delivery
""")
            p = f.name
        result = wb.parse_goals(Path(p))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "perf-q2")
        self.assertEqual(result[0]["impact"], 5)


class TestRoundTrip(unittest.TestCase):
    def test_preserves_custom_sections(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("""---
date: 2026-04-28
week: 2026-W18
mood: focused
energy: 4
energy_eod:
kickstarts: 0
---

# Tuesday, April 28, 2026

## Planned
- [ ] Task → perf-q2

## Done

## Missed

## Wins

## Reflection
Learned X.

## Notes
Some Obsidian note content.

## Links
- [[other note]]
""")
            p = Path(f.name)
        parsed = wb.parse_daily(p)
        # H1 must NOT appear in raw_sections
        self.assertNotIn("Tuesday, April 28, 2026", parsed["raw_sections"])
        self.assertIn("Notes", parsed["raw_sections"])
        # Round-trip
        out = Path(p.parent / "out.md")
        wb.write_daily(parsed, out)
        content = out.read_text()
        self.assertIn("## Notes", content)
        self.assertIn("Some Obsidian note content", content)
        self.assertIn("## Links", content)

    def test_preserves_frontmatter(self):
        cfg, _, work = make_vault()
        d = datetime.date(2026, 4, 28)
        write_day(work, d, mood="tired", energy=2, energy_eod=3, kickstarts=2,
                  planned=["- [ ] A"], done=[], missed=[], wins=[], reflection="ok")
        parsed = wb.parse_daily(work / "Daily" / "2026-04-28.md")
        self.assertEqual(parsed["mood"], "tired")
        self.assertEqual(parsed["energy"], 2)
        self.assertEqual(parsed["energy_eod"], 3)
        self.assertEqual(parsed["kickstarts"], 2)
        # Round-trip
        out = work / "Daily" / "out.md"
        wb.write_daily(parsed, out)
        again = wb.parse_daily(out)
        self.assertEqual(again["mood"], "tired")
        self.assertEqual(again["energy"], 2)
        self.assertEqual(again["energy_eod"], 3)
        self.assertEqual(again["kickstarts"], 2)

    def test_state_change_round_trip(self):
        """Moving a task from planned to done must flip checkbox state."""
        cfg, _, work = make_vault()
        d = datetime.date(2026, 4, 28)
        write_day(work, d, planned=["- [ ] Foo → perf-q2"])
        parsed = wb.parse_daily(work / "Daily" / "2026-04-28.md")
        # Move task to done
        task = parsed["planned"][0]
        task["checked"] = True
        parsed["done"].append(task)
        parsed["planned"] = []
        wb.write_daily(parsed, work / "Daily" / "2026-04-28.md")
        again = wb.parse_daily(work / "Daily" / "2026-04-28.md")
        self.assertEqual(len(again["done"]), 1)
        self.assertTrue(again["done"][0]["checked"])
        self.assertEqual(again["done"][0]["goal_id"], "perf-q2")


# -----------------------------------------------------------------------------
# Signal detection
# -----------------------------------------------------------------------------

class TestKickstartSignals(unittest.TestCase):
    def test_no_eod_evidence_does_not_fire_zero_done(self):
        cfg, _, work = make_vault()
        y = datetime.date.today() - datetime.timedelta(days=1)
        write_day(work, y, planned=["- [ ] A", "- [ ] B", "- [ ] C"])  # no eod
        sig = wb.kickstart_signals(cfg)
        self.assertFalse(sig["suggest"])

    def test_low_energy_fires(self):
        cfg, _, work = make_vault()
        y = datetime.date.today() - datetime.timedelta(days=1)
        write_day(work, y, energy=2, energy_eod=2, reflection="rough",
                  planned=["- [ ] A", "- [ ] B", "- [ ] C"])
        sig = wb.kickstart_signals(cfg)
        self.assertTrue(sig["suggest"])
        self.assertTrue(any("morning energy" in r for r in sig["reasons"]))
        self.assertTrue(any("ended at energy" in r for r in sig["reasons"]))
        self.assertTrue(any("0 tasks completed" in r for r in sig["reasons"]))

    def test_carry_over_chain_3_days(self):
        cfg, _, work = make_vault()
        today = datetime.date.today()
        # Write 3 prior days all with the same unfinished task
        for offset in range(1, 4):
            d = today - datetime.timedelta(days=offset)
            write_day(work, d, planned=["- [ ] Stuck task → perf-q2"], reflection="x", energy_eod=3)
        sig = wb.kickstart_signals(cfg)
        self.assertTrue(sig["suggest"])
        self.assertTrue(any("Stuck task" in r for r in sig["reasons"]))


# -----------------------------------------------------------------------------
# Kickstart counter
# -----------------------------------------------------------------------------

class TestBumpKickstart(unittest.TestCase):
    def test_creates_and_increments(self):
        cfg, _, work = make_vault()
        target = work / "Daily" / "2026-04-29.md"
        self.assertFalse(target.exists())
        r1 = wb.bump_kickstart(cfg, target)
        self.assertTrue(target.exists())
        self.assertTrue(r1["created"])
        self.assertEqual(r1["kickstarts"], 1)
        r2 = wb.bump_kickstart(cfg, target)
        self.assertFalse(r2["created"])
        self.assertEqual(r2["kickstarts"], 2)


# -----------------------------------------------------------------------------
# Weekly aggregator + manager-item generators
# -----------------------------------------------------------------------------

class TestWeeklyAggregate(unittest.TestCase):
    def _make_quarter_goals(self, work):
        (work / "Goals" / "Quarterly.md").write_text("""# Q

## G1: API caching
- id: perf-q2
- impact: 5
- type: delivery
- target: p95 < 200ms

## G2: Distsys
- id: growth-distsys
- impact: 4
- type: growth
- target: lead 1 design

## G3: Hiring
- id: team-hiring
- impact: 4
- type: delivery
- target: 2 hires
""")

    def test_blocker_3_days(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        # Use a fully-past week so _all_week_dates includes every day
        # (it caps at "today", so Mon-Wed of the *current* week may exclude future days).
        # Week 17 of 2026 = Apr 20 (Mon) – Apr 26 (Sun) — all before today (Apr 28+).
        mon = datetime.date(2026, 4, 20)
        for offset in range(3):
            write_day(work, mon + datetime.timedelta(days=offset),
                      planned=["- [ ] Stuck → perf-q2"], reflection="x", energy_eod=3)
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 17, goals)
        self.assertEqual(len(agg["blockers"]), 1)
        self.assertEqual(agg["blockers"][0]["days"], 3)
        self.assertTrue(any(m["type"] == "blocker" for m in agg["manager_items"]))

    def test_stalled_goal(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 27)
        # 2 attempts at perf-q2 with 0 dones
        write_day(work, mon, planned=["- [ ] T1 → perf-q2"], missed=["- [ ] T1 → perf-q2"], reflection="x")
        write_day(work, mon + datetime.timedelta(days=1),
                  planned=["- [ ] T2 → perf-q2"], missed=["- [ ] T2 → perf-q2"], reflection="x")
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 18, goals)
        stalled = [m for m in agg["manager_items"] if m["type"] == "stalled_goal"]
        self.assertTrue(stalled)
        self.assertIn("API caching", stalled[0]["text"])

    def test_workload_signal_low_energy(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 27)
        for offset in range(3):
            write_day(work, mon + datetime.timedelta(days=offset),
                      energy=2, energy_eod=2, reflection="x")
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 18, goals)
        self.assertEqual(agg["energy_avg"], 2.0)
        wl = [m for m in agg["manager_items"] if m["type"] == "workload_signal"]
        self.assertTrue(wl)

    def test_workload_signal_kickstart_count(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 27)
        # 4 kickstarts total across the week
        write_day(work, mon, kickstarts=2, energy=4, reflection="x")
        write_day(work, mon + datetime.timedelta(days=1), kickstarts=2, energy=4, reflection="x")
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 18, goals)
        self.assertEqual(agg["totals"]["kickstarts"], 4)
        wl = [m for m in agg["manager_items"] if m["type"] == "workload_signal"]
        self.assertTrue(wl)
        self.assertIn("kickstart 4", wl[0]["text"])

    def test_alignment_drift(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 27)
        # 4 unlinked, 1 linked → 80% unlinked, way past 30% threshold
        write_day(work, mon,
                  planned=["- [ ] U1", "- [ ] U2", "- [ ] U3", "- [ ] U4", "- [ ] L → perf-q2"],
                  reflection="x")
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 18, goals)
        ad = [m for m in agg["manager_items"] if m["type"] == "alignment_drift"]
        self.assertTrue(ad)

    def test_growth_visibility(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 27)
        write_day(work, mon, wins=["- [x] Paired with Sara → growth-distsys"], reflection="x")
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 18, goals)
        gv = [m for m in agg["manager_items"] if m["type"] == "growth_visibility"]
        self.assertTrue(gv)
        self.assertIn("Sara", gv[0]["text"])

    def test_off_plan_ratio_signal(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 20)
        # 4 done items, 3 of them off-plan = 75%, well above 40% threshold
        write_day(work, mon, reflection="x",
                  done=[
                      "- [x] Planned A → perf-q2",
                      "- [x] Reactive thing 1 [off-plan]",
                      "- [x] Reactive thing 2 [off-plan]",
                      "- [x] Reactive thing 3 [off-plan]",
                  ])
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 17, goals)
        self.assertEqual(agg["off_plan_count"], 3)
        self.assertEqual(agg["off_plan_pct"], 75)
        op = [m for m in agg["manager_items"] if m["type"] == "off_plan_ratio"]
        self.assertTrue(op)

    def test_off_plan_below_threshold(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 20)
        # 4 done, 1 off-plan = 25% — below 40% threshold
        write_day(work, mon, reflection="x",
                  done=[
                      "- [x] A → perf-q2",
                      "- [x] B → perf-q2",
                      "- [x] C → perf-q2",
                      "- [x] D [off-plan]",
                  ])
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 17, goals)
        op = [m for m in agg["manager_items"] if m["type"] == "off_plan_ratio"]
        self.assertEqual(op, [])

    def test_quiet_week_no_manager_items(self):
        cfg, _, work = make_vault()
        self._make_quarter_goals(work)
        mon = datetime.date(2026, 4, 27)
        # Healthy week: high energy, all linked, completes
        write_day(work, mon, energy=4, energy_eod=4,
                  planned=["- [ ] T → perf-q2"], done=["- [x] T → perf-q2"], reflection="x")
        goals = wb.parse_goals(work / "Goals" / "Quarterly.md")
        agg = wb.weekly_aggregate(cfg, 2026, 18, goals)
        self.assertEqual(agg["manager_items"], [])


# -----------------------------------------------------------------------------
# Manager report — outward-facing weekly impact digest
# -----------------------------------------------------------------------------

class TestManagerReport(unittest.TestCase):
    def _goals(self, work):
        (work / "Goals" / "Quarterly.md").write_text("""# Q

## G1: AV flow
- id: av-flow
- impact: 5
- type: delivery

## G2: Bookmark manager
- id: bookmark-mgr
- impact: 4
- type: delivery

## G3: Docs cleanup
- id: docs
- impact: 2
- type: delivery
""")
        return wb.parse_goals(work / "Goals" / "Quarterly.md")

    def test_buckets_by_impact_and_off_plan(self):
        cfg, _, work = make_vault()
        goals = self._goals(work)
        # Fully-past week 17 (Apr 20-26) so all days are counted.
        mon = datetime.date(2026, 4, 20)
        write_day(work, mon, energy_eod=4, reflection="x",
                  done=["- [x] Finalized AV flow → av-flow"])
        write_day(work, mon + datetime.timedelta(days=1), energy_eod=4, reflection="x",
                  done=["- [x] Shipped bookmark support → bookmark-mgr",
                        "- [x] Owned DH ETA launch [off-plan]"])
        write_day(work, mon + datetime.timedelta(days=2), energy_eod=4, reflection="x",
                  done=["- [x] Fixed README typo → docs",
                        "- [x] Unlinked chore"])
        rep = wb.manager_report(cfg, 2026, 17, goals)

        self.assertEqual(rep["summary"]["shipped"], 5)
        self.assertEqual(rep["summary"]["goals_advanced"], 3)
        self.assertEqual(rep["summary"]["cross_team"], 1)

        highest = [e["text"] for e in rep["highest_impact"]]
        self.assertEqual(highest, ["Finalized AV flow", "Shipped bookmark support"])
        # sorted by impact desc: av-flow (5) before bookmark-mgr (4)
        self.assertEqual(rep["highest_impact"][0]["impact"], 5)

        beyond = [e["text"] for e in rep["beyond_scope"]]
        self.assertEqual(beyond, ["Owned DH ETA launch"])

        other = [e["text"] for e in rep["other"]]
        self.assertIn("Fixed README typo", other)   # linked but impact 2
        self.assertIn("Unlinked chore", other)       # no goal link

    def test_markdown_has_sections(self):
        cfg, _, work = make_vault()
        goals = self._goals(work)
        mon = datetime.date(2026, 4, 20)
        write_day(work, mon, energy_eod=4, reflection="x",
                  done=["- [x] Finalized AV flow → av-flow",
                        "- [x] Owned DH ETA launch [off-plan]"])
        md = wb.manager_report(cfg, 2026, 17, goals)["markdown"]
        self.assertIn("# Weekly impact — 2026-W17", md)
        self.assertIn("## Highest impact", md)
        self.assertIn("## Beyond my scope", md)
        self.assertIn("(impact 5)", md)
        self.assertIn("Review and edit before sending", md)

    def test_empty_week_is_valid(self):
        cfg, _, work = make_vault()
        goals = self._goals(work)
        rep = wb.manager_report(cfg, 2026, 17, goals)
        self.assertEqual(rep["summary"]["shipped"], 0)
        self.assertIn("No completed work logged", rep["markdown"])
        self.assertEqual(rep["highest_impact"], [])

    def test_impact_note_leads_bullet(self):
        cfg, _, work = make_vault()
        goals = self._goals(work)
        mon = datetime.date(2026, 4, 20)
        write_day(work, mon, energy_eod=4, reflection="x",
                  done=["- [x] Finalized AV flow → av-flow — impact: unblocked Marketplace"])
        rep = wb.manager_report(cfg, 2026, 17, goals)
        self.assertEqual(rep["highest_impact"][0]["impact_note"], "unblocked Marketplace")
        # The outcome note must appear in the rendered bullet.
        self.assertIn("Finalized AV flow — unblocked Marketplace", rep["markdown"])

    def test_cross_team_tag_surfaces(self):
        cfg, _, work = make_vault()
        goals = self._goals(work)
        mon = datetime.date(2026, 4, 20)
        write_day(work, mon, energy_eod=4, reflection="x",
                  done=["- [x] Launch [with: geo-data] [off-plan] — impact: shipped it"])
        rep = wb.manager_report(cfg, 2026, 17, goals)
        self.assertEqual(rep["beyond_scope"][0]["with_teams"], ["geo-data"])
        self.assertIn("(with geo-data)", rep["markdown"])

    def test_cli_manager_report(self):
        cfg, cfg_path, work = make_vault()
        self._goals(work)
        mon = datetime.date(2026, 4, 20)
        write_day(work, mon, energy_eod=4, reflection="x",
                  done=["- [x] Finalized AV flow → av-flow"])
        r = subprocess.run([sys.executable, WB_CLI, "--config", str(cfg_path),
                            "manager-report", "--year", "2026", "--week", "17"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["summary"]["shipped"], 1)
        self.assertIn("Highest impact", data["markdown"])


# -----------------------------------------------------------------------------
# CLI integration — including --from-file
# -----------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    def test_iso_week(self):
        r = subprocess.run([sys.executable, WB_CLI, "iso-week", "--date", "2026-04-28"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout), {"year": 2026, "week": 18})

    def test_render_daily(self):
        r = subprocess.run([sys.executable, WB_CLI, "render-daily", "--date", "2026-04-28"],
                           capture_output=True, text=True)
        self.assertIn("date: 2026-04-28", r.stdout)
        self.assertIn("# Tuesday, April 28, 2026", r.stdout)

    def test_write_daily_via_stdin(self):
        cfg, cfg_path, work = make_vault()
        path = work / "Daily" / "2026-04-28.md"
        payload = {
            "date": "2026-04-28", "iso_week": "2026-W18",
            "mood": "ok", "energy": 3, "energy_eod": None, "kickstarts": 0,
            "planned": [{"text": "X", "checked": False, "goal_id": None, "raw": ""}],
            "done": [], "missed": [], "wins": [], "reflection": "",
        }
        r = subprocess.run([sys.executable, WB_CLI, "--config", str(cfg_path),
                            "write-daily", "--path", str(path)],
                           input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(path.exists())

    def test_write_daily_via_from_file(self):
        cfg, cfg_path, work = make_vault()
        path = work / "Daily" / "2026-04-28.md"
        payload = {
            "date": "2026-04-28", "iso_week": "2026-W18",
            "mood": "tired", "energy": 2, "energy_eod": None, "kickstarts": 1,
            # Embedded apostrophes and quotes — what would break echo '<json>' | wb.py
            "planned": [{"text": "Don't break — Sara's PR \"review\"", "checked": False,
                         "goal_id": "perf-q2", "raw": ""}],
            "done": [], "missed": [], "wins": [], "reflection": "",
        }
        payload_file = work / "payload.json"
        payload_file.write_text(json.dumps(payload))
        r = subprocess.run([sys.executable, WB_CLI, "--config", str(cfg_path),
                            "write-daily", "--path", str(path),
                            "--from-file", str(payload_file)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        content = path.read_text()
        self.assertIn("Don't break", content)
        self.assertIn("Sara's PR", content)
        self.assertIn("\"review\"", content)


class TestAppendTask(unittest.TestCase):
    def test_creates_and_appends(self):
        cfg, _, work = make_vault()
        target = work / "Daily" / "2026-04-29.md"
        self.assertFalse(target.exists())
        r = wb.append_task(cfg, target, "Quick item", "perf-q2", off_plan=False)
        self.assertTrue(target.exists())
        self.assertTrue(r["created"])
        parsed = wb.parse_daily(target)
        self.assertEqual(len(parsed["planned"]), 1)
        self.assertEqual(parsed["planned"][0]["text"], "Quick item")
        self.assertEqual(parsed["planned"][0]["goal_id"], "perf-q2")

    def test_preserves_existing(self):
        cfg, _, work = make_vault()
        d = datetime.date(2026, 4, 28)
        write_day(work, d, mood="tired", energy=2, kickstarts=1,
                  planned=["- [ ] Existing → perf-q2"])
        target = work / "Daily" / f"{d.isoformat()}.md"
        wb.append_task(cfg, target, "New", "growth-distsys")
        parsed = wb.parse_daily(target)
        self.assertEqual(len(parsed["planned"]), 2)
        self.assertEqual(parsed["mood"], "tired")
        self.assertEqual(parsed["energy"], 2)
        self.assertEqual(parsed["kickstarts"], 1)

    def test_off_plan_flag(self):
        cfg, _, work = make_vault()
        target = work / "Daily" / "2026-04-29.md"
        wb.append_task(cfg, target, "Random", None, off_plan=True)
        parsed = wb.parse_daily(target)
        self.assertTrue(parsed["planned"][0]["off_plan"])

    def test_with_teams(self):
        cfg, _, work = make_vault()
        target = work / "Daily" / "2026-04-29.md"
        wb.append_task(cfg, target, "Cross-team task", "av-flow",
                       with_teams=["devops", "sre"])
        parsed = wb.parse_daily(target)
        self.assertEqual(parsed["planned"][0]["with_teams"], ["devops", "sre"])
        self.assertEqual(parsed["planned"][0]["goal_id"], "av-flow")


class TestWorkdays(unittest.TestCase):
    def test_default_mon_fri(self):
        self.assertEqual(wb.workdays({}), [1, 2, 3, 4, 5])

    def test_custom(self):
        self.assertEqual(wb.workdays({"workdays": [1, 2, 3, 4, 5, 6]}), [1, 2, 3, 4, 5, 6])

    def test_invalid_falls_back(self):
        self.assertEqual(wb.workdays({"workdays": "not-a-list"}), [1, 2, 3, 4, 5])
        self.assertEqual(wb.workdays({"workdays": [99, "x"]}), [1, 2, 3, 4, 5])


class TestUnresolvedWorkdays(unittest.TestCase):
    def test_skips_finished_days(self):
        cfg, _, work = make_vault()
        # Yesterday (assuming weekday) finished cleanly: don't flag.
        today = datetime.date.today()
        # Walk back to the most recent workday.
        d = today - datetime.timedelta(days=1)
        while d.isoweekday() > 5:
            d -= datetime.timedelta(days=1)
        write_day(work, d, energy_eod=4, reflection="all done",
                  done=["- [x] A → perf-q2"])
        result = wb.unresolved_workdays(cfg, max_days=7)
        self.assertNotIn(d.isoformat(), [r["date"] for r in result])

    def test_flags_unresolved(self):
        cfg, _, work = make_vault()
        today = datetime.date.today()
        d = today - datetime.timedelta(days=1)
        while d.isoweekday() > 5:
            d -= datetime.timedelta(days=1)
        write_day(work, d, planned=["- [ ] Stuck → perf-q2"])  # no eod
        result = wb.unresolved_workdays(cfg, max_days=7)
        dates = [r["date"] for r in result]
        self.assertIn(d.isoformat(), dates)
        entry = [r for r in result if r["date"] == d.isoformat()][0]
        self.assertTrue(entry["has_note"])
        self.assertEqual(entry["planned_unresolved"], 1)
        self.assertFalse(entry["eod_done"])

    def test_skips_non_workdays(self):
        # Configure user as Mon-only, then ensure yesterday (likely not Mon) isn't flagged
        # even if missing.
        vault = Path(tempfile.mkdtemp())
        work = vault / "work-buddy"
        (work / "Daily").mkdir(parents=True)
        cfg = {"vault_path": str(vault), "subdir": "work-buddy", "workdays": [1]}  # Mondays only
        result = wb.unresolved_workdays(cfg, max_days=7)
        # All entries (if any) should be Mondays
        for r in result:
            d = datetime.date.fromisoformat(r["date"])
            self.assertEqual(d.isoweekday(), 1)

    def test_empty_vault_flags_nothing(self):
        # No notes at all → adoption floor is None → nothing flagged (a brand-new
        # user shouldn't be told they "forgot" days they were never using the tool for).
        cfg, _, work = make_vault()
        self.assertEqual(wb.unresolved_workdays(cfg, max_days=7), [])

    def test_adoption_floor_excludes_pre_first_note_days(self):
        # First note is a recent workday that's fully resolved. Days BEFORE it must
        # not appear as "no note", even though those files are missing.
        cfg, _, work = make_vault()
        first = self._recent_resolved_workday(work)
        result = wb.unresolved_workdays(cfg, max_days=7)
        for r in result:
            self.assertGreaterEqual(datetime.date.fromisoformat(r["date"]), first)

    def _recent_resolved_workday(self, work):
        d = datetime.date.today() - datetime.timedelta(days=1)
        while d.isoweekday() > 5:
            d -= datetime.timedelta(days=1)
        write_day(work, d, energy_eod=4, reflection="done", done=["- [x] A"])
        return d


class TestReminder(unittest.TestCase):
    def _recent_workday(self):
        d = datetime.date.today() - datetime.timedelta(days=1)
        while d.isoweekday() > 5:
            d -= datetime.timedelta(days=1)
        return d

    def test_status_flags_unresolved(self):
        cfg, _, work = make_vault()
        d = self._recent_workday()
        write_day(work, d, planned=["- [ ] Stuck → perf-q2"])  # no eod
        status = wb.reminder_status(cfg, max_days=1)
        self.assertTrue(status["needs_reminder"])
        self.assertIn("Run /work-buddy catchup", status["message"])
        self.assertTrue(any(u["date"] == d.isoformat() for u in status["unresolved"]))

    def test_status_clean_when_caught_up(self):
        cfg, _, work = make_vault()
        d = self._recent_workday()
        write_day(work, d, energy_eod=4, reflection="done", done=["- [x] A"])
        status = wb.reminder_status(cfg, max_days=1)
        self.assertFalse(status["needs_reminder"])
        self.assertEqual(status["message"], "")

    def test_notify_stdout_delivers_when_unresolved(self):
        cfg, cfg_path, work = make_vault()
        d = self._recent_workday()
        write_day(work, d, planned=["- [ ] Stuck"])
        r = subprocess.run([sys.executable, WB_CLI, "--config", str(cfg_path),
                            "notify", "--channel", "stdout", "--max-days", "1"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("catchup", r.stdout)  # human message on stdout
        self.assertIn("\"delivered\"", r.stderr)  # structured status on stderr

    def test_notify_silent_when_caught_up(self):
        cfg, cfg_path, work = make_vault()
        d = self._recent_workday()
        write_day(work, d, energy_eod=4, reflection="done", done=["- [x] A"])
        r = subprocess.run([sys.executable, WB_CLI, "--config", str(cfg_path),
                            "notify", "--channel", "stdout", "--max-days", "1"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "")  # nothing surfaced to the user

    def test_notify_force_emits_when_nothing_outstanding(self):
        cfg, cfg_path, work = make_vault()
        d = self._recent_workday()
        write_day(work, d, energy_eod=4, reflection="done", done=["- [x] A"])
        r = subprocess.run([sys.executable, WB_CLI, "--config", str(cfg_path),
                            "notify", "--channel", "stdout", "--max-days", "1", "--force"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotEqual(r.stdout.strip(), "")  # force surfaces something


if __name__ == "__main__":
    unittest.main()
