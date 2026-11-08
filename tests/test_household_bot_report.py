import tempfile
import unittest
from pathlib import Path

from chorecourt.__main__ import main as cli_main
from chorecourt.bot import handle
from chorecourt.demo import run_demo
from chorecourt.household import Household
from chorecourt.report import render


class HouseholdTests(unittest.TestCase):
    def test_instances_are_spread_over_the_week(self):
        h = Household()
        days = {c.name: [d for ch, d in h.instances() if ch.name == c.name] for c in h.chores}
        self.assertEqual(days["Dishes"], list(range(7)))
        self.assertEqual(days["Trash"], [0, 2, 4])

    def test_assign_week_is_fair(self):
        h, _ = run_demo(weeks=1)
        rep = h.week_fairness(1)
        self.assertTrue(rep.ef1)
        self.assertTrue(rep.proportional)
        self.assertEqual(len([t for t in h.week_tasks(1) if not t.sentence]), sum(c.per_week for c in h.chores))

    def test_save_load_round_trip(self):
        h, _ = run_demo(weeks=2)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "h.json"
            h.save(p)
            h2 = Household.load(p)
        self.assertEqual(h2.to_json(), h.to_json())

    def test_validation(self):
        h = Household()
        h.add_member("A")
        with self.assertRaises(ValueError):
            h.add_member("A")
        with self.assertRaises(ValueError):
            h.rate("A", "Dishes", 11)
        with self.assertRaises(ValueError):
            h.assign_week()  # one person is not a court
        self.assertEqual(h.chore("dish").name, "Dishes")


class BotTests(unittest.TestCase):
    def test_conversation(self):
        h = Household()
        self.assertIn("Welcome", handle(h, "Aziza", "/join"))
        handle(h, "Bekzod", "/join@ChoreCourtBot")
        self.assertIn("Recorded", handle(h, "Aziza", "/rate dishes 9"))
        self.assertNotIn("9", handle(h, "Aziza", "/rate trash 9"))  # ratings are never echoed
        out = handle(h, "Aziza", "/assign")
        self.assertIn("Week 1", out)
        self.assertIn("EF1: ✅", out)
        tid = next(t.id for t in h.week_tasks() if t.assignee == "Bekzod")
        self.assertIn("Case #1", handle(h, "Aziza", f"/accuse {tid}"))
        self.assertIn("Judge Plov", handle(h, "Bekzod", "/plead 1 I forgot"))
        self.assertIn("VERDICT", handle(h, "Aziza", "/guilty 1"))
        self.assertIn("🚫", handle(h, "Aziza", "/done 9999"))
        self.assertEqual(handle(h, "Aziza", "just chatting"), "")


class ReportAndCliTests(unittest.TestCase):
    def test_report_has_all_sections(self):
        h, _ = run_demo(weeks=2)
        page = render(h)
        for section in ("This week's schedule", "How fair is it?", "Envy matrix", "Court docket", "Hall of fame"):
            self.assertIn(section, page)

    def test_report_escapes_names(self):
        h = Household()
        h.add_member("<script>alert(1)</script>")
        h.add_member("Malika")
        h.assign_week()
        self.assertNotIn("<script>alert", render(h))

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            f = str(Path(d) / "h.json")
            self.assertEqual(cli_main(["--file", f, "init", "Aziza", "Bekzod"]), 0)
            self.assertEqual(cli_main(["--file", f, "rate", "Aziza", "dishes=9", "trash=1"]), 0)
            self.assertEqual(cli_main(["--file", f, "assign"]), 0)
            self.assertEqual(cli_main(["--file", f, "done", "1"]), 0)
            self.assertEqual(cli_main(["--file", f, "done", "999"]), 1)
            self.assertEqual(cli_main(["--file", f, "report", "--no-open", "--out", str(Path(d) / "r.html")]), 0)
            self.assertTrue((Path(d) / "r.html").exists())


if __name__ == "__main__":
    unittest.main()
