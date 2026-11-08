"""Fair division of *chores* (items everybody would rather not get).

Notation: `cost[i][c]` is how much person i dislikes chore c. Each person's costs are
normalised so they sum to 100: everyone has the same "budget of dislike", which makes
people comparable without asking anyone to compare their feelings to someone else's.

Fairness notions implemented and checked:

* **Envy-free (EF):** nobody would rather swap their whole list with someone else's.
* **EF1 (envy-free up to one chore):** any envy disappears if you remove a single chore
  from the envious person's list. EF is often impossible (one awful chore, two people);
  EF1 always exists.
* **PROP:** everyone's pain is at most their fair share, 100 / n.

Algorithms:

* `round_robin` — people take turns picking their least-hated remaining chore (EF1, simple baseline).
* `envy_cycle` — envy-cycle elimination with top-trading cycles (Bhaskar, Sricharan & Vaish, 2020):
  always EF1 for chores, usually much better balanced than round-robin.
* `optimal` — exact search for small households: among all EF1 allocations, minimise
  the worst-off person's pain, then the total pain.
* `fair_assign` — picks `optimal` when the search space is small, otherwise `envy_cycle`
  followed by a local search that only accepts moves keeping EF1.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

Costs = list[list[float]]  # [person][chore]
Allocation = list[list[int]]  # [person] -> chore indices


def normalise(raw: Costs) -> Costs:
    """Scale each person's ratings so they sum to 100 (a zero row becomes uniform)."""
    out = []
    for row in raw:
        if any(v < 0 for v in row):
            raise ValueError("dislike ratings must be >= 0")
        s = sum(row)
        out.append([100 * v / s for v in row] if s > 0 else [100 / len(row)] * len(row))
    return out


def bundle_cost(cost: Costs, i: int, bundle: list[int]) -> float:
    return sum(cost[i][c] for c in bundle)


def envy_matrix(cost: Costs, alloc: Allocation) -> list[list[float]]:
    """envy[i][j] = how much better off i would be with j's list (0 if not at all)."""
    n = len(alloc)
    own = [bundle_cost(cost, i, alloc[i]) for i in range(n)]
    return [[max(0.0, own[i] - bundle_cost(cost, i, alloc[j])) if i != j else 0.0 for j in range(n)] for i in range(n)]


def is_ef(cost: Costs, alloc: Allocation, eps: float = 1e-9) -> bool:
    return all(v <= eps for row in envy_matrix(cost, alloc) for v in row)


def is_ef1(cost: Costs, alloc: Allocation, eps: float = 1e-9) -> bool:
    n = len(alloc)
    for i in range(n):
        if not alloc[i]:
            continue
        own = bundle_cost(cost, i, alloc[i])
        worst = max(cost[i][c] for c in alloc[i])  # dropping your worst chore is the best fix
        for j in range(n):
            if j != i and own - worst > bundle_cost(cost, i, alloc[j]) + eps:
                return False
    return True


def is_prop(cost: Costs, alloc: Allocation, eps: float = 1e-9) -> bool:
    n = len(alloc)
    return all(bundle_cost(cost, i, alloc[i]) <= sum(cost[i]) / n + eps for i in range(n))


# ------------------------------------------------------------------ algorithms


def round_robin(cost: Costs, order: list[int] | None = None) -> Allocation:
    n, m = len(cost), len(cost[0])
    order = order or list(range(n))
    alloc: Allocation = [[] for _ in range(n)]
    left = set(range(m))
    turn = 0
    while left:
        i = order[turn % n]
        c = min(left, key=lambda c: (cost[i][c], c))
        alloc[i].append(c)
        left.remove(c)
        turn += 1
    return alloc


def _find_cycle(succ: dict[int, int]) -> list[int] | None:
    for start in succ:
        seen: dict[int, int] = {}
        v, k = start, 0
        while v in succ and v not in seen:
            seen[v] = k
            v, k = succ[v], k + 1
        if v in seen:
            cyc = [v]
            w = succ[v]
            while w != v:
                cyc.append(w)
                w = succ[w]
            return cyc
    return None


