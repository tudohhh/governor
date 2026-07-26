"""
Post-flop decision engine. Integrates board analysis and equity
to produce GTO-based decisions for flop, turn, and river.
"""
import random
from treys import Card
from board_analyzer import analyze_flop, analyze_turn, cbet_sizing_recommendation, describe_board
from equity import equity_vs_range, eq_to_string, VILLAIN_CONTINUE_VS_CBET, all_cards, remove_cards, cards_from_str


class PostflopEngine:
    """
    Makes post-flop decisions based on board texture, equity, position, and opponent type.
    """

    def __init__(self, hero_cards, villain_range, position="IP", opponent_type="standard",
                 stack=100, pot=7.5):
        """
        hero_cards: list of treys card ints (2 cards)
        villain_range: list of range strings (e.g., ["AA","KK","AKs","AQo"])
        position: "IP" (in position) or "OOP" (out of position)
        opponent_type: "standard", "nit", "lag", "fish", "maniac"
        stack: effective stack in BB
        pot: current pot in BB
        """
        self.hero_cards = hero_cards
        self.villain_range = villain_range
        self.position = position
        self.ip = position == "IP"
        self.opponent_type = opponent_type
        self.stack = stack
        self.pot = pot

    def decide_flop(self, board_cards, bet_faced=0):
        """
        Decide action on the flop.
        bet_faced: size of bet we're facing (0 if checked to us)

        Returns dict: {action, sizing, reasoning, equity}
        """
        flop = analyze_flop(board_cards)
        eq = equity_vs_range(self.hero_cards, self.villain_range, board_cards)

        result = {
            "street": "FLOP",
            "board": flop["cards"],
            "texture": describe_board(flop),
            "equity": eq,
            "equity_str": eq_to_string(eq),
        }

        # Opponent adaptation factors
        opp_factors = self._opponent_modifiers()

        if bet_faced > 0:
            # Facing a bet - decide call/raise/fold
            return self._face_bet_flop(bet_faced, eq, flop, opp_factors, result)
        else:
            # Checked to us - decide bet or check
            return self._initiate_flop(eq, flop, opp_factors, result)

    def decide_turn(self, board_4, flop_action="BET", turn_bet_faced=0):
        """
        Decide action on the turn.
        """
        flop_analysis = analyze_flop(board_4[:3])
        turn_info = analyze_turn(board_4)
        eq = equity_vs_range(self.hero_cards, self.villain_range, board_4)

        result = {
            "street": "TURN",
            "board": [flop_analysis["cards"], turn_info["turn_card"]],
            "turn_info": turn_info,
            "equity": eq,
            "equity_str": eq_to_string(eq),
        }

        opp_factors = self._opponent_modifiers()

        # Scare cards: did turn complete draws?
        scare_card = turn_info["completes_flush"] or turn_info["straight_danger"]

        if turn_bet_faced > 0:
            return self._face_bet_turn(turn_bet_faced, eq, scare_card, opp_factors, result)
        else:
            return self._initiate_turn(eq, scare_card, flop_action, opp_factors, result)

    def decide_river(self, board_5, action_history, bet_faced=0):
        """
        Decide action on the river.
        action_history: list of action strings from previous streets
        """
        eq = equity_vs_range(self.hero_cards, self.villain_range, board_5, trials=300)

        result = {
            "street": "RIVER",
            "board": [Card.int_to_pretty_str(c) for c in board_5],
            "equity": eq,
            "equity_str": eq_to_string(eq),
        }

        opp_factors = self._opponent_modifiers()

        if bet_faced > 0:
            return self._face_bet_river(bet_faced, eq, opp_factors, result)
        else:
            return self._initiate_river(eq, action_history, opp_factors, result)

    # ── Internal decision logic ──

    def _initiate_flop(self, eq, flop, opp, result):
        """We're first to act or checked to."""
        rec = cbet_sizing_recommendation(flop, self.ip, eq)[1]  # sizing
        action, sizing, reason = cbet_sizing_recommendation(flop, self.ip, eq)

        # Opponent adaptation
        if opp["cbet_freq_mod"] < 0 and action == "BET":
            # Vs nit, c-bet more often
            if eq > 0.35:
                action = "BET"
                sizing = 0.33
                reason += " (vs nit: c-bet frecvent)"

        if opp["cbet_freq_mod"] > 0 and eq < 0.55:
            # Vs station/fish, don't bluff
            if eq < 0.40:
                action = "CHECK"
                sizing = 0
                reason += " (vs fish: nu blufa)"

        result["action"] = action
        result["sizing"] = sizing
        result["sizing_bb"] = round(self.pot * sizing, 1)
        result["reasoning"] = reason
        return result

    def _face_bet_flop(self, bet, eq, flop, opp, result):
        """Facing a bet on flop."""
        pot_odds = bet / (self.pot + bet * 2) if (self.pot + bet * 2) > 0 else 0

        if eq > pot_odds * 1.5:
            if eq > 0.70:
                result["action"] = "RAISE"
                result["sizing"] = 3.0  # 3x the bet
                result["reasoning"] = "Equity mare peste pot odds — raise pentru value"
            else:
                result["action"] = "CALL"
                result["sizing"] = 0
                result["reasoning"] = "Equity suficientă pentru call"
        elif eq > pot_odds * 0.8 and opp["fold_to_cbet"] > 0.5:
            # Bluff raise vs high fold-to-cbet
            result["action"] = "RAISE"
            result["sizing"] = 2.5
            result["reasoning"] = "Adversarul foldează des la c-bet — bluff raise"
        elif eq > pot_odds:
            result["action"] = "CALL"
            result["sizing"] = 0
            result["reasoning"] = "Call marginal, equity > pot odds"
        else:
            result["action"] = "FOLD"
            result["sizing"] = 0
            result["reasoning"] = f"Equity {eq_to_string(eq)} sub pot odds {pot_odds*100:.0f}%"

        result["facing_bet"] = bet
        return result

    def _initiate_turn(self, eq, scare_card, flop_action, opp, result):
        """Initiating on turn (checked to us)."""
        if scare_card and eq < 0.50:
            result["action"] = "CHECK"
            result["sizing"] = 0
            result["reasoning"] = "Scare card — mai bine check"
        elif eq > 0.65:
            result["action"] = "BET"
            result["sizing"] = 0.70
            result["reasoning"] = "Value bet turn, equity mare"
        elif eq > 0.50 and flop_action == "BET":
            result["action"] = "BET"
            result["sizing"] = 0.55
            result["reasoning"] = "Continuă barierele, equity decentă"
        elif eq < 0.35:
            result["action"] = "CHECK"
            result["sizing"] = 0
            result["reasoning"] = "Renunță — equity prea mică pentru al doilea barrel"
        else:
            result["action"] = "CHECK"
            result["sizing"] = 0
            result["reasoning"] = "Check pentru pot control"

        return result

    def _face_bet_turn(self, bet, eq, scare_card, opp, result):
        """Facing a bet on turn."""
        pot_odds = bet / (self.pot + bet * 2) if (self.pot + bet * 2) > 0 else 0

        if eq > 0.75:
            result["action"] = "RAISE"
            result["sizing"] = 3.0
            result["reasoning"] = "Mână foarte puternică — raise value"
        elif eq > pot_odds * 1.3:
            result["action"] = "CALL"
            result["reasoning"] = "Equity suficientă pentru call pe turn"
        elif scare_card and eq > 0.35:
            result["action"] = "CALL"
            result["reasoning"] = "Scare card — adversarul poate blufa, call light"
        else:
            result["action"] = "FOLD"
            result["reasoning"] = "Equity insuficientă"

        result["facing_bet"] = bet
        return result

    def _initiate_river(self, eq, history, opp, result):
        """Initiating on river."""
        barrels = history.count("BET")

        if eq > 0.75:
            result["action"] = "BET"
            result["sizing"] = 0.80 if barrels >= 2 else 0.65
            result["reasoning"] = "Value bet river — mână foarte puternică"
        elif eq > 0.60 and barrels >= 1:
            result["action"] = "BET"
            result["sizing"] = 0.50
            result["reasoning"] = "Value bet subțire"
        elif eq < 0.30 and barrels >= 1:
            # Potential bluff spot
            if opp["fold_to_river_bet"] > 0.4:
                result["action"] = "BET"
                result["sizing"] = 0.75
                result["reasoning"] = "Bluff river — adversarul foldează des"
            else:
                result["action"] = "CHECK"
                result["reasoning"] = "Renunță — adversarul nu foldează"
        else:
            result["action"] = "CHECK"
            result["reasoning"] = "Check behind — showdown value marginal"

        return result

    def _face_bet_river(self, bet, eq, opp, result):
        """Facing a bet on river."""
        pot_odds = bet / (self.pot + bet * 2) if (self.pot + bet * 2) > 0 else 0

        if eq > 0.85:
            result["action"] = "RAISE"
            result["sizing"] = 3.0
            result["reasoning"] = "Nuts sau aproape — raise all-in"
        elif eq > pot_odds * 1.2:
            result["action"] = "CALL"
            result["reasoning"] = "Call profitabil"
        elif eq > pot_odds * 0.6 and opp["bluff_freq"] > 0.25:
            result["action"] = "CALL"
            result["reasoning"] = "Hero call — adversarul blufează des"
        else:
            result["action"] = "FOLD"
            result["reasoning"] = "Fold — nu ai equity să chemi"

        result["facing_bet"] = bet
        return result

    def _opponent_modifiers(self):
        """Return opponent-specific strategy modifiers."""
        profiles = {
            "standard": {"cbet_freq_mod": 0, "fold_to_cbet": 0.50, "fold_to_river_bet": 0.55, "bluff_freq": 0.20},
            "nit": {"cbet_freq_mod": -1, "fold_to_cbet": 0.70, "fold_to_river_bet": 0.75, "bluff_freq": 0.10},
            "lag": {"cbet_freq_mod": 1, "fold_to_cbet": 0.40, "fold_to_river_bet": 0.45, "bluff_freq": 0.35},
            "maniac": {"cbet_freq_mod": 2, "fold_to_cbet": 0.25, "fold_to_river_bet": 0.30, "bluff_freq": 0.50},
            "fish": {"cbet_freq_mod": 2, "fold_to_cbet": 0.30, "fold_to_river_bet": 0.35, "bluff_freq": 0.15},
        }
        return profiles.get(self.opponent_type, profiles["standard"])


