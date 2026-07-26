"""
Maximum-power PioSolver: real EHS abstraction, CFR+ with discounting,
real equity computation per board, 16 buckets × 1000 iterations.
"""
import json, math, random, time
from collections import defaultdict
from treys import Card, Evaluator

evaluator = Evaluator()
RANKS_STR = "AKQJT98765432"
SUITS_LIST = ["s", "h", "d", "c"]

def _all_cards():
    return [Card.new(r+s) for r in RANKS_STR for s in SUITS_LIST]

def _combo_to_hands(combo_str):
    hands = []
    if len(combo_str) == 2:
        r = combo_str[0]
        for i, s1 in enumerate(SUITS_LIST):
            for s2 in SUITS_LIST[i+1:]:
                hands.append((Card.new(r+s1), Card.new(r+s2)))
    elif combo_str[2] == 's':
        for s in SUITS_LIST:
            hands.append((Card.new(combo_str[0]+s), Card.new(combo_str[1]+s)))
    else:
        for s1 in SUITS_LIST:
            for s2 in SUITS_LIST:
                if s1 != s2:
                    hands.append((Card.new(combo_str[0]+s1), Card.new(combo_str[1]+s2)))
    return hands

def real_equity(hero_combo, villain_combos, board_cards, trials=100):
    """Real Monte Carlo equity of a specific combo vs a range on a board."""
    h_hands = _combo_to_hands(hero_combo)
    v_hands = []
    for vc in villain_combos:
        v_hands.extend(_combo_to_hands(vc))
    if not h_hands or not v_hands:
        return 0.5

    dead_base = set(board_cards)
    deck = [c for c in _all_cards() if c not in dead_base]
    wins = valid = 0

    for _ in range(trials):
        hp = random.choice(h_hands)
        if hp[0] in dead_base or hp[1] in dead_base:
            continue
        d = dead_base | {hp[0], hp[1]}
        avail = [(a,b) for a,b in v_hands if a not in d and b not in d]
        if not avail:
            continue
        vp = random.choice(avail)
        d.update([vp[0], vp[1]])
        rem = [c for c in deck if c not in d]
        needed = 5 - len(board_cards)
        if needed > 0 and len(rem) >= needed:
            runout = random.sample(rem, needed)
        elif needed <= 0:
            runout = []
        else:
            continue
        fb = list(board_cards) + runout
        hs = evaluator.evaluate(list(hp), fb)
        vs = evaluator.evaluate(list(vp), fb)
        if hs < vs: wins += 1
        elif hs == vs: wins += 0.5
        valid += 1
    return wins / max(1, valid)


# ── EHS hand abstraction ──
PREFLOP_EHS = {}

def _init_ehs():
    global PREFLOP_EHS
    if PREFLOP_EHS:
        return
    for r in "AKQJ": PREFLOP_EHS[r+r] = {"A":0.85,"K":0.82,"Q":0.80,"J":0.77}[r]
    for r in "T987": PREFLOP_EHS[r+r] = 0.72
    for r in "65432": PREFLOP_EHS[r+r] = 0.68
    base = {("A","K"):0.67,("A","Q"):0.66,("A","J"):0.65,("A","T"):0.64,
            ("K","Q"):0.63,("K","J"):0.62,("K","T"):0.60,("Q","J"):0.60}
    for (r1,r2),e in base.items():
        PREFLOP_EHS[r1+r2+"s"] = e
        PREFLOP_EHS[r1+r2+"o"] = e - 0.03
    for i,r1 in enumerate(RANKS_STR):
        for j,r2 in enumerate(RANKS_STR):
            if i > j:
                sk, ok = r1+r2+"s", r1+r2+"o"
                if sk not in PREFLOP_EHS:
                    PREFLOP_EHS[sk] = max(0.40, 0.62 - (i-j)*0.03)
                if ok not in PREFLOP_EHS:
                    PREFLOP_EHS[ok] = max(0.37, PREFLOP_EHS.get(sk,0.55)-0.04)

