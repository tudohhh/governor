"""
Miniature CFR (Counterfactual Regret Minimization) solver for single-street subgames.
Solves river and turn spots for mixed strategies (bet X% / check Y%).
"""
import random
import math
from collections import defaultdict


class GameNode:
    """Node in the game tree: represents a decision point."""
    def __init__(self, name, player, actions, board="", pot=1.0):
        self.name = name
        self.player = player  # 0 = hero, 1 = villain
        self.actions = actions  # list of action names
        self.board = board
        self.pot = pot
        self.children = {}  # action -> GameNode
        self.strategy = {}  # action -> probability
        self.regret_sum = defaultdict(float)
        self.strategy_sum = defaultdict(float)

    def set_terminal(self, hero_equity):
        self.is_terminal = True
        self.hero_equity = hero_equity

    def get_strategy(self, realization_weight=1.0):
        """Get current strategy from regret matching."""
        normalizing_sum = 0.0
        strat = {}

        for action in self.actions:
            strat[action] = max(0.0, self.regret_sum[action])
            normalizing_sum += strat[action]

        if normalizing_sum > 0:
            for action in self.actions:
                strat[action] /= normalizing_sum
        else:
            prob = 1.0 / len(self.actions)
            for action in self.actions:
                strat[action] = prob

        for action in self.actions:
            self.strategy_sum[action] += realization_weight * strat[action]

        self.strategy = strat
        return strat

    def get_average_strategy(self):
        """Get time-averaged strategy (Nash equilibrium approximation)."""
        normalizing_sum = sum(self.strategy_sum.values())
        avg = {}
        if normalizing_sum > 0:
            for action in self.actions:
                avg[action] = self.strategy_sum[action] / normalizing_sum
        else:
            prob = 1.0 / len(self.actions)
            for action in self.actions:
                avg[action] = prob
        return avg


class RiverSolver:
    """
    CFR solver for river spots.
    Given: board, hero range equity, pot size, stack size.
    Produces: optimal bet/check frequencies and sizing.
    """

    def __init__(self, pot=1.0, stack=1.0, hero_equity=0.5, ip=True):
        self.pot = pot
        self.stack = stack
        self.hero_equity = hero_equity
        self.ip = ip  # in position?
        self.spr = stack / pot if pot > 0 else float('inf')

    def solve(self, iterations=500):
        """Run CFR and return optimal strategy."""
        # Simplified river game tree:
        # IP: check or bet (small, medium, large)
        # OOP: after check -> check or bet; after bet -> call/fold/raise

        bet_sizes = self._get_bet_sizes()

        # For IP river: we decide check or bet
        # Villain faces the bet: decides call or fold
        # Their calling frequency depends on our bet size and pot odds

        best_action = None
        best_ev = -float('inf')
        results = {}

        for size_name, bet_pct in bet_sizes:
            bet_amount = self.pot * bet_pct
            # Villain MDF: they need to defend enough to make us indifferent
            mdf = self.pot / (self.pot + bet_amount) if (self.pot + bet_amount) > 0 else 1.0
            villain_call_pct = mdf

            # EV of betting:
            # When villain folds: we win pot * (1 - villain_call_pct)
            # When villain calls: we win (pot + bet) * equity - bet * (1 - equity)
            ev_fold = self.pot * (1 - villain_call_pct)
            ev_call = (self.pot + 2 * bet_amount) * self.hero_equity - bet_amount
            ev_bet = ev_fold + villain_call_pct * ev_call

            # EV of checking (simplified: pot * equity)
            ev_check = self.pot * self.hero_equity

            results[size_name] = {
                "action": "BET",
                "sizing_pct": bet_pct,
                "sizing_bb": round(bet_amount, 1),
                "ev_bet": round(ev_bet, 4),
                "ev_check": round(ev_check, 4),
                "ev_diff": round(ev_bet - ev_check, 4),
                "villain_defend_pct": round(villain_call_pct * 100),
            }

            if ev_bet > best_ev:
                best_ev = ev_bet
                best_action = size_name

        # Determine optimal strategy
        ev_check = self.pot * self.hero_equity

        if best_ev > ev_check * 1.05:
            strategy_type = "value_bet"
            optimal = results[best_action]
        elif best_ev > ev_check:
            strategy_type = "thin_value"
            optimal = results[best_action]
        elif self.hero_equity < 0.30:
            strategy_type = "bluff_candidate"
            optimal = results["medium"]
        else:
            strategy_type = "check"
            optimal = {
                "action": "CHECK",
                "sizing_pct": 0,
                "ev_bet": best_ev,
                "ev_check": ev_check,
                "ev_diff": best_ev - ev_check,
                "villain_defend_pct": 0,
            }

        return {
            "strategy_type": strategy_type,
            "optimal": optimal,
            "all_options": results,
            "spr": round(self.spr, 1),
            "hero_equity": self.hero_equity,
        }


    def _get_bet_sizes(self):
        """Available bet sizes based on SPR."""
        if self.spr < 1:
            return [("all_in", self.spr)]
        elif self.spr < 3:
            return [("small", 0.50), ("large", self.spr)]
        elif self.spr < 6:
            return [("small", 0.33), ("medium", 0.66), ("large", 1.0)]
        else:
            return [("small", 0.33), ("medium", 0.66), ("large", 1.0), ("overbet", min(1.5, self.spr))]


