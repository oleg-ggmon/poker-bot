"""Fast pure-Python hand evaluator. Cards are ints 0..51: rank = c >> 2 (0='2' .. 12='A'), suit = c & 3."""

POP = [bin(i).count("1") for i in range(8192)]
STRAIGHT = [0] * 8192
for _m in range(8192):
    _best = 0
    for _hi in range(12, 3, -1):
        _w = 0x1F << (_hi - 4)
        if _m & _w == _w:
            _best = _hi
            break
    if not _best and (_m & 0x100F) == 0x100F:
        _best = 3
    STRAIGHT[_m] = _best


def _top(m, n):
    out = 0
    for _ in range(n):
        if not m:
            break
        b = 1 << (m.bit_length() - 1)
        out |= b
        m ^= b
    return out


TOP5 = [_top(m, 5) for m in range(8192)]
TOP3 = [_top(m, 3) for m in range(8192)]
TOP2 = [_top(m, 2) for m in range(8192)]


def ev(cards):
    """Rank 5-7 cards. Bigger is better. Category is value >> 26 (0 high card .. 8 straight flush)."""
    m1 = m2 = m3 = m4 = 0
    s0 = s1 = s2 = s3 = 0
    for c in cards:
        b = 1 << (c >> 2)
        s = c & 3
        if s == 0:
            s0 |= b
        elif s == 1:
            s1 |= b
        elif s == 2:
            s2 |= b
        else:
            s3 |= b
        m4 |= m3 & b
        m3 |= m2 & b
        m2 |= m1 & b
        m1 |= b
    for sm in (s0, s1, s2, s3):
        if POP[sm] >= 5:
            st = STRAIGHT[sm]
            if st:
                return (8 << 26) | st
            return (5 << 26) | TOP5[sm]
    if m4:
        q = m4.bit_length() - 1
        return (7 << 26) | (q << 4) | ((m1 ^ (1 << q)).bit_length() - 1)
    t = 0
    if m3:
        t = m3.bit_length() - 1
        r = m2 ^ (1 << t)
        if r:
            return (6 << 26) | (t << 4) | (r.bit_length() - 1)
    st = STRAIGHT[m1]
    if st:
        return (4 << 26) | st
    if m3:
        return (3 << 26) | (t << 13) | TOP2[m1 ^ (1 << t)]
    if m2:
        p = m2.bit_length() - 1
        r = m2 ^ (1 << p)
        if r:
            p2 = r.bit_length() - 1
            return (2 << 26) | (p << 8) | (p2 << 4) | ((m1 ^ (1 << p) ^ (1 << p2)).bit_length() - 1)
        return (1 << 26) | (p << 13) | TOP3[m1 ^ (1 << p)]
    return TOP5[m1]


def cls(c1, c2):
    """Hand class 0..168 on a 13x13 grid: pairs on the diagonal, suited above (hi*13+lo), offsuit below."""
    r1 = c1 >> 2
    r2 = c2 >> 2
    if r1 == r2:
        return r1 * 14
    hi, lo = (r1, r2) if r1 > r2 else (r2, r1)
    if (c1 & 3) == (c2 & 3):
        return hi * 13 + lo
    return lo * 13 + hi
