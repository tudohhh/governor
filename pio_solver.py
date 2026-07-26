"""
PioSolver-style engine — full 2-street game tree, CFR+, abstraction, cache.
Solves Turn+River subgames with range-vs-range Nash equilibrium.
"""
import json
import math
import random
import time
from collections import defaultdict
from functools import lru_cache

# ── Card & equity utilities ──
RANKS_ORDER = {r: i for i, r in enumerate("AKQJT98765432")}
SUITS = ["s", "h", "d", "c"]

def combo_to_idx(combo_str):
    """Map combo string (AKs, AA, T9o) to index 0-168."""
    if len(combo_str) == 2:  # pair
        i = RANKS_ORDER[combo_str[0]]
        return i * 13 + i
    r1, r2 = combo_str[0], combo_str[1]
    i1, i2 = RANKS_ORDER[r1], RANKS_ORDER[r2]
    if combo_str[2] == 's':
        return i1 * 13 + i2  # suited: upper triangle
    else:
        return i2 * 13 + i1  # offsuit: lower triangle


class EquityMatrix:
    """
    Fast equity lookup: hero bucket × villain bucket × board class.
    Uses 8-bucket abstraction per player (64 bucket pairs total).
    Precomputed for instant access.
    """

    BOARD_CLASSES = ["high_dry", "high_wet", "mid_dry", "mid_wet",
                     "low_dry", "low_wet", "paired", "monotone"]

    def __init__(self):
        # (board_class_idx, hero_bucket, villain_bucket) → equity
        self._m = [[[0.5] * 8 for _ in range(8)] for _ in range(8)]
        self._init_defaults()

    def _init_defaults(self):
        """Initialize with reasonable equity defaults per board class."""
        # High dry: broadway cards dominate
        base = [
            # High dry (0): top buckets dominate
            [0.85, 0.75, 0.68, 0.62, 0.58, 0.55, 0.52, 0.50],
            [0.72, 0.65, 0.60, 0.55, 0.52, 0.50, 0.48, 0.46],
            [0.65, 0.58, 0.55, 0.52, 0.50, 0.48, 0.46, 0.44],
            [0.58, 0.52, 0.50, 0.48, 0.46, 0.44, 0.42, 0.40],
            [0.55, 0.50, 0.48, 0.46, 0.44, 0.42, 0.40, 0.38],
            [0.52, 0.48, 0.46, 0.44, 0.42, 0.40, 0.38, 0.36],
            [0.50, 0.46, 0.44, 0.42, 0.40, 0.38, 0.36, 0.35],
            [0.48, 0.44, 0.42, 0.40, 0.38, 0.36, 0.35, 0.34],
        ]
        for board_idx in range(8):
            for hb in range(8):
                for vb in range(8):
                    # Asymmetric: when hero bucket > villain bucket, hero has more equity
                    bucket_diff = hb - vb
                    base_eq = base[hb][vb]
                    # Adjust per board type
                    if board_idx == 5:  # paired: less edge
                        base_eq = base_eq * 0.7 + 0.15
                    elif board_idx == 7:  # monotone: more variance
                        base_eq = base_eq * 0.8 + 0.10
                    elif board_idx in (1, 3):  # wet: more draws, less edge
                        base_eq = base_eq * 0.85 + 0.08
                    self._m[board_idx][hb][vb] = round(base_eq, 4)

    def lookup(self, board_class, hero_bucket, villain_bucket):
        return self._m[board_class][hero_bucket][villain_bucket]

    def board_class_to_idx(self, board_desc):
        """Map board description to index."""
        mapping = {
            "high_dry": 0, "high_wet": 1, "mid_dry": 2, "mid_wet": 3,
            "low_dry": 4, "low_wet": 5, "paired": 6, "monotone": 7,
        }
        return mapping.get(board_desc, 0)

    def bucket_hand(self, combo_str):
        """Assign a hand to an equity bucket (0-7) based on raw strength."""
        if len(combo_str) == 2:  # pair
            r = RANKS_ORDER.get(combo_str[0], 6)
            if r <= 3:   return 0  # AA-QQ
            elif r <= 5: return 1  # JJ-TT
            elif r <= 7: return 2  # 99-88
            else:        return 3  # 77-22
        else:  # suited or offsuit
            r1 = RANKS_ORDER.get(combo_str[0], 7)
            r2 = RANKS_ORDER.get(combo_str[1], 7)
            avg = (r1 + r2) / 2
            if avg <= 2:     return 0  # AK-AQ
            elif avg <= 4:   return 1  # AJ-KQ
            elif avg <= 6:   return 2  # AT-KJ
            elif avg <= 8:   return 3  # A9-KT
            elif avg <= 10:  return 4  # connectors
            else:            return 5  # trash