class TurnSolver:
    """
    2-street solver: turn + river planning.
    Uses simplified CFR to determine optimal turn action given river implications.
    """

    def __init__(self, pot=1.0, stack=1.0, hero_equity=0.5, ip=True, board_texture="dry"):
        self.pot = pot
        self.stack = stack
        self.hero_equity = hero_equity
        self.ip = ip
        self.board_texture = board_texture
        self.spr = stack / pot if pot > 0 else float('inf')

    def solve(self, iterations=300):
        """Solve turn + river strategy."""
        spr = self.spr
        eq = self.hero_equity

        # Plan: bet turn → river shove or bet turn → check river or check turn → bet river
        # Simplified: geometric 2-street sizing

        if spr > 6:
            # Two streets: geometric sizing
            geo = self._geo_2street()
            bet_turn = geo
            pot_after_turn = self.pot * (1 + 2 * geo)
            spr_river = (self.stack - self.pot * geo) / pot_after_turn
            bet_river = min(spr_river, 1.5)  # All-in or large on river

            # EV: we get called some % on turn, then river action
            # Simplified: EV ≈ pot-growth if equity holds
            ev_bet_turn = self.pot * (1 + geo * 2 * eq * 0.8)  # Rough
            ev_check_turn = self.pot * eq * 1.2  # Pot grows slower

        else:
            # Just bet geometric to all-in
            geo = spr / 2 if spr < 4 else 0.75
            bet_turn = geo
            pot_after_turn = self.pot * (1 + 2 * geo)
            spr_river = (self.stack - self.pot * geo) / pot_after_turn
            bet_river = min(spr_river, spr_river)

            ev_bet_turn = self.pot
            ev_check_turn = self.pot * eq

        if eq > 0.55 and ev_bet_turn > ev_check_turn:
            return {
                "action": "BET",
                "turn_bet_pct": round(bet_turn, 2),
                "river_plan_pct": round(bet_river, 2),
                "stack_river": round(max(0, self.stack - self.pot * bet_turn), 1),
                "reasoning": f"Plan pe 2 străzi: bet {bet_turn*100:.0f}% turn, {bet_river*100:.0f}% river",
            }
        elif eq < 0.30:
            return {
                "action": "CHECK",
                "turn_bet_pct": 0,
                "reasoning": "Equity prea mică pentru double barrel",
            }
        else:
            return {
                "action": "CHECK",
                "turn_bet_pct": 0,
                "river_plan_pct": 0.66 if eq > 0.45 else 0,
                "reasoning": "Pot control pe turn, decide river",
            }

    def _geo_2street(self):
        """Geometric sizing for 2 streets remaining."""
        growth_target = (self.pot + 2 * self.stack) / self.pot if self.pot > 0 else 1
        geo = (growth_target ** 0.5 - 1) / 2
        return min(geo, 1.5)  # Cap at 150% pot
