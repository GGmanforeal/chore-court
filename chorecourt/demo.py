"""A simulated household so you can watch the court work without recruiting your family."""
from __future__ import annotations

import random

from . import court
from .household import Household

PEOPLE = {
    # name: (reliability, {chore: dislike 0-10})
    "Aziza": (0.95, {"Dishes": 3, "Trash": 6, "Vacuum": 2, "Bathroom": 9, "Cook dinner": 1, "Laundry": 4, "Groceries": 5, "Water plants": 0}),
    "Bekzod": (0.80, {"Dishes": 9, "Trash": 2, "Vacuum": 5, "Bathroom": 7, "Cook dinner": 8, "Laundry": 6, "Groceries": 1, "Water plants": 3}),
    "Malika": (0.90, {"Dishes": 5, "Trash": 8, "Vacuum": 7, "Bathroom": 6, "Cook dinner": 3, "Laundry": 1, "Groceries": 6, "Water plants": 2}),
    "Timur": (0.65, {"Dishes": 8, "Trash": 4, "Vacuum": 6, "Bathroom": 10, "Cook dinner": 2, "Laundry": 9, "Groceries": 3, "Water plants": 5}),
}

EXCUSES = [
    "I had an exam on Thursday",
    "I forgot, sorry",
    "There was a football match",
    "I was sick with a fever",
    "The cat was sleeping on the vacuum",
    "It was not my turn",
    "The wifi was down so I couldn't see the schedule",
    "I was tired",
]


def sample_household() -> Household:
    h = Household()
    for name, (_, ratings) in PEOPLE.items():
        h.add_member(name)
        for chore, v in ratings.items():
            h.rate(name, chore, v)
    return h


def simulate_week(h: Household, rng: random.Random, log: list[str]) -> None:
    tasks = h.assign_week()
    log.append(f"\n=== Week {h.week}: {len(tasks)} chores assigned fairly ===")
    for t in h.week_tasks():
        if t.status != "todo":
            continue
        reliability = PEOPLE.get(t.assignee, (0.8, {}))[0]
        if rng.random() < reliability:
            # sometimes a sibling covers for you and earns a justice credit
            helper = rng.choice(h.members) if rng.random() < 0.08 else t.assignee
            h.mark_done(t.id, by=helper)
            if helper != t.assignee:
                log.append(f"🦸 {helper} covered {t.assignee}'s {t.chore} (+1 justice credit)")
            continue
        log.append(court.reminder(t, 30))
        accuser = rng.choice([m for m in h.members if m != t.assignee])
        case = court.file_case(h, t.id, accuser)
        court.plead(h, case.id, rng.choice(EXCUSES))
        log.append(f"⚖️  Case #{case.id}: {accuser} v. {case.defendant} — “{case.excuse}”")
        log.append(f"   {court.JUDGE}: {case.judge_note}")
        category, _ = court.judge_excuse(case.excuse or "")
        for juror in court.jurors(h, case):
            # jurors are mostly reasonable: valid excuses usually win, absurd ones usually lose
            p_guilty = {"valid": 0.15, "weak": 0.8, "absurd": 0.6, "unknown": 0.5}[category]
            court.vote(h, case.id, juror, rng.random() < p_guilty)
        log.append(f"   Verdict: {case.verdict.upper()}. {case.sentence}")


def run_demo(weeks: int = 3, seed: int = 7) -> tuple[Household, list[str]]:
    rng = random.Random(seed)
    h = sample_household()
    log: list[str] = []
    for _ in range(weeks):
        simulate_week(h, rng, log)
    return h, log
