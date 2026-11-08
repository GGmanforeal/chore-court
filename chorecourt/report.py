"""Renders the "Weekly Verdict": one self-contained HTML page (inline CSS + SVG, no JavaScript)."""
from __future__ import annotations

import html
from collections import Counter

from . import fairness
from .court import JUDGE
from .household import DAYS, Household

PALETTE = ["#7c5cff", "#ff8a3d", "#18b37e", "#2f8cff", "#e84a7a", "#c9a227"]


def _e(s: object) -> str:
    return html.escape(str(s))


def _comparison(h: Household) -> list[tuple[str, fairness.FairnessReport]]:
    """How would a random chore wheel or plain round-robin have done on the same week?"""
    tasks = [t for t in h.week_tasks() if not t.sentence]
    inst = [(h.chore(t.chore), t.day) for t in tasks]
    cost = h.cost_matrix(inst)
    n, m = len(h.members), len(inst)
    chosen = [[k for k, t in enumerate(tasks) if t.assignee == p] for p in h.members]
    # average the random baseline over several draws so it isn't a lucky/unlucky single sample
    rand = [fairness.report(cost, fairness.random_assign(n, m, seed=s)) for s in range(20)]
    avg = fairness.FairnessReport(
        loads=[round(sum(r.loads[i] for r in rand) / len(rand), 2) for i in range(n)],
        fair_share=rand[0].fair_share,
        max_envy=round(sum(r.max_envy for r in rand) / len(rand), 2),
        envy_free=all(r.envy_free for r in rand),
        ef1=all(r.ef1 for r in rand),
        proportional=all(r.proportional for r in rand),
    )
    avg_spread = round(sum(r.spread for r in rand) / len(rand), 2)
    rr = fairness.report(cost, fairness.round_robin(fairness.normalise(cost)))
    ours = fairness.report(cost, chosen)
    return [("Random chore wheel (avg of 20)", avg, avg_spread), ("Take-turns picking", rr, rr.spread), ("Chore Court", ours, ours.spread)]


def _bars(h: Household, rep: fairness.FairnessReport) -> str:
    w, row = 520, 38
    hgt = row * len(h.members) + 30
    scale = (w - 150) / max(max(rep.loads), rep.fair_share) / 1.1
    out = [f'<svg viewBox="0 0 {w} {hgt}" class="bars" role="img" aria-label="Each person\'s share of their own dislike">']
    for i, (m, load) in enumerate(zip(h.members, rep.loads)):
        y = 10 + i * row
        out.append(f'<text x="0" y="{y + 18}" class="lbl">{_e(m)}</text>')
        out.append(f'<rect x="90" y="{y + 4}" width="{load * scale:.1f}" height="20" rx="6" fill="{PALETTE[i % len(PALETTE)]}"/>')
        out.append(f'<text x="{96 + load * scale:.1f}" y="{y + 19}" class="val">{load:.1f}%</text>')
    x = 90 + rep.fair_share * scale
    out.append(f'<line x1="{x:.1f}" y1="4" x2="{x:.1f}" y2="{hgt - 18}" stroke="#d33" stroke-dasharray="5 4" stroke-width="2"/>')
    out.append(f'<text x="{x:.1f}" y="{hgt - 4}" text-anchor="middle" class="share">fair share {rep.fair_share:.0f}%</text></svg>')
    return "".join(out)


def _heatmap(h: Household) -> str:
    tasks = [t for t in h.week_tasks() if not t.sentence]
    inst = [(h.chore(t.chore), t.day) for t in tasks]
    cost = fairness.normalise(h.cost_matrix(inst))
    alloc = [[k for k, t in enumerate(tasks) if t.assignee == p] for p in h.members]
    env = fairness.envy_matrix(cost, alloc)
    head = "".join(f"<th>{_e(m)}'s list</th>" for m in h.members)
    rows = []
    for i, m in enumerate(h.members):
        cells = []
        for j in range(len(h.members)):
            if i == j:
                cells.append('<td class="self">—</td>')
            else:
                v = env[i][j]
                alpha = min(1.0, v / 15)
                cells.append(f'<td style="background:rgba(232,74,122,{alpha:.2f})">{v:.1f}</td>')
        rows.append(f"<tr><th>{_e(m)}</th>{''.join(cells)}</tr>")
    return f'<table class="heat"><tr><th></th>{head}</tr>{"".join(rows)}</table>'


