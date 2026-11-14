"""Independent Chip Model (Malmuth-Harville).

icm([5000, 3000, 2000], [100, 60, 40]) -> expected payout for each stack.
"""
from functools import lru_cache


def icm(stacks, payouts):
    n = len(stacks)
    payouts = list(payouts) + [0] * max(0, n - len(payouts))
    full = (1 << n) - 1

    @lru_cache(maxsize=None)
    def ev(mask):
        # Expected payout per player when the players in `mask` are left
        # competing for the next-best place.
        out = [0.0] * n
        left = bin(mask).count("1")
        place = n - left
        if left == 0 or payouts[place] == 0 and not any(payouts[place:]):
            return tuple(out)
        total = sum(stacks[i] for i in range(n) if mask >> i & 1)
        for i in range(n):
            if not mask >> i & 1:
                continue
            p = stacks[i] / total if total else 1 / left
            out[i] += p * payouts[place]
            rest = ev(mask & ~(1 << i))
            for j in range(n):
                out[j] += p * rest[j]
        return tuple(out)

    return list(ev(full))
