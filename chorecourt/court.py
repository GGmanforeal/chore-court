"""The Honourable Judge Plov 🍚 presiding.

Reminders get more passive-aggressive the longer a chore is overdue, missed chores go to
trial, the household is the jury, and repeat offenders receive increasingly creative
(but always fair) sentences.
"""
from __future__ import annotations

import re
from collections import Counter

from .household import DAYS, Case, Household, Task

JUDGE = "Judge Plov 🍚"

# ------------------------------------------------------------------ reminders

REMINDERS = [
    (0, "🙂 Friendly reminder: {chore} is on your list today, {name}."),
    (6, "🙂 Just checking in! {chore} is still waiting for you, {name}. No pressure. 🙂"),
    (24, "😐 {name}. {chore}. It's been a day. I'm not mad, I'm just disappointed."),
    (48, "😑 Day 2 of '{chore_lower}' being undone. It has started forming its own government."),
    (72, "📜 {name}, this is your final notice before {judge} gets involved. '{chore}' has hired a lawyer."),
    (96, "⚖️ Case automatically filed. {name} vs. The People Who Have To Live Here."),
]


def reminder(task: Task, hours_overdue: float) -> str:
    """The longer it waits, the more passive-aggressive the tone (6 escalation levels)."""
    text = REMINDERS[0][1]
    for threshold, t in REMINDERS:
        if hours_overdue >= threshold:
            text = t
    return text.format(chore=task.chore, chore_lower=task.chore.lower(), name=task.assignee, judge=JUDGE)


def reminder_level(hours_overdue: float) -> int:
    return sum(1 for threshold, _ in REMINDERS if hours_overdue >= threshold)


# ------------------------------------------------------------------ excuses

EXCUSES = [
    # (pattern, category, judge's comment)
    (r"\b(sick|ill|fever|flu|hospital|kasal|isitma|shifoxona|болел|болею|температур|больниц)", "valid",
     "The court wishes the defendant a speedy recovery. Being ill is a valid defence."),
    (r"\b(exam|test|olympiad|imtihon|olimpiada|экзамен|контрольн|олимпиад)", "valid",
     "Exam week is recognised by the court as a natural disaster. Defence accepted."),
    (r"\b(funeral|wedding|to'y|janoza|похорон|свадьб)", "valid",
     "Family events take priority. The court sends its regards."),
    (r"\b(cat|dog|mushuk|kuchuk|кот|собак)", "absurd",
     "The court has reviewed the evidence and the cat has an alibi."),
    (r"\b(alien|ufo|ghost|jin|wifi|internet|инопланет)", "absurd",
     "Creative. Unconvincing. The court awards points for imagination and zero for the excuse."),
    (r"\b(forgot|forget|unutdim|esimdan|забыл)", "weak",
     "Ignorance of the chore schedule is no excuse. The schedule was literally on the fridge."),
    (r"\b(tired|sleep|nap|charchadim|uxlab|устал|спал)", "weak",
     "The court is also tired. The court still did the dishes."),
    (r"\b(busy|band edim|занят)", "weak",
     "Everyone is busy. The dishes are not impressed by your calendar."),
    (r"\b(game|gaming|football|futbol|match|netflix|series|serial|youtube|tiktok|игр|сериал)", "weak",
     "So the defendant chose entertainment over civic duty. Noted. Strongly noted."),
    (r"\b(not my turn|wasn't mine|navbatim emas|не моя очередь)", "weak",
     "The algorithm is mathematically envy-free up to one chore. It was your turn."),
]


def judge_excuse(excuse: str) -> tuple[str, str]:
    """Returns (category, Judge Plov's comment). Category: valid | weak | absurd | unknown."""
    low = excuse.lower()
    for pattern, category, note in EXCUSES:
        if re.search(pattern, low):
            return category, note
    if not low.strip():
        return "unknown", "The defendant remains silent. Bold strategy."
    return "unknown", "The court has heard the defence. The jury will decide."


# ------------------------------------------------------------------ sentences

SENTENCES = {
    1: "Official warning. Your name is written on the fridge whiteboard in *small* letters.",
    2: "A passive-aggressive sticky note will be placed on your door for 48 hours. 🟨",
    3: "Community service: you get the chore everyone else hates most, once, next week.",
    4: "Community service ×2 and your playlist loses aux privileges in the kitchen for a week.",
    5: "Maximum sentence: double community service, and Buvi (grandma) will be informed. 👵",
}


