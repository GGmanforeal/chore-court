import itertools
import random
import unittest

from chorecourt import fairness as f


def random_instance(rng, max_people=5, max_chores=14):
    n = rng.randint(2, max_people)
    m = rng.randint(1, max_chores)
    return [[rng.randint(0, 10) for _ in range(m)] for _ in range(n)]


def covers_all(alloc, m):
    return sorted(c for b in alloc for c in b) == list(range(m))


class GuaranteeTests(unittest.TestCase):
    """Property tests: the theorems must hold on hundreds of random households."""

    def test_round_robin_is_always_ef1(self):
        rng = random.Random(1)
        for _ in range(300):
            cost = f.normalise(random_instance(rng))
            a = f.round_robin(cost)
            self.assertTrue(covers_all(a, len(cost[0])))
            self.assertTrue(f.is_ef1(cost, a), cost)

    def test_envy_cycle_elimination_is_always_ef1(self):
        rng = random.Random(2)
        for _ in range(300):
            cost = f.normalise(random_instance(rng))
            a = f.envy_cycle(cost)
            self.assertTrue(covers_all(a, len(cost[0])))
            self.assertTrue(f.is_ef1(cost, a), cost)

    def test_fair_assign_is_always_ef1(self):
        rng = random.Random(3)
        for _ in range(120):
            raw = random_instance(rng, max_chores=24)
            a = f.fair_assign(raw)
            cost = f.normalise(raw)
            self.assertTrue(covers_all(a, len(raw[0])))
            self.assertTrue(f.is_ef1(cost, a))

    def test_optimal_really_is_optimal(self):
        rng = random.Random(4)
        for _ in range(25):
            cost = f.normalise(random_instance(rng, max_people=3, max_chores=6))
            n, m = len(cost), len(cost[0])
            best = f.optimal(cost)
            best_max = max(f.bundle_cost(cost, i, best[i]) for i in range(n))
            for owners in itertools.product(range(n), repeat=m):
                alloc = [[c for c in range(m) if owners[c] == i] for i in range(n)]
                if f.is_ef1(cost, alloc):
                    worst = max(f.bundle_cost(cost, i, alloc[i]) for i in range(n))
                    self.assertGreaterEqual(worst + 1e-9, best_max)

    def test_local_search_never_breaks_ef1_or_gets_worse(self):
        rng = random.Random(5)
        for _ in range(60):
            cost = f.normalise(random_instance(rng, max_chores=20))
            start = f.envy_cycle(cost)
            better = f.improve(cost, start)
            self.assertTrue(f.is_ef1(cost, better))
            self.assertLessEqual(f._objective(cost, better), f._objective(cost, start))


class DefinitionTests(unittest.TestCase):
    def test_normalise(self):
        self.assertEqual(f.normalise([[1, 3], [0, 0]]), [[25.0, 75.0], [50.0, 50.0]])
        with self.assertRaises(ValueError):
            f.normalise([[-1, 2]])

    def test_one_terrible_chore_cannot_be_envy_free_but_is_ef1(self):
        cost = f.normalise([[10], [10]])
        a = f.fair_assign([[10], [10]])
        self.assertFalse(f.is_ef(cost, a))
        self.assertTrue(f.is_ef1(cost, a))

    def test_envy_matrix(self):
        cost = [[60, 40], [50, 50]]
        env = f.envy_matrix(cost, [[0], [1]])
        self.assertEqual(env[0][1], 20)
        self.assertEqual(env[1][0], 0)

    def test_different_tastes_give_everyone_less_than_fair_share(self):
        # one hates dishes, the other hates trash: both end up well under 50%
        raw = [[9, 1, 5, 5], [1, 9, 5, 5]]
        rep = f.report(raw, f.fair_assign(raw))
        self.assertTrue(rep.envy_free)
        self.assertTrue(all(load < 50 for load in rep.loads))

    def test_beats_a_random_chore_wheel(self):
        rng = random.Random(6)
        for _ in range(40):
            raw = random_instance(rng, max_chores=20)
            n, m = len(raw), len(raw[0])
            ours = f.report(raw, f.fair_assign(raw))
            rand = f.report(raw, f.random_assign(n, m, seed=rng.randint(0, 999)))
            self.assertLessEqual(ours.max_envy, rand.max_envy + 1e-9)


if __name__ == "__main__":
    unittest.main()
