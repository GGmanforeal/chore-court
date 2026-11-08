"""The household: members, chores, secret ratings, weekly schedules — stored as plain JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import fairness

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Chore:
    name: str
    emoji: str = "🧽"
    per_week: int = 1
    minutes: int = 15


@dataclass
class Task:
    id: int
    week: int
    chore: str
    day: int
    assignee: str
    status: str = "todo"  # todo | done | missed | pardoned
    done_by: str | None = None
    sentence: bool = False  # extra duty handed out by the court


@dataclass
class Case:
    id: int
    week: int
    task_id: int
    defendant: str
    accuser: str
    excuse: str | None = None
    judge_note: str | None = None
    votes: dict[str, bool] = field(default_factory=dict)  # voter -> guilty?
    verdict: str | None = None  # guilty | acquitted
    sentence_level: int = 0
    sentence: str | None = None


DEFAULT_CHORES = [
    Chore("Dishes", "🍽️", 7, 15),
    Chore("Trash", "🗑️", 3, 5),
    Chore("Vacuum", "🧹", 2, 30),
    Chore("Bathroom", "🚽", 1, 40),
    Chore("Cook dinner", "🍚", 3, 60),
    Chore("Laundry", "👕", 2, 20),
    Chore("Groceries", "🛒", 2, 45),
    Chore("Water plants", "🪴", 2, 5),
]


@dataclass
class Household:
    members: list[str] = field(default_factory=list)
    chores: list[Chore] = field(default_factory=lambda: [Chore(**asdict(c)) for c in DEFAULT_CHORES])
    # ratings[member][chore] = how much they hate it, 0 (don't mind) .. 10 (pure suffering)
    ratings: dict[str, dict[str, float]] = field(default_factory=dict)
    week: int = 0
    tasks: list[Task] = field(default_factory=list)
    cases: list[Case] = field(default_factory=list)
    credits: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------ people & chores
    def add_member(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("a member needs a name")
        if name in self.members:
            raise ValueError(f"{name} is already in the household")
        self.members.append(name)
        self.credits.setdefault(name, 0)

    def chore(self, name: str) -> Chore:
        for c in self.chores:
            if c.name.lower() == name.lower() or c.name.lower().startswith(name.lower()):
                return c
        raise KeyError(f"no chore called {name!r}")

    def rate(self, member: str, chore: str, value: float) -> None:
        if member not in self.members:
            raise KeyError(f"{member} is not in the household")
        if not 0 <= value <= 10:
            raise ValueError("ratings go from 0 (don't mind) to 10 (pure suffering)")
        self.ratings.setdefault(member, {})[self.chore(chore).name] = float(value)

    def rating(self, member: str, chore: str) -> float:
        return self.ratings.get(member, {}).get(chore, 5.0)  # unrated = neutral

    # ------------------------------------------------------------ weekly schedule
    def instances(self) -> list[tuple[Chore, int]]:
        """Every chore occurrence this week with its day, spread evenly (dishes every day, trash Mon/Wed/Fri…)."""
        out = []
        for c in self.chores:
            for k in range(c.per_week):
                out.append((c, (k * 7) // c.per_week))
        return out

    def cost_matrix(self, inst: list[tuple[Chore, int]]) -> fairness.Costs:
        # pain = how much you hate it × how long it takes (+1 so "don't mind" still costs a little time)
        return [[(self.rating(m, c.name) + 1) * c.minutes for c, _ in inst] for m in self.members]

    def assign_week(self) -> list[Task]:
        if len(self.members) < 2:
            raise ValueError("a court needs at least two people")
        self.week += 1
        inst = self.instances()
        alloc = fairness.fair_assign(self.cost_matrix(inst))
        next_id = max((t.id for t in self.tasks), default=0) + 1
        new: list[Task] = []
        for i, bundle in enumerate(alloc):
            for c in bundle:
                chore, day = inst[c]
                new.append(Task(next_id, self.week, chore.name, day, self.members[i]))
                next_id += 1
        new.sort(key=lambda t: (t.day, t.chore, t.assignee))
        self.tasks.extend(new)
        return new

    def week_tasks(self, week: int | None = None) -> list[Task]:
        w = self.week if week is None else week
        return [t for t in self.tasks if t.week == w]

    def week_fairness(self, week: int | None = None) -> fairness.FairnessReport:
        """Fairness of the *planned* allocation (court sentences excluded)."""
        tasks = [t for t in self.week_tasks(week) if not t.sentence]
        inst = [(self.chore(t.chore), t.day) for t in tasks]
        alloc = [[k for k, t in enumerate(tasks) if t.assignee == m] for m in self.members]
        return fairness.report(self.cost_matrix(inst), alloc)

    def task(self, task_id: int) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(f"no task #{task_id}")

    def mark_done(self, task_id: int, by: str | None = None) -> Task:
        t = self.task(task_id)
        by = by or t.assignee
        if by not in self.members:
            raise KeyError(f"{by} is not in the household")
        t.status, t.done_by = "done", by
        if by != t.assignee:
            self.credits[by] = self.credits.get(by, 0) + 1  # covering for someone earns a justice credit
        return t

    # ------------------------------------------------------------ persistence
    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict) -> "Household":
        h = cls(
            members=list(d["members"]),
            chores=[Chore(**c) for c in d["chores"]],
            ratings={m: dict(r) for m, r in d.get("ratings", {}).items()},
            week=d.get("week", 0),
            tasks=[Task(**t) for t in d.get("tasks", [])],
            cases=[Case(**c) for c in d.get("cases", [])],
            credits=dict(d.get("credits", {})),
        )
        return h

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Household":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
