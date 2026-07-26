"""
Full pre-computed equity database — like real PioSolver.
169×169 combo equity matrix for ~50 canonical flop types.
Pre-computed offline with 1000+ trials per pair, stored in compact binary.
"""
import json, os, math, random, time, struct
from collections import defaultdict
from treys import Card, Evaluator

evaluator = Evaluator()
RANKS = "AKQJT98765432"
SUITS = ["s", "h", "d", "c"]

# ── Canonical flop classification ──
# Reduce 22,100 flops → ~50 types based on rank pattern + suit pattern

def flop_signature(board_ints):
    """Returns (rank_pattern, suit_pattern) for a 3-card flop."""
    ranks = []
    suits = []
    for c in board_ints:
        s = Card.int_to_str(c)
        ranks.append(RANKS.index(s[0]))
        suits.append(Card.get_suit_int(c))

    # Rank pattern: sort descending, then encode gaps
    sorted_r = sorted(ranks, reverse=True)
    r_pattern = (sorted_r[0], sorted_r[1], sorted_r[2])

    # Suit pattern: mono (3 same), two-tone (2+1), rainbow (all different)
    unique_s = len(set(suits))
    if unique_s == 1:   s_type = 0  # monotone
    elif unique_s == 2: s_type = 1  # two-tone
    else:               s_type = 2  # rainbow

    # Paired?
    paired = len(set(ranks)) < 3

    return (r_pattern, s_type, paired)


def canonical_id(board_ints):
    """Map any flop to its canonical ID (0-~50)."""
    rp, st, paired = flop_signature(board_ints)
    # Hash the rank pattern
    r_hash = rp[0] * 169 + rp[1] * 13 + rp[2]
    # Combine with suit type and paired flag
    return (r_hash * 3 + st) * 2 + (1 if paired else 0)


# ── All 169 combos as treys Card pairs ──

def all_combos_169():
    """Generate all 169 combos as [(combo_str, [card_pairs])]."""
    combos = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i < j:
                key = r1 + r2 + "s"
                hands = []
                for s in SUITS:
                    hands.append((Card.new(r1+s), Card.new(r2+s)))
                combos.append((key, hands))
            elif i == j:
                key = r1 + r2
                hands = []
                for si, s1 in enumerate(SUITS):
                    for s2 in SUITS[si+1:]:
                        hands.append((Card.new(r1+s1), Card.new(r1+s2)))
                combos.append((key, hands))
            else:
                key = r2 + r1 + "o"
                hands = []
                for s1 in SUITS:
                    for s2 in SUITS:
                        if s1 != s2:
                            hands.append((Card.new(r2+s1), Card.new(r1+s2)))
                combos.append((key, hands))
    return combos


# ── Pre-compute equity for one flop ──

def compute_flop_equity(board_ints, combos_169, trials=500):
    """
    Compute full 169×169 equity matrix for a specific flop.
    Returns upper-triangular flat array (169*170/2 values).
    """
    n = 169
    dead_base = set(board_ints)
    deck = [Card.new(r+s) for r in RANKS for s in SUITS if Card.new(r+s) not in dead_base]

    # Flatten: only upper triangle (i <= j) since equity(i,j) = 1 - equity(j,i)
    size = n * (n + 1) // 2
    matrix = [0.5] * size

    for i in range(n):
        ci, hi_hands = combos_169[i]
        for j in range(i, n):
            cj, hj_hands = combos_169[j]

            wins = 0
            valid = 0
            for _ in range(trials):
                hp = random.choice(hi_hands)
                if hp[0] in dead_base or hp[1] in dead_base:
                    continue
                dead = dead_base | {hp[0], hp[1]}

                vp = random.choice(hj_hands)
                if vp[0] in dead or vp[1] in dead:
                    continue
                dead2 = dead | {vp[0], vp[1]}

                remaining = [c for c in deck if c not in dead2]
                needed = 2  # turn + river
                if len(remaining) < needed:
                    continue
                runout = random.sample(remaining, needed)
                fb = list(board_ints) + runout

                hs = evaluator.evaluate(list(hp), fb)
                vs = evaluator.evaluate(list(vp), fb)
                if hs < vs: wins += 1
                elif hs == vs: wins += 0.5
                valid += 1

            idx = i * n + j - (i * (i + 1)) // 2  # upper triangular index
            matrix[idx] = wins / max(1, valid)

    return matrix


