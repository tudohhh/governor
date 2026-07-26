"""
Hand history parser for PokerStars and GGPoker formats.
Extracts actions, positions, bet sizes, and outcomes.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class PlayerAction:
    player: str
    action: str  # fold, call, raise, check, bet, all-in
    amount: float = 0.0


@dataclass
class PokerHand:
    hand_id: str = ""
    game_type: str = ""
    stakes: str = ""
    date: str = ""
    table_name: str = ""
    hero_name: str = ""
    hero_cards: List[str] = field(default_factory=list)
    players: Dict[str, float] = field(default_factory=dict)  # name -> stack
    positions: Dict[str, str] = field(default_factory=dict)  # name -> position
    actions_preflop: List[PlayerAction] = field(default_factory=list)
    actions_flop: List[PlayerAction] = field(default_factory=list)
    actions_turn: List[PlayerAction] = field(default_factory=list)
    actions_river: List[PlayerAction] = field(default_factory=list)
    board: List[str] = field(default_factory=list)
    pot: float = 0.0
    result: str = ""


def parse_pokerstars(hand_text: str) -> Optional[PokerHand]:
    """Parse a single PokerStars hand history."""
    hand = PokerHand()
    lines = hand_text.strip().split("\n")
    current_street = "preflop"
    hero_name = ""

    for line in lines:
        line = line.strip()

        # Hand ID
        m = re.search(r"PokerStars Hand #(\d+)", line)
        if m:
            hand.hand_id = m.group(1)

        # Stakes
        m = re.search(r"\((\$?\d+\.?\d*/\$?\d+\.?\d*)\)", line)
        if m:
            hand.stakes = m.group(1)

        # Table
        m = re.search(r"Table '([^']+)'", line)
        if m:
            hand.table_name = m.group(1)

        # Hero cards
        m = re.search(r"Dealt to (\w+)\s+\[([^\]]+)\]", line)
        if m:
            hand.hero_name = m.group(1)
            hand.hero_cards = [c.strip() for c in m.group(2).split()]

        # Seats
        m = re.search(r"Seat (\d+):\s*(\w+)\s*\(([\d.]+)", line)
        if m:
            seat, name, stack = int(m.group(1)), m.group(2), float(m.group(3))
            hand.players[name] = stack
            # Approximate position from seat
            if seat <= 3:
                hand.positions[name] = ["UTG","HJ","CO","BTN","SB","BB"][min(seat - 1, 5)]
            else:
                hand.positions[name] = "BTN" if seat == 6 else "SB"

        # Board
        m = re.search(r"Board:\s*\[([^\]]+)\]", line)
        if m:
            hand.board = [c.strip() for c in m.group(1).split()]

        # Street detection
        if "*** FLOP ***" in line:
            current_street = "flop"
        elif "*** TURN ***" in line:
            current_street = "turn"
        elif "*** RIVER ***" in line:
            current_street = "river"

        # Actions
        action_match = re.search(r"(\w+):\s*(folds|checks|calls|bets|raises|all-in)\s*\$?([\d.]+)?", line)
        if action_match:
            name = action_match.group(1)
            action = action_match.group(2)
            amount = float(action_match.group(3)) if action_match.group(3) else 0

            pa = PlayerAction(name, action, amount)
            street_map = {
                "preflop": hand.actions_preflop,
                "flop": hand.actions_flop,
                "turn": hand.actions_turn,
                "river": hand.actions_river,
            }
            street_map.get(current_street, hand.actions_preflop).append(pa)

        # Pot
        m = re.search(r"Pot:\s*\$?([\d.]+)", line)
        if m:
            hand.pot = float(m.group(1))

        # Result
        m = re.search(r"(won|collected)\s*\$?([\d.]+)", line, re.IGNORECASE)
        if m and hand.hero_name and hand.hero_name in line:
            hand.result = f"Won ${m.group(2)}"

    return hand if hand.hand_id else None


def analyze_hand(hand: PokerHand) -> dict:
    """
    Analyze a parsed hand and extract key metrics.
    Returns dict with analysis suitable for training feedback.
    """
    analysis = {
        "hand_id": hand.hand_id,
        "stakes": hand.stakes,
        "hero_cards": hand.hero_cards,
        "board": hand.board,
        "num_players": len(hand.players),
        "position": hand.positions.get(hand.hero_name, "?"),
        "preflop_actions": len(hand.actions_preflop),
        "flop_seen": len(hand.board) >= 3,
        "turn_seen": len(hand.board) >= 4,
        "river_seen": len(hand.board) >= 5,
        "went_to_showdown": "*** SHOW DOWN ***" in getattr(hand, '_raw', ''),
        "pot_size": hand.pot,
        "result": hand.result,
        "aggression": _calc_aggression(hand),
    }

    # Detect likely mistakes
    mistakes = []
    if analysis["flop_seen"] and not hand.actions_flop:
        mistakes.append("No flop action — likely folded preflop correctly")

    analysis["potential_mistakes"] = mistakes
    return analysis


def _calc_aggression(hand: PokerHand) -> float:
    """Calculate aggression factor: (bets + raises) / calls."""
    bets_raises = 0
    calls = 0
    for actions in [hand.actions_preflop, hand.actions_flop,
                     hand.actions_turn, hand.actions_river]:
        for a in actions:
            if a.player == hand.hero_name:
                if a.action in ("bets", "raises", "all-in"):
                    bets_raises += 1
                elif a.action == "calls":
                    calls += 1
    return bets_raises / max(1, calls)


def bulk_analyze(hand_texts: List[str]) -> List[dict]:
    """Parse and analyze multiple hand histories."""
    results = []
    for text in hand_texts:
        hand = parse_pokerstars(text)
        if hand:
            results.append(analyze_hand(hand))
    return results