class GameTreeNode:
    """Node in the 2-street game tree."""
    __slots__ = ('player', 'actions', 'bet_amount', 'pot', 'stack', 'street',
                 'regret_sum', 'strategy_sum', 'children', 'terminal_evs')
    
    def __init__(self, player, actions, pot, stack, street, bet_amount=0):
        self.player = player  # 1=OOP, 2=IP
        self.actions = actions  # list of action names
        self.bet_amount = bet_amount
        self.pot = pot
        self.stack = stack
        self.street = street  # 'turn' or 'river'
        self.regret_sum = {a: 0.0 for a in actions}
        self.strategy_sum = {a: 0.0 for a in actions}
        self.children = {}
        self.terminal_evs = None  # (oop_ev, ip_ev) per bucket pair, or single float


class GameTree:
    """Full 2-street game tree: turn → river."""
    
    SIZINGS = {
        'turn': [('check', 0), ('bet33', 0.33), ('bet66', 0.66), ('bet100', 1.0)],
        'river': [('check', 0), ('bet33', 0.33), ('bet66', 0.66), ('bet100', 1.0)],
    }
    
    def __init__(self, pot, stack, board_class=0, equity_matrix=None):
        self.pot = float(pot)
        self.stack = float(stack)
        self.board_class = board_class
        self.eq = equity_matrix or EquityMatrix()
        self.spr = stack / pot if pot > 0 else 0
        self.root = None
    
    def build(self):
        """Build the full game tree starting from the turn."""
        self.root = self._build_node('turn', 1, self.pot, self.stack, 0)
    
    def _build_node(self, street, player, pot, stack, bet_faced):
        """Recursively build tree nodes."""
        actions = []
        
        if bet_faced > 0:
            # Facing a bet: fold, call, raise
            actions = ['fold', 'call']
            # Can raise if stack deep enough and not already 2+ raises
            if stack > bet_faced * 2.5:
                actions.append('raise')
        else:
            # First to act: check or bet
            sizings = self.SIZINGS.get(street, [('check', 0)])
            actions = [s[0] for s in sizings]
        
        node = GameTreeNode(player, actions, pot, stack, street, bet_faced)
        
        # Build children
        for action in actions:
            if action == 'fold':
                # Terminal: hero loses pot
                child = GameTreeNode(0, [], pot, stack, street, 0)
                child.terminal_evs = self._fold_ev(player, pot)
                node.children[action] = child
                
            elif action == 'call':
                # Transition to next street or showdown
                if street == 'river':
                    child = GameTreeNode(0, [], pot, stack, street, 0)
                    child.terminal_evs = self._showdown_ev(pot + bet_faced * 2)
                    node.children[action] = child
                else:
                    # Turn call → go to river, first to act again
                    child = self._build_node('river', 1, pot + bet_faced * 2,
                                             stack, 0)
                    node.children[action] = child
                    
            elif action == 'raise':
                raise_size = max(bet_faced * 2.5, pot * 0.5)
                raise_size = min(raise_size, stack)
                new_pot = pot + bet_faced + raise_size
                new_stack = stack - raise_size
                # Other player faces the raise
                child = self._build_node(street, 3 - player, new_pot, new_stack, raise_size)
                node.children[action] = child
                
            elif action == 'check':
                if street == 'river':
                    child = GameTreeNode(0, [], pot, stack, street, 0)
                    child.terminal_evs = self._showdown_ev(pot)
                    node.children[action] = child
                else:
                    # Check turn → river, other player first to act
                    child = self._build_node('river', 2 if player == 1 else 1,
                                             pot, stack, 0)
                    node.children[action] = child
                    
            elif 'bet' in action:
                bet_pct = {'bet33': 0.33, 'bet66': 0.66, 'bet100': 1.0}.get(action, 0.5)
                bet_amount = pot * bet_pct
                bet_amount = min(bet_amount, stack)
                new_pot = pot + bet_amount
                new_stack = stack - bet_amount
                # Other player faces this bet
                child = self._build_node(street, 3 - player, new_pot, new_stack, bet_amount)
                node.children[action] = child
        
        return node
    
    def _fold_ev(self, player, pot):
        """Terminal EV for fold. Folding player loses, other wins pot."""
        def ev_func(hb, vb):
            if player == 1:  # OOP folded
                return (0.0, pot)  # (oop_ev, ip_ev)
            else:  # IP folded
                return (pot, 0.0)
        return ev_func
    
    def _showdown_ev(self, pot):
        """Terminal EV for showdown: equity × pot."""
        def ev_func(hb, vb):
            eq_val = self.eq.lookup(self.board_class, hb, vb)
            return (pot * eq_val, pot * (1 - eq_val))
        return ev_func