def bucketize(combos, n=16):
    """Assign combos to buckets by EHS percentile. 0=best."""
    _init_ehs()
    items = [(c, PREFLOP_EHS.get(c,0.50)) for c in combos]
    items.sort(key=lambda x:-x[1])
    result = {}
    per = max(1, len(items) // n)
    for rank,(combo,ehs) in enumerate(items):
        result[combo] = min(n-1, rank // per)
    return result


# ── Board-specific equity matrix ──
class EquityMatrix:
    def __init__(self, hero_combos, villain_combos, board_cards, n=16):
        self.n = n
        self.hb = bucketize(hero_combos, n)
        self.vb = bucketize(villain_combos, n)
        self.board = list(board_cards)
        self._m = [[0.5]*n for _ in range(n)]
        self._compute(hero_combos, villain_combos)

    def _compute(self, hc, vc):
        h_by = defaultdict(list)
        v_by = defaultdict(list)
        for c in hc: h_by[self.hb.get(c,0)].append(c)
        for c in vc: v_by[self.vb.get(c,0)].append(c)
        for hbi in range(self.n):
            hl = h_by.get(hbi,[])
            if not hl: continue
            for vbi in range(self.n):
                vl = v_by.get(vbi,[])
                if not vl: continue
                total = count = 0
                for _ in range(min(30, len(hl)*len(vl))):
                    total += real_equity(random.choice(hl), [random.choice(vl)], self.board, 20)
                    count += 1
                if count: self._m[hbi][vbi] = round(total/count, 4)

    def lookup(self, hb, vb):
        return self._m[hb][vb]


# ── Game tree ──
class Node:
    __slots__ = ('player','actions','pot','stack','street','depth',
                 'regret','strat_sum','kids','term')
    def __init__(self, p, acts, pot, stk, street, depth):
        self.player = p; self.actions = acts; self.pot = pot
        self.stack = stk; self.street = street; self.depth = depth
        self.regret = {a:0.0 for a in acts}
        self.strat_sum = {a:0.0 for a in acts}
        self.kids = {}; self.term = None

SIZES = {'turn':[(0.33,'s'),(0.66,'m'),(1.0,'l')],
         'river':[(0.33,'s'),(0.66,'m'),(1.0,'l')]}

def build_tree(pot, stack, eq, street='turn', player=1, bet_faced=0, depth=0):
    if depth > 10:
        n = Node(player,['call'],pot,stack,street,depth)
        n.term = lambda h,v: (pot*eq.lookup(h,v), pot*(1-eq.lookup(h,v)))
        return n

    acts = []
    if bet_faced > 0:
        acts = ['fold','call']
        if stack > bet_faced*2.2 and depth < 8:
            acts.append('raise')
    else:
        acts = ['check'] + [f'b{s[1]}' for s in SIZES.get(street,[])]

    n = Node(player, acts, pot, stack, street, depth)
    for a in acts:
        if a == 'fold':
            k = Node(0,[],pot,stack,street,depth+1)
            k.term = (lambda p,pt: lambda h,v: ((0.0,pt) if p==1 else (pt,0.0)))(player,pot)
            n.kids[a] = k
        elif a == 'call':
            np = pot if bet_faced==0 else pot+bet_faced
            if street == 'river':
                k = Node(0,[],np,stack,street,depth+1)
                k.term = lambda h,v,fp=np: (fp*eq.lookup(h,v), fp*(1-eq.lookup(h,v)))
                n.kids[a] = k
            else:
                n.kids[a] = build_tree(np, stack, eq, 'river', 1, 0, depth+1)
        elif a == 'raise':
            rs = max(bet_faced*2.5, pot*0.5)
            rs = min(rs, stack)
            n.kids[a] = build_tree(pot+rs, stack-rs, eq, street, 3-player, rs, depth+1)
        elif a == 'check':
            if street == 'river':
                k = Node(0,[],pot,stack,street,depth+1)
                k.term = lambda h,v,p=pot: (p*eq.lookup(h,v), p*(1-eq.lookup(h,v)))
                n.kids[a] = k
            else:
                n.kids[a] = build_tree(pot, stack, eq, 'river', 2 if player==1 else 1, 0, depth+1)
        elif a.startswith('b'):
            pct = {'s':0.33,'m':0.66,'l':1.0}[a[-1]]
            bet = min(pot*pct, stack)
            n.kids[a] = build_tree(pot+bet, stack-bet, eq, street, 3-player, bet, depth+1)
    return n


# ── CFR+ solver ──
def solve_cfr(root, nb, iters=1000):
    t0 = time.time()
    gamma = 0.9

    for t in range(iters):
        if t > 0 and t % 150 == 0:
            _discount(root, gamma)
        w = t + 1
        for hb in range(nb):
            for vb in range(nb):
                _walk(root, hb, vb, w)

    return _extract(root), time.time() - t0

def _walk(n, hb, vb, w):
    if n.term:
        return n.term(hb, vb)
    s = _strat(n)
    ev = [0.0, 0.0]; cev = {}
    for a, p in s.items():
        if a not in n.kids: continue
        e = _walk(n.kids[a], hb, vb, w*p)
        cev[a] = e
        ev[0] += p*e[0]; ev[1] += p*e[1]
    pi = n.player - 1
    for a in n.actions:
        if a not in cev: continue
        n.regret[a] = max(0.0, n.regret[a] + cev[a][pi] - ev[pi])
        n.strat_sum[a] += w * s.get(a, 0)
    return ev[0], ev[1]

def _strat(n):
    t = sum(n.regret.values())
    if t > 0: return {a: n.regret[a]/t for a in n.actions}
    return {a: 1.0/len(n.actions) for a in n.actions}

def _discount(n, g):
    for a in n.actions: n.regret[a] *= g
    for k in n.kids.values():
        if not k.term: _discount(k, g)

def _extract(n, out=None, path=""):
    if out is None: out = {}
    t = sum(n.strat_sum.values())
    if t > 0.001:
        s = {}
        for a in n.actions:
            v = n.strat_sum[a]/t
            if v > 0.005: s[a] = round(v, 4)
        if s:
            out[path or "root"] = {'player':'OOP' if n.player==1 else 'IP',
                                   'street':n.street,'pot':round(n.pot,1),'strategy':s}
    for a, k in n.kids.items():
        if not k.term:
            _extract(k, out, f"{path}/{a}" if path else a)
    return out


# ── API ──
class PioSolver:
    def __init__(self): self.nb = 16

    def solve(self, hero_c, vill_c, board, pot=10, stack=100, pos="IP", iters=1000):
        eq = EquityMatrix(hero_c, vill_c, board, self.nb)
        root = build_tree(pot, stack, eq)
        strats, elapsed = solve_cfr(root, self.nb, iters)

        hb_set = set(bucketize(hero_c, self.nb).values())
        vb_set = set(bucketize(vill_c, self.nb).values())
        ev_total = count = 0.0
        for hb in hb_set:
            for vb in vb_set:
                e = _walk(root, hb, vb, 1.0)
                ev_total += e[1] if pos == "IP" else e[0]
                count += 1
        hero_ev = ev_total / max(1, count)

        acts = {}
        for a, f in strats.get('root',{}).get('strategy',{}).items():
            label = a.replace('b','BET ').replace('check','CHECK').upper()
            for k,v in [('S','33%'),('M','66%'),('L','100%')]: label=label.replace(k,v)
            acts[label]=round(f*100,1)

        return {'actions':acts,'hero_ev':round(hero_ev,2),
                'ev_pct':round(hero_ev/pot*100,1),'time':round(elapsed,2),
                'iters':iters,'buckets':self.nb}