def render(h: Household) -> str:
    rep = h.week_fairness()
    tasks = h.week_tasks()
    grid_rows = []
    for i, m in enumerate(h.members):
        cells = []
        for d in range(7):
            chips = []
            for t in tasks:
                if t.assignee == m and t.day == d:
                    c = h.chore(t.chore)
                    cls = f"chip {t.status}{' court' if t.sentence else ''}"
                    title = f"#{t.id} {t.chore} — {t.status}" + (f" (done by {t.done_by})" if t.done_by and t.done_by != m else "") + (" — court-ordered" if t.sentence else "")
                    chips.append(f'<span class="{cls}" title="{_e(title)}">{c.emoji} {_e(c.name)}</span>')
            cells.append(f"<td>{''.join(chips)}</td>")
        grid_rows.append(f'<tr><th><span class="dot" style="background:{PALETTE[i % len(PALETTE)]}"></span>{_e(m)}</th>{"".join(cells)}</tr>')

    comp_rows = "".join(
        f"<tr><td>{_e(name)}</td><td>{r.max_envy:.1f}</td><td>{spread:.1f}</td><td>{'✅' if r.ef1 else '❌'}</td><td>{'✅' if r.proportional else '❌'}</td></tr>"
        for name, r, spread in _comparison(h)
    )

    docket = []
    for c in sorted(h.cases, key=lambda c: -c.id):
        votes = " ".join(("🔴" if g else "🟢") for g in c.votes.values())
        badge = {"guilty": "guilty", "acquitted": "acquitted", None: "pending"}[c.verdict]
        docket.append(
            f'<div class="case"><div class="case-head"><b>Case #{c.id}</b> · week {c.week} · {_e(c.accuser)} v. <b>{_e(c.defendant)}</b>'
            f' <span class="badge {badge}">{badge.upper()}</span></div>'
            f'<div class="excuse">Defence: “{_e(c.excuse or "no comment")}”</div>'
            f'<div class="judge">{JUDGE}: {_e(c.judge_note or "")}</div>'
            f'<div class="votes">Jury: {votes or "voting…"}</div>'
            f'<div class="sentence">{_e(c.sentence or "")}</div></div>'
        )

    done = Counter(t.done_by for t in h.tasks if t.status == "done")
    assigned = Counter(t.assignee for t in h.tasks if t.week <= h.week)
    convictions = Counter(c.defendant for c in h.cases if c.verdict == "guilty")
    board = sorted(h.members, key=lambda m: (-done[m] / max(1, assigned[m]), m))
    board_rows = "".join(
        f"<tr><td>{'🏆' if k == 0 else '🧹' if k < len(board) - 1 else '🫠'} {_e(m)}</td><td>{done[m]}/{assigned[m]}</td>"
        f"<td>{h.credits.get(m, 0)}</td><td>{'⚖️' * convictions[m] or '—'}</td></tr>"
        for k, m in enumerate(board)
    )

    badges = "".join(
        f'<span class="pill {"ok" if ok else "no"}">{"✓" if ok else "✗"} {label}</span>'
        for label, ok in (("Envy-free", rep.envy_free), ("EF1", rep.ef1), ("Proportional", rep.proportional))
    )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chore Court — Week {h.week} verdict</title><style>{CSS}</style></head><body>
<header><div class="seal">⚖️</div><div><h1>Chore Court</h1><p>Weekly Verdict · Week {h.week} · {_e(JUDGE)} presiding</p></div></header>
<main>
<section class="card wide"><h2>This week's schedule</h2>
<p class="muted">Assigned by envy-cycle elimination + local search. Everyone's dislike ratings stay secret — not even this page shows them.</p>
<div class="scroll"><table class="grid"><tr><th></th>{''.join(f'<th>{d}</th>' for d in DAYS)}</tr>{''.join(grid_rows)}</table></div>
<div class="legend"><span class="chip done">done</span><span class="chip todo">to do</span><span class="chip missed">missed</span><span class="chip pardoned">acquitted / pardoned</span><span class="chip todo court">court-ordered</span></div></section>

<section class="card"><h2>How fair is it?</h2>
<p class="muted">Each bar is that person's chores as a share of <i>their own</i> total dislike. Nobody should be above the red line.</p>
{_bars(h, rep)}<div class="pills">{badges}</div></section>

