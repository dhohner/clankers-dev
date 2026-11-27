"""Compares first_overdue and overdue_total in <repo> with their staged versions.

Usage: python3 -I check-overdue.py <repo>
Results must match exactly, including which invoice wins a tie on the due date.
"""
import itertools, subprocess, sys, types
from datetime import date

repo = sys.argv[1]
def load(src, name):
    mod = types.ModuleType(name)
    exec(src, mod.__dict__)
    return mod
ref = load(subprocess.run(["git", "show", ":shop/overdue.py"], cwd=repo, capture_output=True, text=True, check=True).stdout, "ref")
new = load(open(f"{repo}/shop/overdue.py").read(), "new")
days = [date(2026, 1, d) for d in (1, 5, 5, 9)]
pool = [{"id": i, "due": d, "paid": p, "amount": 10 + i} for i, (d, p) in enumerate(itertools.product(days, (False, True)))]
mismatches = 0
for n in range(4):
    for combo in itertools.permutations(pool, n):
        for today in (date(2026, 1, 1), date(2026, 1, 6), date(2026, 1, 31)):
            for fn in ("first_overdue", "overdue_total"):
                a, b = getattr(ref, fn)(list(combo), today), getattr(new, fn)(list(combo), today)
                if (a is b) if isinstance(a, dict) else (a == b):
                    continue
                mismatches += 1
print("behavior mismatches against the staged version:", mismatches)
