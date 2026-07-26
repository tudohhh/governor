"""
Real Counterfactual Regret Minimization (CFR) solver for river subgames.
Implements recursive tree traversal with regret matching.
"""
import random
import math
from collections import defaultdict


class CFRNode:
    """A node in the CFR game tree."""
    def __init__(self, actions, player):
        self.actions = actions
        self.player = player  # 0 = chance, 1 = hero, 2 = villain
        self.regret_sum = {a: 0.0 for a in actions}
        self.strategy_sum = {a: 0.0 for a in actions}
        self.children = {}  # action -> CFRNode
        self.terminal_ev = None  # For terminal nodes: (hero_ev, villain_ev)
        self.is_chance = (player == 0)

    def get_strategy(self, weight=1.0):
        """Regret matching: strategy proportional to positive regrets."""
        normalizing = sum(max(0, self.regret_sum[a]) for a in self.actions)
        strategy = {}
        if normalizing > 0:
            for a in self.actions:
                strategy[a] = max(0, self.regret_sum[a]) / normalizing
        else:
            for a in self.actions:
                strategy[a] = 1.0 / len(self.actions)

        for a in self.actions:
            self.strategy_sum[a] += weight * strategy[a]
        return strategy

    def get_average_strategy(self):
        """Return time-averaged (Nash) strategy."""
        total = sum(self.strategy_sum.values())
        if total > 0:
            return {a: self.strategy_sum[a] / total for a in self.actions}
        return {a: 1.0 / len(self.actions) for a in self.actions}


class ChanceNode(CFRNode):
    """Chance node: nature deals a card. Each action = a possible outcome with probability."""
    def __init__(self, outcomes_with_probs):
        super().__init__([o[0] for o in outcomes_with_probs], player=0)
        self.probs = {o[0]: o[1] for o in outcomes_with_probs}

    def get_strategy(self, weight=1.0):
        return {a: self.probs[a] for a in self.actions}


def cfr(root, iterations=1000):
    """Run CFR algorithm starting from root node."""
    for t in range(iterations):
        _cfr_walk(root, 1.0, 1.0)
    return {a: root.get_average_strategy()[a] for a in root.actions}


def _cfr_walk(node, p0, p1):
    """Recursive CFR walk. Returns (hero_ev, villain_ev)."""
    if node.terminal_ev is not None:
        return node.terminal_ev[0], node.terminal_ev[1]

    strategy = node.get_strategy(p0 if node.player == 1 else p1)
    ev = [0.0, 0.0]

    child_evs = {}
    for action, prob in strategy.items():
        child = node.children.get(action)
        if child is None:
            continue
        if node.player == 1:
            new_p0 = p0 * prob
            new_p1 = p1
        elif node.player == 2:
            new_p0 = p0
            new_p1 = p1 * prob
        else:
            new_p0, new_p1 = p0, p1

        cev = _cfr_walk(child, new_p0, new_p1)
        child_evs[action] = cev
        ev[0] += prob * cev[0]
        ev[1] += prob * cev[1]

    # Update regrets
    for action, prob in strategy.items():
        if action not in child_evs:
            continue
        cev = child_evs[action]
        if node.player == 1:
            node.regret_sum[action] += cev[0] - ev[0]
        elif node.player == 2:
            node.regret_sum[action] += cev[1] - ev[1]

    return ev[0], ev[1]