def prior_convictions(h: Household, member: str, within_weeks: int = 4) -> int:
    return sum(1 for c in h.cases if c.defendant == member and c.verdict == "guilty" and c.week > h.week - within_weeks)


def most_hated_chore(h: Household, exclude: str) -> str:
    """The chore with the highest average dislike among everyone except the convicted person."""
    others = [m for m in h.members if m != exclude] or h.members
    return max(h.chores, key=lambda c: (sum(h.rating(m, c.name) for m in others) / len(others), c.minutes)).name


# ------------------------------------------------------------------ the trial


class CourtError(ValueError):
    pass


def file_case(h: Household, task_id: int, accuser: str) -> Case:
    t = h.task(task_id)
    if t.status == "done":
        raise CourtError(f"Task #{task_id} was done by {t.done_by}. Case dismissed, and the accuser owes them a thank-you.")
    if any(c.task_id == task_id for c in h.cases):
        raise CourtError(f"Task #{task_id} is already in court.")
    if accuser not in h.members:
        raise CourtError(f"{accuser} is not in the household and has no standing in this court.")
    if accuser == t.assignee:
        raise CourtError("Self-incrimination is admirable but unnecessary. Just do the chore.")
    t.status = "missed"
    case = Case(id=max((c.id for c in h.cases), default=0) + 1, week=t.week, task_id=task_id, defendant=t.assignee, accuser=accuser)
    h.cases.append(case)
    return case


def plead(h: Household, case_id: int, excuse: str) -> Case:
    case = _case(h, case_id)
    if case.verdict:
        raise CourtError("This case is closed.")
    case.excuse = excuse.strip()
    _, case.judge_note = judge_excuse(case.excuse)
    return case


def jurors(h: Household, case: Case) -> list[str]:
    return [m for m in h.members if m != case.defendant]


def vote(h: Household, case_id: int, voter: str, guilty: bool) -> Case:
    """Jury = everyone except the defendant. Majority decides; a tie is resolved by the judge using the excuse."""
    case = _case(h, case_id)
    if case.verdict:
        raise CourtError("This case is closed.")
    if voter == case.defendant:
        raise CourtError("The defendant may not vote in their own trial. Nice try.")
    if voter not in h.members:
        raise CourtError(f"{voter} is not in the household.")
    case.votes[voter] = guilty
    jury = jurors(h, case)
    if len(case.votes) == len(jury):
        tally = Counter(case.votes.values())
        if tally[True] != tally[False]:
            guilty_verdict = tally[True] > tally[False]
        else:
            guilty_verdict = judge_excuse(case.excuse or "")[0] != "valid"
        _close(h, case, guilty_verdict)
    return case


def pardon(h: Household, case_id: int, member: str, cost: int = 2) -> Case:
    """Spend justice credits (earned by covering other people's chores) to pardon a case."""
    case = _case(h, case_id)
    if case.verdict:
        raise CourtError("This case is closed.")
    if h.credits.get(member, 0) < cost:
        raise CourtError(f"A pardon costs {cost} justice credits. {member} has {h.credits.get(member, 0)}.")
    h.credits[member] -= cost
    case.verdict = "acquitted"
    case.sentence = f"Pardoned by {member} (−{cost} credits). How generous."
    h.task(case.task_id).status = "pardoned"
    return case


def _close(h: Household, case: Case, guilty: bool) -> None:
    if not guilty:
        case.verdict = "acquitted"
        case.sentence = "Acquitted. The defendant leaves the court with their dignity mostly intact."
        h.task(case.task_id).status = "pardoned"
        return
    level = min(5, prior_convictions(h, case.defendant) + 1)  # count before marking this case guilty
    case.verdict = "guilty"
    case.sentence_level = level
    case.sentence = SENTENCES[level]
    extra = 2 if level >= 4 else 1 if level >= 3 else 0
    if extra:
        chore = most_hated_chore(h, case.defendant)
        case.sentence += f" (Extra: {extra}× {chore}.)"
        next_id = max(t.id for t in h.tasks) + 1
        for k in range(extra):
            # served next week; the day is spread so it doesn't all land on Monday
            h.tasks.append(Task(next_id + k, h.week + 1, chore, (2 + 3 * k) % 7, case.defendant, sentence=True))


def _case(h: Household, case_id: int) -> Case:
    for c in h.cases:
        if c.id == case_id:
            return c
    raise CourtError(f"No case #{case_id}.")


def describe_task(t: Task) -> str:
    tag = " ⚖️ (court-ordered)" if t.sentence else ""
    return f"#{t.id} {DAYS[t.day]} {t.chore} → {t.assignee}{tag}"