<section class="card"><h2>Envy matrix</h2>
<p class="muted">How much better off the row person would be with the column person's list (0 = no envy).</p>
{_heatmap(h)}
<h2 class="mt">Compared with the usual ways</h2>
<table class="cmp"><tr><th>Method</th><th>Worst envy</th><th>Spread</th><th>EF1</th><th>Fair share</th></tr>{comp_rows}</table></section>

<section class="card"><h2>Court docket</h2>{''.join(docket) or '<p class="muted">No cases. A peaceful household. Suspicious.</p>'}</section>

<section class="card"><h2>Hall of fame &amp; shame</h2>
<table class="cmp"><tr><th>Member</th><th>Done</th><th>Justice credits</th><th>Convictions</th></tr>{board_rows}</table>
<p class="muted">Covering someone else's chore earns a justice credit. Two credits buy a pardon.</p></section>
</main><footer>Generated by Chore Court · github.com/GGmanforeal/chore-court</footer></body></html>"""


CSS = """
:root{--bg:#f4f1ea;--ink:#1f1d1a;--muted:#6f6a62;--card:#fff;--line:#e6e0d4;--gold:#b8892b}
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:16px;align-items:center;padding:22px 32px;background:#1f1d1a;color:#f4f1ea;border-bottom:4px solid var(--gold)}
.seal{font-size:40px;background:var(--gold);width:64px;height:64px;border-radius:50%;display:grid;place-items:center}
h1{margin:0;font-family:Georgia,serif;font-size:30px}header p{margin:2px 0 0;opacity:.8}
main{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:22px 32px;max-width:1280px;margin:0 auto}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px}.wide{grid-column:1/-1}
h2{font-family:Georgia,serif;margin:0 0 6px;font-size:20px}.mt{margin-top:18px}.muted{color:var(--muted);font-size:13.5px;margin:0 0 12px}
.scroll{overflow-x:auto}.grid{border-collapse:collapse;width:100%}.grid th,.grid td{border-bottom:1px solid var(--line);padding:6px;vertical-align:top;text-align:left;font-size:13px}
.grid th{white-space:nowrap}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
.chip{display:inline-block;margin:2px 3px 2px 0;padding:3px 8px;border-radius:999px;font-size:12px;white-space:nowrap;border:1px solid transparent}
.chip.done{background:#dff5e8;border-color:#a9e0c0}.chip.todo{background:#eef2ff;border-color:#c9d4ff}
.chip.missed{background:#ffe1e1;border-color:#f3a6a6;text-decoration:line-through}.chip.pardoned{background:#eee;color:#777}
.chip.court{border:2px dashed #b8892b}.legend{margin-top:10px;font-size:12px}
.bars{width:100%;max-width:520px}.bars .lbl{font-size:14px;font-weight:600}.bars .val{font-size:12px;fill:#555}.bars .share{font-size:11px;fill:#d33}
.pills{margin-top:8px}.pill{display:inline-block;margin-right:8px;padding:4px 10px;border-radius:999px;font-size:13px;font-weight:600}
.pill.ok{background:#dff5e8;color:#127a45}.pill.no{background:#ffe1e1;color:#a12}
table.heat,table.cmp{border-collapse:collapse;width:100%;font-size:13px}.heat th,.heat td,.cmp th,.cmp td{border:1px solid var(--line);padding:6px 8px;text-align:center}
.cmp td:first-child,.cmp th:first-child{text-align:left}.heat .self{color:#bbb}.cmp tr:last-child td{font-weight:700;background:#fbf6e8}
.case{border-left:4px solid var(--gold);padding:8px 12px;margin-bottom:10px;background:#fcfaf5;border-radius:0 10px 10px 0;font-size:13.5px}
.case-head{margin-bottom:4px}.excuse{font-style:italic}.judge{color:#5a4a1c;margin-top:3px}.votes{margin-top:3px}.sentence{margin-top:4px;font-weight:600}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;margin-left:6px}.badge.guilty{background:#ffd9d9;color:#a12}.badge.acquitted{background:#dff5e8;color:#127a45}.badge.pending{background:#eee}
footer{text-align:center;color:var(--muted);font-size:12px;padding:10px 0 24px}
"""
