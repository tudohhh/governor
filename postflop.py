"""
Post-flop decision engine v2 — NL100 ready.
Integrates: equity tables, blockers, range advantage, geometric sizing,
range narrowing, HUD-based opponent profiles.
"""
import math
from treys import Card
from board_analyzer import analyze_flop, analyze_turn, describe_board
from equity import all_cards, remove_cards
from equity_tables import lookup_equity, find_closest_texture
from blockers import bluff_equity_boost, blocker_effect_summary, count_blocked_combos
from board_texture_advanced import range_advantage, nut_advantage, geometric_sizing_recommendation
from sizing import geometric_sizing_plan, recommend_sizing, calculate_spr
from range_narrowing import (narrow_after_flop_call, narrow_after_turn_call,
                              narrow_after_raise, estimate_villain_equity_distribution,
                              initial_range)
from opponent_hud import OpponentTracker, PROFILES


class PostflopEngine:
    """NL100-level postflop decision engine with full GTO integration."""

    def __init__(self, hero_cards, villain_range, position="IP",
                 opponent_type="standard", stack=100, pot=7.5,
                 hero_position="BTN", villain_position="BB",
                 villain_preflop_action="call"):
        self.hero_cards = hero_cards
        self.villain_range = list(villain_range) if isinstance(villain_range, set) else villain_range
        self.position = position
        self.ip = position == "IP"
        self.stack = stack
        self.pot = pot
        self.hero_position = hero_position
        self.villain_position = villain_position
        self.villain_preflop_action = villain_preflop_action

        # HUD tracker
        self.opponent = OpponentTracker(opponent_type)
        self.opponent_type = opponent_type

        # Session state
        self.street = "PREFLOP"
        self.action_history = []

    def decide_flop(self, board_cards, bet_faced=0):
        """Full flop decision with all modules integrated."""
        flop = analyze_flop(board_cards)
        tex_name, tex_cat = find_closest_texture(board_cards)

        # Equity from precomputed table (fast + deterministic)
        combo_str = self._combo_str()
        eq = lookup_equity(combo_str, tex_name, self.villain_position)
        if eq is None:
            from equity import equity_vs_range
            eq = equity_vs_range(self.hero_cards, self.villain_range, board_cards, trials=500)

        # Advanced board analysis
        range_adv = range_advantage(self.hero_position, self.villain_position, board_cards)
        nut_ratio = nut_advantage(list(initial_range(self.hero_position))[:10], self.villain_range[:10], board_cards)
        block_boost = bluff_equity_boost(self.hero_cards, self.villain_range, board_cards)
        blockers_summary = blocker_effect_summary(self.hero_cards, self.villain_range, board_cards)
        fold_eq = self.opponent.fold_to_cbet

        # Sizing recommendation
        spr = calculate_spr(self.stack, self.pot)
        streets_left = 3
        sizing_rec = recommend_sizing(flop, spr, streets_left, eq, range_adv,
                                       nut_ratio, block_boost, self.position)

        result = {
            "street": "FLOP",
            "board": [Card.int_to_pretty_str(c) for c in board_cards],
            "texture": describe_board(flop),
            "equity": eq,
            "equity_str": f"{eq*100:.0f}%",
            "range_advantage": range_adv,
            "nut_ratio": round(nut_ratio, 2),
            "blockers": blockers_summary,
            "blocker_boost": round(block_boost, 2),
            "fold_equity": fold_eq,
        }

        # Decision
        if bet_faced > 0:
            result.update(self._face_bet(bet_faced, eq, flop, sizing_rec, "FLOP"))
        else:
            result.update(self._initiate(eq, flop, sizing_rec, range_adv, block_boost))

        self.street = "FLOP"
        self.action_history.append(result.get("action", "CHECK"))
        return result

    def decide_turn(self, board_4, flop_action=None, bet_faced=0):
        """Turn decision with range narrowing."""
        if flop_action:
            self.action_history.append(flop_action)

        flop_analysis = analyze_flop(board_4[:3])
        turn_info = analyze_turn(board_4)

        # Narrow villain range after flop
        if "BET" in self.action_history:
            self.villain_range = narrow_after_flop_call(self.villain_range, board_4[:3])

        tex_name, tex_cat = find_closest_texture(board_4[:3])
        combo_str = self._combo_str()
        eq = lookup_equity(combo_str, tex_name, self.villain_position)
        if eq is None:
            from equity import equity_vs_range
            eq = equity_vs_range(self.hero_cards, self.villain_range, board_4, trials=400)

        spr = calculate_spr(self.stack, self.pot)
        range_adv = range_advantage(self.hero_position, self.villain_position, board_4[:3])
        nut_ratio = nut_advantage(list(initial_range(self.hero_position))[:10], self.villain_range[:10], board_4[:3])
        block_boost = bluff_equity_boost(self.hero_cards, self.villain_range, board_4[:3])

        sizing_rec = recommend_sizing(flop_analysis, spr, 2, eq, range_adv,
                                       nut_ratio, block_boost, self.position)

        # Turn-specific adjustments
        scare = turn_info["completes_flush"] or turn_info["straight_danger"]
        if scare:
            sizing_rec["reasoning"] += " | ATENȚIE: scare card"

        result = {
            "street": "TURN",
            "board": [flop_analysis["cards"], turn_info["turn_card"]],
            "turn_info": turn_info,
            "equity": eq,
            "equity_str": f"{eq*100:.0f}%",
            "scare_card": scare,
            "range_narrowed": len(self.villain_range),
            "blockers": blocker_effect_summary(self.hero_cards, self.villain_range, board_4[:3]),
        }

        if bet_faced > 0:
            result.update(self._face_bet(bet_faced, eq, flop_analysis, sizing_rec, "TURN"))
        else:
            result.update(self._initiate(eq, flop_analysis, sizing_rec, range_adv, block_boost))

        self.street = "TURN"
        self.action_history.append(result.get("action", "CHECK"))
        return result

    def decide_river(self, board_5, action_history=None, bet_faced=0):
        """River decision with full range narrowing."""
        if action_history:
            self.action_history = action_history

        # Narrow range progressively
        current_range = list(self.villain_range)
        if len(self.action_history) >= 1 and "BET" in self.action_history:
            current_range = narrow_after_flop_call(current_range, board_5[:3])
        if len(self.action_history) >= 2:
            current_range = narrow_after_turn_call(current_range, board_5[:4])

        eq = self._river_equity(board_5, current_range)

        # Villain equity distribution
        eq_dist = estimate_villain_equity_distribution(current_range, board_5)

        # GTO river frequencies
        spr = calculate_spr(self.stack, self.pot)
        sizing_rec = recommend_sizing(
            analyze_flop(board_5[:3]), spr, 1, eq,
            "neutral", 1.0, 1.0, self.position
        )

        # GTO bluff:value ratio based on bet size
        if sizing_rec["sizing_pct"] > 0:
            bet_size = sizing_rec["sizing_pct"]
            # Optimal bluff frequency = bet / (bet + pot), simplified
            optimal_bluff_pct = bet_size / (1 + 2 * bet_size)

            # Our decision
            if eq > 0.75:
                action = "BET"
                reason = "Value bet river — mână foarte puternică"
            elif eq > 0.60 and self.ip:
                action = "BET"
                reason = "Value bet subțire IP"
            elif eq < 0.30 and self.action_history.count("BET") >= 2:
                if self.opponent.fold_to_river_bet > 0.4:
                    action = "BET"
                    reason = "Bluff river — villain foldează des"
                else:
                    action = "CHECK"
                    reason = "Villain nu foldează — renunță la bluff"
            else:
                action = "CHECK"
                reason = "Showdown value marginal"
        else:
            action = "CHECK"
            reason = sizing_rec["reasoning"]
            bet_size = 0

        if bet_faced > 0:
            result = self._face_bet(bet_faced, eq, analyze_flop(board_5[:3]),
                                     sizing_rec, "RIVER")
        else:
            result = {
                "action": action,
                "sizing": bet_size,
                "sizing_bb": round(self.pot * bet_size, 1),
                "reasoning": reason,
            }

        result.update({
            "street": "RIVER",
            "board": [Card.int_to_pretty_str(c) for c in board_5],
            "equity": eq,
            "equity_str": f"{eq*100:.0f}%",
            "villain_distribution": eq_dist,
            "range_narrowed": len(current_range),
            "blockers": blocker_effect_summary(self.hero_cards, current_range, board_5[:3]),
        })

        self.street = "RIVER"
        return result

    # ── Internal helpers ──

    def _initiate(self, eq, flop, sizing_rec, range_adv, block_boost):
        """We're checked to — decide whether to bet."""
        action = sizing_rec["sizing_type"]
        sizing = sizing_rec["sizing_pct"]

        if sizing == 0 or action == "check":
            return {"action": "CHECK", "sizing": 0, "sizing_bb": 0,
                    "reasoning": sizing_rec["reasoning"]}

        # Override check if we should bet
        if eq < 0.30 and block_boost < 1.15 and range_adv != "hero":
            return {"action": "CHECK", "sizing": 0, "sizing_bb": 0,
                    "reasoning": "Equity prea mică, fără blocanți — check"}

        return {
            "action": "BET",
            "sizing": sizing,
            "sizing_bb": round(self.pot * sizing, 1),
            "reasoning": sizing_rec["reasoning"],
        }

    def _face_bet(self, bet_amount, eq, flop, sizing_rec, street):
        """Facing a bet — call, raise, or fold."""
        pot_odds = bet_amount / (self.pot + bet_amount * 2) if (self.pot + bet_amount * 2) > 0 else 0
        result = {"facing_bet": bet_amount, "pot_odds": f"{pot_odds*100:.0f}%"}

        # MDF: minimum defense frequency
        # If villain bets X into pot, MDF = pot / (pot + bet)
        # Simplified: we need to defend with top MDF% of our range
        mdf = self.pot / (self.pot + bet_amount) if (self.pot + bet_amount) > 0 else 1.0

        if eq > 0.80:
            result["action"] = "RAISE"
            result["sizing"] = min(3.0, bet_amount * 3 / self.pot)
            result["reasoning"] = "Mână foarte puternică — raise pentru value"
        elif eq > pot_odds * 1.4:
            result["action"] = "CALL"
            result["reasoning"] = f"Equity {eq*100:.0f}% > pot odds {pot_odds*100:.0f}% — call profitabil"
        elif eq > pot_odds and mdf > 0.5:
            result["action"] = "CALL"
            result["reasoning"] = f"MDF {mdf*100:.0f}% — trebuie să aperi range-ul"
        elif street == "RIVER" and eq > pot_odds * 0.5:
            if self.opponent.bluff_freq > 0.25:
                result["action"] = "CALL"
                result["reasoning"] = "Hero call — villain blufează des"
            else:
                result["action"] = "FOLD"
                result["reasoning"] = "Insuficientă equity, villain nu blufează"
        else:
            result["action"] = "FOLD"
            result["reasoning"] = f"Equity {eq*100:.0f}% sub pot odds {pot_odds*100:.0f}%"

        return result

    def _combo_str(self):
        """Convert hero cards to combo string like 'AKs'."""
        c1 = Card.int_to_str(self.hero_cards[0])
        c2 = Card.int_to_str(self.hero_cards[1])
        r1, s1 = c1[0], c1[1]
        r2, s2 = c2[0], c2[1]

        from app import RANKS
        i1, i2 = RANKS.index(r1), RANKS.index(r2)
        if i1 > i2:
            r1, r2 = r2, r1
            s1, s2 = s2, s1
        if r1 == r2:
            return r1 + r2
        if s1 == s2:
            return r1 + r2 + "s"
        return r1 + r2 + "o"

    def _river_equity(self, board, current_range):
        """Accurate equity on river (deterministic — no Monte Carlo needed)."""
        if len(board) < 5:
            tex_name, _ = find_closest_texture(board[:3])
            combo_str = self._combo_str()
            eq = lookup_equity(combo_str, tex_name, self.villain_position)
            if eq is not None:
                return eq

        from equity import equity_vs_range
        return equity_vs_range(self.hero_cards, current_range, board, trials=300)

    def get_opponent_summary(self):
        return self.opponent.summary()


# ── Convenience factory ──

def create_engine(hero_combo_str, villain_position="BB", hero_position="BTN",
                  opponent_type="standard", stack=100, pot=7.5):
    """
    Create engine from combo strings instead of Card ints.
    hero_combo_str: "AKs", "JJ", "T9o", etc.
    """
    from equity import _range_to_combos
    from treys import Card

    deck = all_cards()
    hands = _range_to_combos(hero_combo_str, deck)
    if not hands:
        raise ValueError(f"No valid hands for combo {hero_combo_str}")
    hero_cards = hands[0]

    villain_range = initial_range(villain_position)
    position = "IP" if hero_position in ("BTN", "CO") else "OOP"

    return PostflopEngine(
        hero_cards, villain_range, position=position,
        opponent_type=opponent_type, stack=stack, pot=pot,
        hero_position=hero_position, villain_position=villain_position,
    )