def generate_drill_scenario(hero_position="BTN", villain_position="BB", opponent_type="standard"):
    """
    Generate a random postflop drill scenario.
    Returns (hero_cards, villain_range_strs, board_cards, position, pot, stack).
    """
    from treys import Card
    deck = all_cards()
    random.shuffle(deck)

    hero = (deck[0], deck[1])
    dead = list(hero)
    remaining = remove_cards(deck, dead)

    # Deal a flop
    board = remaining[:3]
    dead.extend(board)
    remaining = remove_cards(remaining, board)

    # Villain range based on position
    from app import GTO_RANGES
    bb_defend = set()
    for vpos in ["UTG", "HJ", "CO", "BTN", "SB"]:
        k = f"vs_{vpos}"
        if k in GTO_RANGES.get("VS_RFI", {}).get("3bet", {}):
            bb_defend.update(GTO_RANGES["VS_RFI"]["3bet"].get(k, set()))
        if k in GTO_RANGES.get("VS_RFI", {}).get("call", {}):
            bb_defend.update(GTO_RANGES["VS_RFI"]["call"].get(k, set()))

    villain_range = list(bb_defend) if bb_defend else ["AA", "KK", "QQ", "JJ", "AK", "AQ"]

    hero_position = "IP"  # BTN is IP vs BB
    pot = 7.5
    stack = 100

    return hero, villain_range, board, hero_position, opponent_type, pot, stack