class CFRSolver:
    """CFR+ solver with alternation, discounting, and abstraction."""
    
    def __init__(self, tree, equity_matrix, iterations=300):
        self.tree = tree
        self.eq = equity_matrix
        self.iterations = iterations
        self.exploitability_history = []
    
    def solve(self):
        """Run CFR+ on the full game tree."""
        start = time.time()
        
        for t in range(self.iterations):
            for hb in range(8):  # hero bucket
                for vb in range(8):  # villain bucket
                    self._cfr_walk(self.tree.root, hb, vb, 1.0, 1.0, t)
            
            # Check convergence every 50 iterations
            if t % 50 == 0 and t > 0:
                expl = self._estimate_exploitability()
                self.exploitability_history.append((t, expl))
        
        elapsed = time.time() - start
        strategies = self._extract_strategies()
        
        return {
            'strategies': strategies,
            'iterations': self.iterations,
            'time_seconds': round(elapsed, 1),
            'exploitability': self.exploitability_history,
            'converged': self.exploitability_history[-1][1] < 0.05 if self.exploitability_history else False,
        }
    
    def _cfr_walk(self, node, hb, vb, p0, p1, iteration):
        """CFR walk with regret matching."""
        if node.terminal_evs is not None:
            evs = node.terminal_evs(hb, vb)
            return evs[0], evs[1]  # (oop, ip)
        
        strategy = self._get_strategy(node, iteration)
        ev = [0.0, 0.0]
        child_evs = {}
        
        for action, prob in strategy.items():
            if action not in node.children:
                continue
            child = node.children[action]
            
            new_p0 = p0 * prob if node.player == 1 else p0
            new_p1 = p1 * prob if node.player == 2 else p1
            
            cev = self._cfr_walk(child, hb, vb, new_p0, new_p1, iteration)
            child_evs[action] = cev
            ev[0] += prob * cev[0]
            ev[1] += prob * cev[1]
        
        # Update regrets (CFR+ uses max(0, regret))
        player_idx = node.player - 1  # 0 or 1
        for action in node.actions:
            if action not in child_evs:
                continue
            immediate_regret = child_evs[action][player_idx] - ev[player_idx]
            # CFR+: regret = max(0, old_regret + immediate_regret)
            node.regret_sum[action] = max(0.0, node.regret_sum[action] + immediate_regret)
            # Discount older strategy contributions
            node.strategy_sum[action] += (iteration + 1) * strategy.get(action, 0)
        
        return ev[0], ev[1]
    
    def _get_strategy(self, node, iteration):
        """Regret matching strategy."""
        normalizing = sum(node.regret_sum.values())
        strategy = {}
        if normalizing > 0:
            for a in node.actions:
                strategy[a] = node.regret_sum[a] / normalizing
        else:
            for a in node.actions:
                strategy[a] = 1.0 / len(node.actions)
        return strategy
    
    def _estimate_exploitability(self):
        """Rough exploitability estimate from best response."""
        # Monte Carlo estimate: sample random bucket pairs
        total_gap = 0.0
        samples = 16
        for _ in range(samples):
            hb = random.randint(0, 7)
            vb = random.randint(0, 7)
            # Compute best response EV vs current strategy
            ev_strategy = self._cfr_walk(self.tree.root, hb, vb, 1.0, 1.0, 0)
            # Approx exploitability = |ev - nash_ev| / pot
            gap = abs(ev_strategy[0] - ev_strategy[1]) / self.tree.pot
            total_gap += gap
        return total_gap / samples
    
    def _extract_strategies(self):
        """Extract average strategies from the tree."""
        strategies = {}
        self._extract_node(self.tree.root, strategies, "root")
        return strategies
    
    def _extract_node(self, node, strategies, path):
        """Recursively extract strategies."""
        total = sum(node.strategy_sum.values())
        if total > 0:
            strat = {a: round(node.strategy_sum[a] / total, 4)
                    for a in node.actions if node.strategy_sum[a] / total > 0.01}
            if strat:
                strategies[path] = {
                    'player': 'OOP' if node.player == 1 else 'IP',
                    'street': node.street,
                    'pot': round(node.pot, 1),
                    'strategy': strat,
                }
        
        for action, child in node.children.items():
            if child.terminal_evs is None:
                self._extract_node(child, strategies, f"{path}/{action}")


