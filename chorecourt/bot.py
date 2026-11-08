"""Optional Telegram bot: add it to your family group and let Judge Plov keep order.

Token comes from the CHORECOURT_BOT_TOKEN environment variable only. Each group chat gets
its own household file in ./households/. Commands:

/join            join the household
/rate dishes 8   your dislike rating 0-10 (the bot never repeats or shows anyone's ratings)
/assign          make next week's fair schedule
/today           today's chores
/done 12         mark chore #12 as done (covering for someone earns a justice credit)
/accuse 12       take chore #12 to court
/plead 3 text    your excuse for case #3
/guilty 3, /innocent 3   jury vote
/fairness        how fair this week is
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from . import court
from .court import CourtError, describe_task
from .household import Household

STORE = Path("households")


def handle(h: Household, user: str, text: str, today: int | None = None) -> str:
    """Pure function: (household, sender, message) -> reply. Mutates `h`; the caller saves it."""
    parts = text.strip().split(maxsplit=2)
    if not parts or not parts[0].startswith("/"):
        return ""
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]
    today = date.today().weekday() if today is None else today
    try:
        if cmd in ("/start", "/help"):
            return f"{court.JUDGE} presiding. ⚖️\n" + __doc__.split("Commands:")[1].strip()
        if cmd == "/join":
            h.add_member(user)
            return f"🏠 Welcome to the household, {user}. Rate the chores privately with /rate."
        if cmd == "/rate":
            if len(args) < 2:
                return "Usage: /rate dishes 8   (0 = don't mind, 10 = pure suffering)"
            h.rate(user, args[0], float(args[1]))
            return "🤫 Recorded. Nobody will ever see your rating."
        if cmd == "/assign":
            tasks = h.assign_week()
            rep = h.week_fairness()
            lines = [f"📅 Week {h.week} — {len(tasks)} chores, assigned fairly:"]
            for m in h.members:
                mine = [t for t in h.week_tasks() if t.assignee == m]
                lines.append(f"• {m}: " + ", ".join(f"#{t.id} {t.chore}" for t in mine))
            lines.append(f"Envy-free: {'✅' if rep.envy_free else '—'}  EF1: {'✅' if rep.ef1 else '❌'}  Fair share: {'✅' if rep.proportional else '❌'}")
            return "\n".join(lines)
        if cmd == "/today":
            todo = [t for t in h.week_tasks() if t.day == today]
            if not todo:
                return "Nothing today. Enjoy it while it lasts."
            return "\n".join(("✅ " if t.status == "done" else "⬜ ") + describe_task(t) for t in todo)
        if cmd == "/done":
            t = h.mark_done(int(args[0]), user)
            extra = " Covering for someone: +1 justice credit! 🦸" if t.done_by != t.assignee else ""
            return f"✅ {t.chore} done by {user}.{extra}"
        if cmd == "/accuse":
            t = h.task(int(args[0]))
            c = court.file_case(h, t.id, user)
            return f"{court.reminder(t, 96)}\n⚖️ Case #{c.id}: {user} v. {c.defendant}. {c.defendant}, use /plead {c.id} <excuse>."
        if cmd == "/plead":
            c = court.plead(h, int(args[0]), args[1] if len(args) > 1 else "")
            return f"{court.JUDGE}: {c.judge_note}\nJury ({', '.join(court.jurors(h, c))}): /guilty {c.id} or /innocent {c.id}"
        if cmd in ("/guilty", "/innocent"):
            c = court.vote(h, int(args[0]), user, cmd == "/guilty")
            if c.verdict:
                return f"🔨 VERDICT in case #{c.id}: {c.verdict.upper()}.\n{c.sentence}"
            return f"🗳️ Vote counted ({len(c.votes)}/{len(court.jurors(h, c))})."
        if cmd == "/fairness":
            rep = h.week_fairness()
            loads = ", ".join(f"{m} {v:.0f}%" for m, v in zip(h.members, rep.loads))
            return f"Pain as % of each person's own dislike: {loads}. Fair share: {rep.fair_share:.0f}%. Worst envy: {rep.max_envy:.1f}."
        return "Unknown command. /help"
    except (CourtError, KeyError, ValueError, IndexError) as e:
        return f"🚫 {e.args[0] if e.args else 'That did not work.'}"


def _api(token: str, method: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())


def run_bot() -> int:
    token = os.environ.get("CHORECOURT_BOT_TOKEN", "").strip()
    if not token:
        print("Set CHORECOURT_BOT_TOKEN first (create a bot with @BotFather).", file=sys.stderr)
        return 2
    STORE.mkdir(exist_ok=True)
    print(f"{court.JUDGE} is in session. Ctrl+C to adjourn.")
    offset = 0
    while True:
        try:
            for u in _api(token, "getUpdates", {"offset": offset, "timeout": 30}).get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message")
                if not msg or "text" not in msg:
                    continue
                path = STORE / f"{msg['chat']['id']}.json"
                h = Household.load(path) if path.exists() else Household()
                user = msg["from"].get("first_name") or str(msg["from"]["id"])
                reply = handle(h, user, msg["text"])
                if reply:
                    h.save(path)
                    _api(token, "sendMessage", {"chat_id": msg["chat"]["id"], "text": reply})
        except KeyboardInterrupt:
            print("\nCourt adjourned.")
            return 0
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"network hiccup ({e.__class__.__name__}), retrying…", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(run_bot())
