"""Chore Court command line.

    python -m chorecourt demo                      simulate 3 weeks of a family and open the report
    python -m chorecourt init Aziza Bekzod Malika  start a household (household.json)
    python -m chorecourt rate Aziza dishes=3 bathroom=9 ...   secret dislike ratings 0-10
    python -m chorecourt assign                    fair schedule for next week
    python -m chorecourt show                      this week's chores
    python -m chorecourt done 12 [--by Malika]     mark chore #12 done (covering = justice credit)
    python -m chorecourt accuse 12 --by Aziza      take chore #12 to court
    python -m chorecourt plead 3 "I had an exam"   defendant's excuse for case #3
    python -m chorecourt vote 3 Malika guilty      jury vote (guilty / innocent)
    python -m chorecourt pardon 3 --by Malika      spend 2 justice credits on a pardon
    python -m chorecourt report                    write report.html (the Weekly Verdict)
    python -m chorecourt bot                       Telegram bot for a family group chat
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from . import court
from .court import CourtError, describe_task
from .household import Household


def _load(path: Path) -> Household:
    if not path.exists():
        sys.exit(f"No household at {path}. Start one with: python -m chorecourt init NAME NAME ...")
    return Household.load(path)


def _write_report(h: Household, out: Path, open_it: bool) -> None:
    from .report import render

    out.write_text(render(h), encoding="utf-8")
    print(f"📜 Weekly Verdict written to {out.resolve()}")
    if open_it:
        webbrowser.open(out.resolve().as_uri())


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="chorecourt", description="Fair chores. Real consequences.", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--file", default="household.json", type=Path, help="household file (default: household.json)")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--weeks", type=int, default=3)
    d.add_argument("--out", type=Path, default=Path("report.html"))
    d.add_argument("--no-open", action="store_true")
    i = sub.add_parser("init")
    i.add_argument("members", nargs="+")
    r = sub.add_parser("rate")
    r.add_argument("member")
    r.add_argument("ratings", nargs="+", help="chore=0..10")
    sub.add_parser("assign")
    sub.add_parser("show")
    dn = sub.add_parser("done")
    dn.add_argument("task", type=int)
    dn.add_argument("--by")
    ac = sub.add_parser("accuse")
    ac.add_argument("task", type=int)
    ac.add_argument("--by", required=True)
    pl = sub.add_parser("plead")
    pl.add_argument("case", type=int)
    pl.add_argument("excuse")
    v = sub.add_parser("vote")
    v.add_argument("case", type=int)
    v.add_argument("voter")
    v.add_argument("decision", choices=["guilty", "innocent"])
    pa = sub.add_parser("pardon")
    pa.add_argument("case", type=int)
    pa.add_argument("--by", required=True)
    sub.add_parser("bot", help="run the Telegram bot (needs CHORECOURT_BOT_TOKEN)")
    rp = sub.add_parser("report")
    rp.add_argument("--out", type=Path, default=Path("report.html"))
    rp.add_argument("--no-open", action="store_true")
    a = p.parse_args(argv)

    try:
        if a.cmd == "demo":
            from .demo import run_demo

            h, log = run_demo(a.weeks)
            print("\n".join(log))
            _write_report(h, a.out, not a.no_open)
            return 0
        if a.cmd == "bot":
            from .bot import run_bot

            return run_bot()
        if a.cmd == "init":
            if a.file.exists():
                sys.exit(f"{a.file} already exists — the court does not overwrite households.")
            h = Household()
            for m in a.members:
                h.add_member(m)
            h.save(a.file)
            print(f"🏠 Household created with {', '.join(h.members)}.")
            print("Chores: " + ", ".join(f"{c.emoji} {c.name} ×{c.per_week}/week" for c in h.chores))
            print("Next: everyone rates chores in secret, e.g.  python -m chorecourt rate NAME dishes=8 trash=2")
            return 0

        h = _load(a.file)
        if a.cmd == "rate":
            for item in a.ratings:
                chore, _, val = item.partition("=")
                h.rate(a.member, chore, float(val))
            print(f"🤫 {a.member}'s ratings are recorded (and will never be shown to anyone).")
        elif a.cmd == "assign":
            tasks = h.assign_week()
            rep = h.week_fairness()
            print(f"📅 Week {h.week}: {len(tasks)} chores.")
            for m in h.members:
                print(f"  {m}: " + ", ".join(f"#{t.id} {t.chore}" for t in h.week_tasks() if t.assignee == m))
            print(f"Fairness: envy-free={rep.envy_free}, EF1={rep.ef1}, proportional={rep.proportional}, loads={rep.loads}")
        elif a.cmd == "show":
            for t in h.week_tasks():
                print(("✅ " if t.status == "done" else "❌ " if t.status == "missed" else "⬜ ") + describe_task(t))
        elif a.cmd == "done":
            t = h.mark_done(a.task, a.by)
            print(f"✅ #{t.id} {t.chore} done by {t.done_by}." + (" +1 justice credit!" if t.done_by != t.assignee else ""))
        elif a.cmd == "accuse":
            t = h.task(a.task)
            print(court.reminder(t, 96))
            c = court.file_case(h, a.task, a.by)
            print(f"⚖️ Case #{c.id} opened: {c.accuser} v. {c.defendant}. The defendant may now plead.")
        elif a.cmd == "plead":
            c = court.plead(h, a.case, a.excuse)
            print(f"{court.JUDGE}: {c.judge_note}\nJurors: {', '.join(court.jurors(h, c))} — please vote.")
        elif a.cmd == "vote":
            c = court.vote(h, a.case, a.voter, a.decision == "guilty")
            print(f"🗳️ {a.voter} voted {a.decision}.")
            if c.verdict:
                print(f"🔨 VERDICT: {c.verdict.upper()}. {c.sentence}")
        elif a.cmd == "pardon":
            c = court.pardon(h, a.case, a.by)
            print(f"🕊️ {c.sentence}")
        elif a.cmd == "report":
            _write_report(h, a.out, not a.no_open)
        h.save(a.file)
    except (CourtError, KeyError, ValueError) as e:
        msg = e.args[0] if e.args else str(e)
        print(f"🚫 {msg}", file=sys.stderr)
        return 1
    return 0


def cli() -> None:
    sys.exit(main())


if __name__ == "__main__":
    cli()
