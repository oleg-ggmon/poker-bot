"""Cards and a 7-card hand evaluator.

Cards are strings like "As", "Td", "2c" (rank + suit).
Internally a card is an int 0..51: rank_index * 4 + suit_index,
rank_index 0..12 for 2..A, suit_index 0..3 for c, d, h, s.
"""

RANKS = "23456789TJQKA"
SUITS = "cdhs"

HAND_NAMES = [
    "High Card", "Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush",
]


def to_int(card):
    return RANKS.index(card[0]) * 4 + SUITS.index(card[1])


def to_str(c):
    return RANKS[c >> 2] + SUITS[c & 3]


def full_deck():
    return list(range(52))


def _straight_high(mask):
    """Highest rank index of a 5-card straight in a 13-bit rank mask, or -1."""
    m = (mask << 1) | (1 if mask & (1 << 12) else 0)  # ace also plays low
    for top in range(13, 3, -1):
        if (m >> (top - 4)) & 0b11111 == 0b11111:
            return top - 1
    return -1


def evaluate(cards):
    """Score the best 5-card hand from 5-7 int cards. Higher tuple wins."""
    counts = [0] * 13
    suit_cards = ([], [], [], [])
    mask = 0
    for c in cards:
        r = c >> 2
        counts[r] += 1
        suit_cards[c & 3].append(r)
        mask |= 1 << r

    for sc in suit_cards:
        if len(sc) >= 5:
            fmask = 0
            for r in sc:
                fmask |= 1 << r
            sh = _straight_high(fmask)
            if sh >= 0:
                return (8, sh)
            flush = tuple(sorted(sc, reverse=True)[:5])
            break
    else:
        flush = None

    groups = sorted(((n, r) for r, n in enumerate(counts) if n), reverse=True)
    top_n, top_r = groups[0]

    if top_n == 4:
        kicker = max(r for r in range(13) if counts[r] and r != top_r)
        return (7, top_r, kicker)
    if top_n == 3 and len(groups) > 1 and groups[1][0] >= 2:
        return (6, top_r, groups[1][1])
    if flush:
        return (5,) + flush
    sh = _straight_high(mask)
    if sh >= 0:
        return (4, sh)
    singles = [r for n, r in groups if n == 1]
    if top_n == 3:
        return (3, top_r) + tuple(singles[:2])
    if top_n == 2:
        pairs = [r for n, r in groups if n == 2]
        if len(pairs) >= 2:
            rest = [r for r in range(12, -1, -1) if counts[r] and r not in pairs[:2]]
            return (2, pairs[0], pairs[1], rest[0])
        return (1, top_r) + tuple(singles[:3])
    return (0,) + tuple(singles[:5])


def hand_name(score):
    return HAND_NAMES[score[0]]
