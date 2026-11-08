import unittest

from chorecourt import court
from chorecourt.court import CourtError
from chorecourt.household import Household, Task


def household():
    h = Household()
    for m in ("Aziza", "Bekzod", "Malika"):
        h.add_member(m)
    h.rate("Aziza", "Bathroom", 2)
    h.rate("Bekzod", "Bathroom", 10)
    h.rate("Malika", "Bathroom", 9)
    h.assign_week()
    return h


def task_of(h, member):
    return next(t for t in h.week_tasks() if t.assignee == member)


class ReminderTests(unittest.TestCase):
    def test_escalation(self):
        t = Task(1, 1, "Dishes", 0, "Timur")
        levels = [court.reminder_level(hours) for hours in (0, 6, 24, 48, 72, 96)]
        self.assertEqual(levels, [1, 2, 3, 4, 5, 6])
        self.assertIn("Friendly", court.reminder(t, 0))
        self.assertIn("disappointed", court.reminder(t, 30))
        self.assertIn("government", court.reminder(t, 50))
        self.assertIn("Timur vs.", court.reminder(t, 200))


class ExcuseTests(unittest.TestCase):
    def test_categories_in_three_languages(self):
        self.assertEqual(court.judge_excuse("I had an exam")[0], "valid")
        self.assertEqual(court.judge_excuse("Imtihonim bor edi")[0], "valid")
        self.assertEqual(court.judge_excuse("Я болел")[0], "valid")
        self.assertEqual(court.judge_excuse("I forgot")[0], "weak")
        self.assertEqual(court.judge_excuse("Unutdim")[0], "weak")
        self.assertEqual(court.judge_excuse("There was a football match")[0], "weak")
        self.assertEqual(court.judge_excuse("The aliens took the trash")[0], "absurd")
        self.assertEqual(court.judge_excuse("hmm")[0], "unknown")

    def test_the_cat_outranks_sleep(self):
        category, note = court.judge_excuse("The cat was sleeping on the vacuum")
        self.assertEqual(category, "absurd")
        self.assertIn("alibi", note)


class TrialTests(unittest.TestCase):
    def test_full_trial_guilty_and_escalating_sentences(self):
        h = household()
        levels = []
        for t in [t for t in h.week_tasks() if t.assignee == "Bekzod"][:3]:
            case = court.file_case(h, t.id, "Aziza")
            court.plead(h, case.id, "I forgot")
            court.vote(h, case.id, "Aziza", True)
            court.vote(h, case.id, "Malika", True)
            self.assertEqual(case.verdict, "guilty")
            levels.append(case.sentence_level)
        self.assertEqual(levels, [1, 2, 3])
        extra = [t for t in h.tasks if t.sentence]
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0].week, h.week + 1)
        # community service is the chore the *other* people hate most
        self.assertEqual(extra[0].chore, "Bathroom")

    def test_tie_is_broken_by_the_excuse(self):
        h = household()
        t = task_of(h, "Malika")
        case = court.file_case(h, t.id, "Aziza")
        court.plead(h, case.id, "I was sick with a fever")
        court.vote(h, case.id, "Aziza", True)
        court.vote(h, case.id, "Bekzod", False)
        self.assertEqual(case.verdict, "acquitted")
        self.assertEqual(h.task(t.id).status, "pardoned")

    def test_rules_of_procedure(self):
        h = household()
        t = task_of(h, "Malika")
        with self.assertRaises(CourtError):
            court.file_case(h, t.id, "Malika")  # can't accuse yourself
        case = court.file_case(h, t.id, "Aziza")
        with self.assertRaises(CourtError):
            court.file_case(h, t.id, "Bekzod")  # double jeopardy
        with self.assertRaises(CourtError):
            court.vote(h, case.id, "Malika", False)  # defendant can't vote
        done = task_of(h, "Bekzod")
        h.mark_done(done.id)
        with self.assertRaises(CourtError):
            court.file_case(h, done.id, "Aziza")  # it was done!

    def test_pardon_costs_credits(self):
        h = household()
        t = task_of(h, "Malika")
        case = court.file_case(h, t.id, "Aziza")
        with self.assertRaises(CourtError):
            court.pardon(h, case.id, "Bekzod")
        for other in [x for x in h.week_tasks() if x.assignee == "Aziza"][:2]:
            h.mark_done(other.id, by="Bekzod")
        self.assertEqual(h.credits["Bekzod"], 2)
        court.pardon(h, case.id, "Bekzod")
        self.assertEqual(case.verdict, "acquitted")
        self.assertEqual(h.credits["Bekzod"], 0)


if __name__ == "__main__":
    unittest.main()