def envy_cycle(cost: Costs) -> Allocation:
    """Envy-cycle elimination for chores using the top-trading envy graph (always EF1)."""
    n, m = len(cost), len(cost[0])
    alloc: Allocation = [[] for _ in range(n)]
    # hardest chores first: they're the ones that need careful placement
    order = sorted(range(m), key=lambda c: -sum(cost[i][c] for i in range(n)))
    for c in order:
        while True:  # terminates: every rotation strictly lowers the pain of everyone in the cycle
            own = [bundle_cost(cost, i, alloc[i]) for i in range(n)]
            sinks = [i for i in range(n) if all(own[i] <= bundle_cost(cost, i, alloc[j]) + 1e-12 for j in range(n))]
            if sinks:
                break
            # top-trading graph: everyone points at the list they like best (all of them envy someone)
            succ = {i: min((j for j in range(n) if j != i), key=lambda j: (bundle_cost(cost, i, alloc[j]), j)) for i in range(n)}
            cyc = _find_cycle(succ)
            assert cyc, "a graph where every node has an out-edge always has a cycle"
            bundles = {i: alloc[succ[i]] for i in cyc}
            for i in cyc:
                alloc[i] = bundles[i]
        # give the chore to the envy-free person who minds it least (relative to their load)
        i = min(sinks, key=lambda i: (cost[i][c] + bundle_cost(cost, i, alloc[i]), i))
        alloc[i] = alloc[i] + [c]
    return [sorted(b) for b in alloc]


def _objective(cost: Costs, alloc: Allocation) -> tuple[float, float]:
    loads = [bundle_cost(cost, i, alloc[i]) for i in range(len(alloc))]
    return (round(max(loads), 9), round(sum(loads), 9))


def optimal(cost: Costs) -> Allocation:
    """Exact: minimise the worst-off person's pain among EF1 allocations (then total pain)."""
    n, m = len(cost), len(cost[0])
    best: Allocation | None = None
    best_key = (float("inf"), float("inf"))
    for owners in itertools.product(range(n), repeat=m):
        alloc: Allocation = [[] for _ in range(n)]
        for c, i in enumerate(owners):
            alloc[i].append(c)
        key = _objective(cost, alloc)
        if key < best_key and is_ef1(cost, alloc):
            best, best_key = alloc, key
    assert best is not None  # an EF1 allocation always exists
    return best


def improve(cost: Costs, alloc: Allocation, rounds: int = 200, seed: int = 0) -> Allocation:
    """Local search: move or swap single chores while it lowers the max pain and keeps EF1."""
    rng = random.Random(seed)
    alloc = [list(b) for b in alloc]
    n = len(alloc)
    key = _objective(cost, alloc)
    for _ in range(rounds):
        improved = False
        moves = [(a, b) for a in range(n) for b in range(n) if a != b]
        rng.shuffle(moves)
        for a, b in moves:
            for c in list(alloc[a]):
                # move c from a to b
                cand = [list(x) for x in alloc]
                cand[a].remove(c)
                cand[b].append(c)
                k = _objective(cost, cand)
                if k < key and is_ef1(cost, cand):
                    alloc, key, improved = cand, k, True
                    break
                # swap c with something of b's
                for d in alloc[b]:
                    cand = [list(x) for x in alloc]
                    cand[a].remove(c)
                    cand[b].remove(d)
                    cand[a].append(d)
                    cand[b].append(c)
                    k = _objective(cost, cand)
                    if k < key and is_ef1(cost, cand):
                        alloc, key, improved = cand, k, True
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            break
    return [sorted(b) for b in alloc]


EXACT_LIMIT = 60_000


def fair_assign(raw_cost: Costs) -> Allocation:
    cost = normalise(raw_cost)
    n, m = len(cost), len(cost[0])
    if n ** m <= EXACT_LIMIT:
        return optimal(cost)
    return improve(cost, envy_cycle(cost))


def random_assign(n: int, m: int, seed: int = 0) -> Allocation:
    """Baseline: how a chore wheel / random draw would do."""
    rng = random.Random(seed)
    alloc: Allocation = [[] for _ in range(n)]
    chores = list(range(m))
    rng.shuffle(chores)
    for k, c in enumerate(chores):
        alloc[k % n].append(c)
    return alloc


@dataclass
class FairnessReport:
    loads: list[float]
    fair_share: float
    max_envy: float
    envy_free: bool
    ef1: bool
    proportional: bool

    @property
    def spread(self) -> float:
        return max(self.loads) - min(self.loads)


def report(raw_cost: Costs, alloc: Allocation) -> FairnessReport:
    cost = normalise(raw_cost)
    n = len(alloc)
    env = envy_matrix(cost, alloc)
    return FairnessReport(
        loads=[round(bundle_cost(cost, i, alloc[i]), 2) for i in range(n)],
        fair_share=round(100 / n, 2),
        max_envy=round(max(max(r) for r in env), 2),
        envy_free=is_ef(cost, alloc),
        ef1=is_ef1(cost, alloc),
        proportional=is_prop(cost, alloc),
    )