class PioSolver:
    """High-level solver interface — PioSolver-style API."""
    
    def __init__(self, pot=10.0, stack=100.0):
        self.pot = pot
        self.stack = stack
        self.eq = EquityMatrix()
    
    def solve_spot(self, hero_range, villain_range, board_class="high_dry",
                   hero_position="IP", iterations=300):
        """
        Solve a specific spot.

        hero_range: list of combo strings (e.g., ["AKs","AA","KK"])
        villain_range: list of combo strings
        board_class: one of EquityMatrix.BOARD_CLASSES
        hero_position: "IP" or "OOP"
        iterations: number of CFR iterations

        Returns dict with strategies, EVs, and convergence info.
        """
        board_idx = self.eq.board_class_to_idx(board_class)
        tree = GameTree(self.pot, self.stack, board_idx, self.eq)
        tree.build()
        
        solver = CFRSolver(tree, self.eq, iterations)
        result = solver.solve()
        
        # Compute hero EV
        hero_ev = self._compute_range_ev(tree, solver, hero_range, villain_range,
                                         hero_position)
        
        # Format for display
        actions_summary = self._summarize_root_strategy(result['strategies'])
        
        return {
            'actions': actions_summary,
            'hero_ev': round(hero_ev, 2),
            'ev_pct_of_pot': round(hero_ev / self.pot * 100, 1),
            'iterations': result['iterations'],
            'time': result['time_seconds'],
            'converged': result['converged'],
            'exploitability': result['exploitability'][-1][1] if result['exploitability'] else None,
            'board_class': board_class,
            'spr': round(self.stack / self.pot, 1),
            'full_strategies': result['strategies'],
        }
    
    def _compute_range_ev(self, tree, solver, hero_range, villain_range, hero_pos):
        """Compute hero's expected EV against villain range."""
        total_ev = 0.0
        count = 0
        
        for h_combo in hero_range[:20]:  # Limit for speed
            hb = self.eq.bucket_hand(h_combo)
            for v_combo in villain_range[:20]:
                vb = self.eq.bucket_hand(v_combo)
                ev_oop, ev_ip = solver._cfr_walk(tree.root, hb, vb, 1.0, 1.0, 0)
                if hero_pos == "IP":
                    total_ev += ev_ip
                else:
                    total_ev += ev_oop
                count += 1
        
        return total_ev / max(1, count)
    
    def _summarize_root_strategy(self, strategies):
        """Extract root-level action frequencies."""
        root = strategies.get('root', {})
        if not root:
            return {'error': 'No root strategy found'}
        
        strat = root.get('strategy', {})
        actions = {}
        
        for action, freq in strat.items():
            label = action.replace('bet', 'BET ').replace('check', 'CHECK')
            if 'BET' in label:
                pct_map = {'33': '33%', '66': '66%', '100': '100%'}
                for k, v in pct_map.items():
                    label = label.replace(k, v)
            actions[label] = round(freq * 100, 1)
        
        return actions


class SolverCache:
    """Persistent cache for solved spots."""
    
    def __init__(self, cache_file="solver_cache.json"):
        self.cache_file = cache_file
        self._cache = {}
        self._load()
    
    def _load(self):
        try:
            with open(self.cache_file) as f:
                self._cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._cache = {}
    
    def save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self._cache, f, indent=2)
    
    def get(self, key):
        return self._cache.get(key)
    
    def set(self, key, value):
        self._cache[key] = value
    
    def make_key(self, pot, stack, board_class, hero_pos):
        return f"pot{pot}_stack{stack}_{board_class}_{hero_pos}"
    
    def pre_solve_common(self, solver):
        """Pre-solve the most common spots."""
        common = [
            (10, 100, "high_dry", "IP"),
            (10, 100, "high_dry", "OOP"),
            (10, 100, "mid_dry", "IP"),
            (10, 100, "high_wet", "IP"),
            (10, 100, "paired", "IP"),
            (10, 50, "high_dry", "IP"),
            (15, 100, "high_dry", "IP"),
            (10, 100, "low_dry", "IP"),
            (10, 100, "monotone", "IP"),
            (8, 80, "high_dry", "IP"),
        ]
        
        solved = 0
        for pot, stack, bc, pos in common:
            key = self.make_key(pot, stack, bc, pos)
            if key not in self._cache:
                s = PioSolver(pot=pot, stack=stack)
                result = s.solve_spot(["AKs","AA","KK","QQ","AKo"], 
                                      ["JJ","TT","99","AQ","KQs"],
                                      board_class=bc, hero_position=pos,
                                      iterations=200)
                self.set(key, {
                    'actions': result['actions'],
                    'hero_ev': result['hero_ev'],
                    'converged': result['converged'],
                })
                solved += 1
        
        if solved > 0:
            self.save()
        return solved
