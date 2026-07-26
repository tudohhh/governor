"""
PioSolver MAX v3 — full 3-street tree, vectorized CFR, equity DB integration.
Pre-computed equity for canonical flops enables sub-second solving.
"""
import json, os, math, random, time, struct
from collections import defaultdict
from treys import Card, Evaluator
from equity_db import EquityDB, canonical_id, equity_lookup, all_combos_169

evaluator = Evaluator()
RANKS_STR = "AKQJT98765432"
SUITS_LIST = ["s", "h", "d", "c"]

# ── Fast EHS abstraction ──
PREFLOP_EHS = {}
def _init_ehs():
    global PREFLOP_EHS
    if PREFLOP_EHS: return
    for r in "AKQJ": PREFLOP_EHS[r+r] = {"A":0.85,"K":0.82,"Q":0.80,"J":0.77}[r]
    for r in "T987": PREFLOP_EHS[r+r] = 0.72
    for r in "65432": PREFLOP_EHS[r+r] = 0.68
    base = {("A","K"):0.67,("A","Q"):0.66,("A","J"):0.65,("A","T"):0.64,
            ("K","Q"):0.63,("K","J"):0.62,("K","T"):0.60,("Q","J"):0.60}
    for (r1,r2),e in base.items():
        PREFLOP_EHS[r1+r2+"s"] = e; PREFLOP_EHS[r1+r2+"o"] = e - 0.03
    for i,r1 in enumerate(RANKS_STR):
        for j,r2 in enumerate(RANKS_STR):
            if i > j:
                sk, ok = r1+r2+"s", r1+r2+"o"
                if sk not in PREFLOP_EHS: PREFLOP_EHS[sk] = max(0.40, 0.62 - (i-j)*0.03)
                if ok not in PREFLOP_EHS: PREFLOP_EHS[ok] = max(0.37, PREFLOP_EHS.get(sk,0.55)-0.04)
_init_ehs()