class RiverGame:
    """
    Real river subgame solved with CFR.
    Decision tree: hero bets or checks -> villain responds -> terminal equity.
    """

    def __init__(self, pot, stack, hero_equity, ip=True):
        self.pot = float(pot)
        self.stack = float(stack)
        self.spr = stack / pot if pot > 0 else 0
        self.hero_equity = hero_equity
        self.ip = ip

    def solve(self, bet_sizes=None, iterations=1000):
        """Build and solve the game tree."""
        if bet_sizes is None:
            bet_sizes = self._default_sizes()

        # Build tree
        root = CFRNode(["check", "bet_small", "bet_medium", "bet_large"], player=1)

        for bet_name, bet_pct in bet_sizes:
            if bet_name == "check":
                child = self._build_check_branch()
            else:
                child = self._build_bet_branch(bet_pct)
            root.children[bet_name] = child

        # Solve
        result = cfr(root, iterations)
        return {
            "strategy": {k: round(v, 4) for k, v in result.items() if v > 0.01},
            "explanation": self._explain_strategy(result, bet_sizes),
            "spr": round(self.spr, 1),
            "equity": round(self.hero_equity, 3),
        }

    def _build_check_branch(self):
        """After hero checks, villain can check or bet."""
        node = CFRNode(["check", "bet"], player=2)

        # Villain checks -> showdown
        check_node = CFRNode([], player=0)
        check_node.terminal_ev = (self.pot * self.hero_equity,
                                   self.pot * (1 - self.hero_equity))
        node.children["check"] = check_node

        # Villain bets
        bet_node = CFRNode(["call", "fold"], player=1)
        bet_node.terminal_ev = None
        # Hero can call or fold vs villain's bet
        bet_pct = 0.66
        bet_amount = self.pot * bet_pct
        call_node = CFRNode([], player=0)
        call_node.terminal_ev = ((self.pot + 2 * bet_amount) * self.hero_equity - bet_amount,
                                  (self.pot + 2 * bet_amount) * (1 - self.hero_equity) - bet_amount)
        fold_node = CFRNode([], player=0)
        fold_node.terminal_ev = (0, self.pot)
        bet_node.children["call"] = call_node
        bet_node.children["fold"] = fold_node
        node.children["bet"] = bet_node

        return node

    def _build_bet_branch(self, bet_pct):
        """Hero bets, villain responds."""
        bet_amount = self.pot * bet_pct
        actual_bet = min(bet_amount, self.stack)

        node = CFRNode(["fold", "call", "raise"], player=2)

        # Fold
        fn = CFRNode([], player=0)
        fn.terminal_ev = (self.pot, 0)
        node.children["fold"] = fn

        # Call
        cn = CFRNode([], player=0)
        cn.terminal_ev = ((self.pot + 2 * actual_bet) * self.hero_equity - actual_bet,
                           (self.pot + 2 * actual_bet) * (1 - self.hero_equity) - actual_bet)
        node.children["call"] = cn

        # Raise (simplified: all-in)
        rn = CFRNode(["call_raise", "fold_raise"], player=1)
        call_rn = CFRNode([], player=0)
        all_in = self.stack
        call_rn.terminal_ev = ((self.pot + 2 * all_in) * self.hero_equity - all_in,
                                (self.pot + 2 * all_in) * (1 - self.hero_equity) - all_in)
        fold_rn = CFRNode([], player=0)
        fold_rn.terminal_ev = (0, self.pot + actual_bet)
        rn.children["call_raise"] = call_rn
        rn.children["fold_raise"] = fold_rn
        node.children["raise"] = rn

        return node

    def _default_sizes(self):
        if self.spr < 1:
            return [("check", 0), ("bet_all_in", self.spr)]
        elif self.spr < 3:
            return [("check", 0), ("bet_small", 0.40), ("bet_large", self.spr)]
        else:
            return [("check", 0), ("bet_small", 0.33), ("bet_medium", 0.66), ("bet_large", 1.0)]

    def _explain_strategy(self, strategy, bet_sizes):
        """Human-readable explanation of the mixed strategy."""
        check_pct = strategy.get("check", 0)
        parts = []

        if check_pct > 0.7:
            parts.append(f"check {check_pct*100:.0f}% — preferă showdown")
        elif check_pct > 0.3:
            parts.append(f"mix echilibrat (check {check_pct*100:.0f}%)")

        for name, pct in strategy.items():
            if name == "check":
                continue
            if pct > 0.15:
                size_name = name.replace("bet_", "")
                parts.append(f"bet {size_name} {pct*100:.0f}%")

        if self.hero_equity > 0.70:
            parts.append("— value-heavy")
        elif self.hero_equity < 0.35:
            parts.append("— cu bluff-uri")

        return " | ".join(parts) if parts else "strategie mixtă"