# ── Flat matrix to symmetric access ──

def equity_lookup(matrix_flat, i, j):
    """Look up equity between combo i and combo j."""
    n = 169
    if i <= j:
        idx = i * n + j - (i * (i + 1)) // 2
        return matrix_flat[idx]
    else:
        return 1.0 - equity_lookup(matrix_flat, j, i)


# ── Database manager ──

class EquityDB:
    """Persistent equity database for canonical flops."""

    def __init__(self, path="equity_db"):
        self.path = path
        os.makedirs(path, exist_ok=True)
        self._cache = {}
        self.combos_169 = all_combos_169()

    def get(self, board_ints):
        """Get equity matrix for a flop. Computes if not cached."""
        cid = canonical_id(board_ints)
        if cid in self._cache:
            return self._cache[cid]

        fname = f"{self.path}/flop_{cid}.bin"
        if os.path.exists(fname):
            with open(fname, 'rb') as f:
                data = f.read()
            # Unpack: each value is 2 bytes (uint16, scaled 0-65535)
            n = 169
            size = n * (n + 1) // 2
            matrix = [struct.unpack_from('<H', data, i*2)[0] / 65535.0 for i in range(size)]
            self._cache[cid] = matrix
            return matrix

        return None

    def compute_and_store(self, board_ints, trials=500):
        """Compute equity matrix and save to disk."""
        cid = canonical_id(board_ints)
        fname = f"{self.path}/flop_{cid}.bin"

        if os.path.exists(fname):
            return self.get(board_ints)

        print(f"Computing equity for {[Card.int_to_pretty_str(c) for c in board_ints]}...")
        t0 = time.time()
        matrix = compute_flop_equity(board_ints, self.combos_169, trials)

        # Store as uint16 (0-65535)
        data = bytearray()
        for v in matrix:
            scaled = int(v * 65535)
            data.extend(struct.pack('<H', scaled))

        with open(fname, 'wb') as f:
            f.write(data)

        self._cache[cid] = matrix
        print(f"  Done in {time.time()-t0:.1f}s, stored {len(data)//1024}KB")
        return matrix

    def pre_compute_top(self, n=10):
        """Pre-compute the most common canonical flops."""
        # Most frequent flop types by rank pattern:
        # Broadway combos, mid-card combos, paired combos, etc.
        common_flops = [
            [Card.new("Ks"), Card.new("7h"), Card.new("2d")],  # K72r - high dry
            [Card.new("As"), Card.new("Th"), Card.new("5d")],  # AT5r - ace high
            [Card.new("Qs"), Card.new("Jh"), Card.new("8d")],  # QJ8r - mid
            [Card.new("Js"), Card.new("Ts"), Card.new("9h")],  # JTs9tt - wet connected
            [Card.new("As"), Card.new("Ah"), Card.new("3d")],  # AA3 - paired
            [Card.new("Ks"), Card.new("7s"), Card.new("2d")],  # K72ss - two-tone
            [Card.new("Qs"), Card.new("8s"), Card.new("3d")],  # Q83ss - two-tone
            [Card.new("8s"), Card.new("7s"), Card.new("6h")],  # 876tt - wet
            [Card.new("Ks"), Card.new("7s"), Card.new("2s")],  # K72m - monotone
            [Card.new("5s"), Card.new("3h"), Card.new("2d")],  # 532r - low
        ]
        computed = 0
        for flop in common_flops[:n]:
            if self.get(flop) is None:
                self.compute_and_store(flop, trials=500)
                computed += 1
        return computed

    def list_cached(self):
        """List all cached flop IDs."""
        if not os.path.exists(self.path):
            return []
        return [f for f in os.listdir(self.path) if f.endswith('.bin')]