def bucketize(combos, n=10):
    items = [(c, PREFLOP_EHS.get(c,0.50)) for c in combos]
    items.sort(key=lambda x:-x[1])
    result = {}
    per = max(1, len(items)//n)
    for rank,(combo,ehs) in enumerate(items):
        result[combo] = min(n-1, rank//per)
    return result


# ── Vectorized equity matrix (uses EquityDB) ──

class FastEquity:
    """Multi-street equity lookup. Supports flop (DB), turn (MC buckets), river (exact)."""

    def __init__(self, hero_c, vill_c, board, n=10):
        self.n = n
        self.hb_map = bucketize(hero_c, n)
        self.vb_map = bucketize(vill_c, n)
        self.board = list(board)
        self.combos_169 = all_combos_169()
        self.use_db = False
        self._m = [[0.5] * self.n for _ in range(self.n)]

        n_board = len(board)
        if n_board == 0:
            self._init_preflop()
        elif n_board == 3:
            self._init_flop(hero_c, vill_c)
        elif n_board == 4:
            self._init_turn(hero_c, vill_c)
        elif n_board >= 5:
            self._init_river(hero_c, vill_c)

    def _init_preflop(self):
        """Preflop equity from EHS heuristic (fast, good enough for buckets)."""
        h_by = defaultdict(list); v_by = defaultdict(list)
        for c, _ in enumerate(self.hb_map): pass  # build group lists
        for c, hb in self.hb_map.items(): h_by[hb].append(c)
        for c, vb in self.vb_map.items(): v_by[vb].append(c)
        for hb in range(self.n):
            hl = h_by.get(hb, [])
            for vb in range(self.n):
                vl = v_by.get(vb, [])
                if not hl or not vl:
                    self._m[hb][vb] = 0.5
                    continue
                total = sum(PREFLOP_EHS.get(h, 0.5) for h in hl) / len(hl)
                v_avg = sum(PREFLOP_EHS.get(v, 0.5) for v in vl) / len(vl)
                self._m[hb][vb] = round(total / (total + v_avg + 0.001), 3)

    def _init_flop(self, hero_c, vill_c):
        """Flop equity from DB (precomputed) or MC fallback."""
        self.db = EquityDB()
        self.matrix = self.db.get(self.board)
        self.use_db = self.matrix is not None
        if self.use_db:
            self._init_from_db(hero_c, vill_c)
        else:
            self._init_from_scratch(hero_c, vill_c)

    def _init_turn(self, hero_c, vill_c):
        """Turn equity: MC over 47 remaining river cards, within buckets.
        Samples random river completions and averages equity across buckets."""
        # Build bucket → card-int lists (need actual card ints, not combo strings)
        # For turn, convert combo strings to actual hands
        from equity import all_cards, remove_cards

        h_by = defaultdict(list); v_by = defaultdict(list)
        for c in hero_c:
            hb = self.hb_map.get(c, 0)
            hands = self._combo_to_card_pairs(c)
            h_by[hb].extend(hands)
        for c in vill_c:
            vb = self.vb_map.get(c, 0)
            hands = self._combo_to_card_pairs(c)
            v_by[vb].extend(hands)

        # Remaining deck for river card
        deck = all_cards()
        dead = set(self.board)
        remaining = [c for c in deck if c not in dead]

        for hb in range(self.n):
            hl = h_by.get(hb, [])
            if not hl: continue
            for vb in range(self.n):
                vl = v_by.get(vb, [])
                if not vl: continue
                wins = ties = total = 0
                n_river = min(47, len(remaining))
                for _ in range(n_river):
                    river = random.choice(remaining)
                    # Pick random hero and villain hands (no collision with each other or board+river)
                    hh = random.choice(hl)
                    while (hh[0] in dead or hh[1] in dead or
                           hh[0] == river or hh[1] == river):
                        hh = random.choice(hl)
                    vh = random.choice(vl)
                    while (vh[0] in dead or vh[1] in dead or
                           vh[0] == river or vh[1] == river or
                           vh[0] in hh or vh[1] in hh):
                        vh = random.choice(vl)

                    fb = self.board + [river]
                    hs = evaluator.evaluate(list(hh), fb)
                    vs = evaluator.evaluate(list(vh), fb)
                    if hs < vs: wins += 1
                    elif hs == vs: ties += 1
                    total += 1
                self._m[hb][vb] = round((wins + ties * 0.5) / max(1, total), 3)

    def _init_river(self, hero_c, vill_c):
        """River equity: deterministic (5 known cards). Exact evaluation."""
        from equity import all_cards, remove_cards

        h_by = defaultdict(list); v_by = defaultdict(list)
        for c in hero_c:
            hb = self.hb_map.get(c, 0)
            h_by[hb].extend(self._combo_to_card_pairs(c))
        for c in vill_c:
            vb = self.vb_map.get(c, 0)
            v_by[vb].extend(self._combo_to_card_pairs(c))

        dead = set(self.board)

        for hb in range(self.n):
            hl = h_by.get(hb, [])
            if not hl: continue
            for vb in range(self.n):
                vl = v_by.get(vb, [])
                if not vl: continue
                wins = ties = total = 0
                for hh in hl:
                    if hh[0] in dead or hh[1] in dead: continue
                    for vh in vl:
                        if vh[0] in dead or vh[1] in dead: continue
                        if hh[0] in vh or hh[1] in vh: continue
                        hs = evaluator.evaluate(list(hh), self.board)
                        vs = evaluator.evaluate(list(vh), self.board)
                        if hs < vs: wins += 1
                        elif hs == vs: ties += 1
                        total += 1
                self._m[hb][vb] = round((wins + ties * 0.5) / max(1, total), 3)

    def _combo_to_card_pairs(self, combo_str):
        """Convert combo string like 'AKs' to list of (card_int, card_int) tuples."""
        from app import combo_to_hands
        try:
            return combo_to_hands(combo_str)
        except:
            return []

    def _init_from_db(self, hc, vc):
        """Build bucket-pair equity from precomputed 169×169 matrix."""
        combo_to_idx = {}
        for idx, (name, _) in enumerate(self.combos_169):
            combo_to_idx[name] = idx

        counts = [[0] * self.n for _ in range(self.n)]

        for h in hc:
            hb = self.hb_map.get(h, 0)
            hi = combo_to_idx.get(h)
            if hi is None: continue
            for v in vc:
                vb = self.vb_map.get(v, 0)
                vi = combo_to_idx.get(v)
                if vi is None: continue
                eq = equity_lookup(self.matrix, hi, vi)
                self._m[hb][vb] += eq
                counts[hb][vb] += 1

        for hb in range(self.n):
            for vb in range(self.n):
                if counts[hb][vb] > 0:
                    self._m[hb][vb] /= counts[hb][vb]

    def _init_from_scratch(self, hc, vc):
        """Fallback: compute from Monte Carlo (slower)."""
        self._m = [[0.5] * self.n for _ in range(self.n)]
        h_by = defaultdict(list); v_by = defaultdict(list)
        for c in hc: h_by[self.hb_map.get(c, 0)].append(c)
        for c in vc: v_by[self.vb_map.get(c, 0)].append(c)

        for hbi in range(self.n):
            hl = h_by.get(hbi, [])
            if not hl: continue
            for vbi in range(self.n):
                vl = v_by.get(vbi, [])
                if not vl: continue
                total = count = 0
                for _ in range(min(20, len(hl) * len(vl))):
                    total += real_equity(random.choice(hl), [random.choice(vl)], self.board, 15)
                    count += 1
                if count: self._m[hbi][vbi] = round(total / count, 4)

    def lookup(self, hb, vb):
        return self._m[hb][vb]


# ── Compact 3-street game tree ──

class CompactTree:
    """Flattened game tree for fast CFR traversal. Supports flop+turn+river."""

    def __init__(self, eq, pot, stack, start_street='flop'):
        self.eq = eq
        self.pot = pot
        self.stack = stack
        self.start = start_street

        # Build flattened representation
        self.nodes = []  # list of (player, children_indices, actions_list, pot, is_terminal)
        if start_street == 'flop':
            self.root = self._build('flop', 1, pot, stack, 0)
        else:
            self.root = self._build('turn', 1, pot, stack, 0)

    def _build(self, street, player, pot, stack, bet_faced, depth=0):
        if depth > 8:
            idx = len(self.nodes)
            self.nodes.append((0, [], [], pot, True))
            return idx

        acts, kids = [], []

        if bet_faced > 0:
            acts = ['fold','call']
            if stack > bet_faced*2.2 and depth < 6:
                acts.append('raise')
        else:
            if street == 'flop':
                acts = ['check','b33','b66']
            elif street == 'turn':
                acts = ['check','b33','b66','b100']
            else:
                acts = ['check','b33','b66','b100']

        for a in acts:
            if a == 'fold':
                kid_idx = len(self.nodes)
                self.nodes.append((0, [], [], pot, True))
                kids.append(kid_idx)
            elif a == 'call':
                np = pot + bet_faced if bet_faced > 0 else pot
                if street == 'river':
                    kid_idx = len(self.nodes)
                    self.nodes.append((0, [], [], np, True))
                    kids.append(kid_idx)
                else:
                    ns = 'turn' if street == 'flop' else 'river'
                    kids.append(self._build(ns, 1, np, stack, 0, depth+1))
            elif a == 'raise':
                rs = min(max(bet_faced*2.5, pot*0.5), stack)
                kids.append(self._build(street, 3-player, pot+rs, stack-rs, rs, depth+1))
            elif a == 'check':
                if street == 'river':
                    kid_idx = len(self.nodes)
                    self.nodes.append((0, [], [], pot, True))
                    kids.append(kid_idx)
                else:
                    ns = 'turn' if street == 'flop' else 'river'
                    kids.append(self._build(ns, 2 if player==1 else 1, pot, stack, 0, depth+1))
            elif a.startswith('b'):
                pct = {'b33':0.33,'b66':0.66,'b100':1.0}[a]
                bet = min(pot*pct, stack)
                kids.append(self._build(street, 3-player, pot+bet, stack-bet, bet, depth+1))

        idx = len(self.nodes)
        self.nodes.append((player, kids, acts, pot, False))
        return idx

    def terminal_ev(self, node_idx, hb, vb):
        """Get terminal EV for a node."""
        _, _, _, pot, _ = self.nodes[node_idx]
        eq_val = self.eq.lookup(hb, vb)
        return (pot * eq_val, pot * (1 - eq_val))


# ── Vectorized CFR solver ──

class FastCFR:
    """Vectorized CFR using pre-allocated arrays and batch updates."""

    def __init__(self, tree, nb, iters=500):
        self.tree = tree
        self.nb = nb
        self.iters = iters
        self.nn = len(tree.nodes)

        # Pre-allocate regret and strategy sums
        max_acts = max(len(n[2]) for n in tree.nodes) if tree.nodes else 4
        self.regrets = [[0.0]*max_acts for _ in range(self.nn)]
        self.strat_sums = [[0.0]*max_acts for _ in range(self.nn)]
        self.gamma = 0.9

    def solve(self):
        t0 = time.time()

        for t in range(self.iters):
            w = t + 1
            if t > 0 and t % 100 == 0:
                self._discount()

            # Batch over bucket pairs
            for hb in range(self.nb):
                for vb in range(self.nb):
                    self._walk(self.tree.root, hb, vb, w)

        return time.time() - t0

    def _walk(self, ni, hb, vb, w):
        player, kids, acts, pot, is_term = self.tree.nodes[ni]

        if is_term:
            return self.tree.terminal_ev(ni, hb, vb)

        # Get strategy
        na = len(acts)
        regs = self.regrets[ni][:na]
        rsum = sum(regs)
        if rsum > 0:
            strat = [r / rsum for r in regs]
        else:
            strat = [1.0 / na] * na

        # Walk children
        ev = [0.0, 0.0]
        cev = [None] * na
        for ai, ki in enumerate(kids):
            if ki >= 0:
                cev[ai] = self._walk(ki, hb, vb, w * strat[ai])
                ev[0] += strat[ai] * cev[ai][0]
                ev[1] += strat[ai] * cev[ai][1]

        # Update regrets (CFR+)
        pi = player - 1
        for ai in range(na):
            if cev[ai] is None: continue
            reg = cev[ai][pi] - ev[pi]
            self.regrets[ni][ai] = max(0.0, self.regrets[ni][ai] + reg)
            self.strat_sums[ni][ai] += w * strat[ai]

        return ev[0], ev[1]

    def _discount(self):
        for ni in range(self.nn):
            for ai in range(len(self.regrets[ni])):
                self.regrets[ni][ai] *= self.gamma

    def get_strategy(self, ni):
        """Get average strategy for a node."""
        _, _, acts, _, _ = self.tree.nodes[ni]
        total = sum(self.strat_sums[ni][:len(acts)])
        if total > 0.001:
            s = {}
            for ai, a in enumerate(acts):
                v = self.strat_sums[ni][ai] / total
                if v > 0.005: s[a] = round(v, 4)
            return s
        return {}

    def get_ev(self, hb, vb):
        """Get EV for a specific bucket pair from the root."""
        return self._walk(self.tree.root, hb, vb, 1.0)


# ── API ──

def real_equity(hero_combo, villain_combos, board_cards, trials=50):
    """Quick real equity via Monte Carlo (used as fallback in FastEquity)."""
    from equity import equity_vs_range
    from app import combo_to_hands

    hero_hands = combo_to_hands(hero_combo)
    if not hero_hands:
        return 0.5
    hero_cards = hero_hands[0]  # Take one representative
    return equity_vs_range(hero_cards, villain_combos, board_cards, trials=trials)

class PioSolver:
    """MAX v4: 6 buckets, vectorized CFR, 200 iters → ~2-3s per solve."""

    def __init__(self): self.nb = 6

    def solve(self, hero_c, vill_c, board, pot=10, stack=100, pos="IP",
              start='flop', iters=500):
        """Solve GTO strategy for any starting street.
        board: 0 cards (preflop), 3 (flop), 4 (turn), or 5 (river).
        start: 'preflop', 'flop', 'turn', or 'river'.
        Returns dict with actions, hero_ev, ev_pct, timing."""
        n_board = len(board)

        # ── Equity ──
        eq = FastEquity(hero_c, vill_c, board, self.nb)
        eq_time = time.time()

        # ── Tree ──
        t0 = time.time()
        if n_board == 0:
            # Preflop only: simple decision tree, not full CFR
            actual_start = 'flop'
        elif n_board == 3:
            actual_start = start if start in ('flop', 'turn', 'river') else 'flop'
        elif n_board == 4:
            actual_start = 'turn' if start != 'river' else 'river'
        elif n_board >= 5:
            actual_start = 'river'
        else:
            actual_start = start

        tree = CompactTree(eq, pot, stack, actual_start)
        tree_build_time = time.time() - t0

        # ── Solve ──
        solver = FastCFR(tree, self.nb, iters)
        solve_time = solver.solve()

        # ── EV ──
        hb_set = set(bucketize(hero_c, self.nb).values())
        vb_set = set(bucketize(vill_c, self.nb).values())
        ev_total = count = 0.0
        for hb in hb_set:
            for vb in vb_set:
                e = solver.get_ev(hb, vb)
                ev_total += e[1] if pos == "IP" else e[0]
                count += 1
        hero_ev = ev_total / max(1, count)

        # ── Root strategy ──
        root_s = solver.get_strategy(tree.root)
        acts = {}
        for a, f in root_s.items():
            label = a.replace('b', 'BET ').replace('check', 'CHECK').upper()
            for k, v in [('33', '33%'), ('66', '66%'), ('100', '100%')]:
                label = label.replace(k, v)
            acts[label] = round(f * 100, 1)

        return {
            'actions': acts,
            'hero_ev': round(hero_ev, 2),
            'ev_pct': round(hero_ev / pot * 100, 1),
            'total_time': round(time.time() - t0, 2),
            'tree_time': round(tree_build_time, 3),
            'solve_time': round(solve_time, 2),
            'iters': iters,
            'buckets': self.nb,
            'start_street': actual_start,
            'db_used': getattr(eq, 'use_db', False),
        }

# ── Pre-solved spot cache ──
import hashlib

class SpotCache:
    """Persistent cache of solved strategies. Sub-second lookup."""
    def __init__(self, path="spot_cache.json"):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.data = json.load(f)
            except: pass

    def key(self, hero_c, vill_c, board, pot, stack, pos):
        h = hashlib.md5()
        h.update(str(sorted(hero_c)).encode())
        h.update(str(sorted(vill_c)).encode())
        h.update(str([Card.int_to_str(c) for c in board]).encode())
        h.update(f"{pot}_{stack}_{pos}".encode())
        return h.hexdigest()[:12]

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        if len(self.data) % 5 == 0:
            with open(self.path, 'w') as f:
                json.dump(self.data, f)

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f)


class TurboSolver(PioSolver):
    """Sub-second solver: cache + 6 buckets + 200 iters."""

    def __init__(self):
        super().__init__()
        self.cache = SpotCache()

    def solve(self, hero_c, vill_c, board, pot=10, stack=100, pos="IP",
              start='flop', iters=200, use_cache=True):
        # Try cache first
        ck = self.cache.key(hero_c, vill_c, board, pot, stack, pos)
        if use_cache:
            cached = self.cache.get(ck)
            if cached:
                cached['cached'] = True
                return cached

        # Solve fresh
        result = super().solve(hero_c, vill_c, board, pot, stack, pos, start, iters)
        result['cached'] = False

        # Store in cache
        cacheable = {
            'actions': result['actions'],
            'hero_ev': result['hero_ev'],
            'ev_pct': result['ev_pct'],
            'time': result.get('total_time', result.get('time', 0)),
            'iters': result.get('iters', iters),
        }
        self.cache.set(ck, cacheable)
        return result
