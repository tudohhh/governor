"""
Board texture analyzer for post-flop decision making.
Classifies flop/turn/river texture to inform betting strategy.
"""
from treys import Card

RANK_NAMES = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]

def _rank(card_int):
    """Get rank index (0-12) from treys card int."""
    s = Card.int_to_str(card_int)
    return "23456789TJQKA".index(s[0])

def _suit(card_int):
    """Get suit index (0-3) from treys card int."""
    return Card.get_suit_int(card_int)

def _ranks(cards):
    return [_rank(c) for c in cards]

def _suits(cards):
    return [_suit(c) for c in cards]


def analyze_flop(cards):
    """
    Analyze flop texture (3 cards).
    Returns dict with classification details.
    """
    if len(cards) != 3:
        raise ValueError("Flop needs exactly 3 cards")

    r = _ranks(cards)
    s = _suits(cards)
    high = max(r)

    # Paired board?
    paired = len(set(r)) < 3
    trips = len(set(r)) == 1

    # Suitedness
    suited = "monotone" if len(set(s)) == 1 else ("rainbow" if len(set(s)) == 3 else "two-tone")

    # Connectedness: count gaps between sorted ranks
    sorted_r = sorted(r)
    gaps = [sorted_r[i+1] - sorted_r[i] - 1 for i in range(2)]
    total_gap = sum(gaps)
    max_gap = max(gaps) if gaps else 0

    if total_gap == 0:
        connected = "fully-connected"
    elif total_gap <= 1 and max_gap <= 1:
        connected = "semi-connected"
    elif total_gap <= 3:
        connected = "moderate"
    else:
        connected = "disconnected"

    # High card classification (rank index: 0=2, 12=A)
    if high >= 12:  # A
        high_type = "ace-high"
    elif high >= 8:  # T-K
        high_type = "broadway"
    elif high >= 4:  # 6-9
        high_type = "mid"
    else:  # 2-5
        high_type = "low"

    # Wetness: how many draws are possible
    wetness_score = 0
    if suited == "two-tone":
        wetness_score += 1
    if suited == "monotone":
        wetness_score += 2
    if connected in ("fully-connected", "semi-connected"):
        wetness_score += 1
    if total_gap <= 1:
        wetness_score += 1

    if wetness_score >= 2:
        wetness = "wet"
    elif wetness_score == 1:
        wetness = "semi-dry"
    else:
        wetness = "dry"

    # C-bet recommendation
    if paired and not trips:
        texture_cbet = "frequent_small"  # paired boards: c-bet small, often
    elif wetness == "dry":
        texture_cbet = "frequent_small"  # dry: can bet small, range advantage matters
    elif wetness == "wet":
        texture_cbet = "polarized_large"  # wet: bet large, polarized
    else:
        texture_cbet = "standard"

    return {
        "cards": [Card.int_to_pretty_str(c) for c in cards],
        "paired": paired,
        "trips": trips,
        "suited": suited,
        "connected": connected,
        "high_type": high_type,
        "wetness": wetness,
        "texture_cbet": texture_cbet,
        "high_card": RANK_NAMES[high],
        "total_gap": total_gap,
    }


def analyze_turn(board_4):
    """
    Analyze turn card in context of the board.
    Returns dict with turn-specific info.
    """
    if len(board_4) != 4:
        raise ValueError("Turn board needs exactly 4 cards")

    r = _ranks(board_4)
    s = _suits(board_4)
    turn_rank = r[-1]
    turn_suit = s[-1]

    # Did the turn complete any draws?
    flop = board_4[:3]
    flop_suits = _suits(flop)
    turn_completes_flush = flop_suits.count(s[-1]) >= 2

    # Straight completion check
    sorted_all = sorted(r)
    straight_danger = False
    for i in range(len(sorted_all) - 3):
        if sorted_all[i+3] - sorted_all[i] <= 3:
            straight_danger = True
            break

    # Did board pair?
    paired_turn = len(set(r)) < 4

    return {
        "turn_card": Card.int_to_pretty_str(board_4[-1]),
        "completes_flush": turn_completes_flush,
        "straight_danger": straight_danger,
        "paired": paired_turn,
        "overcard_to_flop": turn_rank > max(_ranks(flop)),
    }


def describe_board(flop_analysis):
    """Human-readable board description in Romanian."""
    parts = []
    if flop_analysis["paired"]:
        parts.append("pereche")
    if flop_analysis["trips"]:
        parts.append("trips pe bord")
    parts.append(flop_analysis["high_type"])

    suit_map = {"rainbow": "rainbow", "two-tone": "two-tone", "monotone": "monotone"}
    parts.append(suit_map.get(flop_analysis["suited"], flop_analysis["suited"]))

    parts.append(flop_analysis["wetness"])

    return " · ".join(parts)


def cbet_sizing_recommendation(flop_analysis, ip=True, hero_equity=0.5):
    """
    Recommend c-bet sizing based on board texture and position.
    Returns (action, sizing_percent, reasoning).
    """
    wetness = flop_analysis["wetness"]
    paired = flop_analysis["paired"]
    high = flop_analysis["high_type"]

    # Paired flops: bet small, very often
    if paired:
        return ("BET", 0.33, "Board pereche — c-bet mic, range-ul tău pare mai credibil")

    # Dry boards: bet small when IP, can check OOP
    if wetness == "dry":
        if ip:
            return ("BET", 0.33, "Board uscat — c-bet mic, adversarul oricum nu prinde")
        else:
            return ("BET" if hero_equity > 0.45 else "CHECK", 0.40,
                    "Board uscat OOP — bet moderat dacă ai equity, altfel check")

    # Wet boards: bet large with strong hands, check weak
    if wetness == "wet":
        if hero_equity > 0.60:
            return ("BET", 0.75, "Board umed — bet mare, multe draw-uri de protejat")
        elif hero_equity > 0.45:
            return ("BET", 0.55, "Board umed — bet moderat, equity decentă")
        else:
            return ("CHECK", 0, "Board umed — equity slabă, mai bine check")

    # Semi-dry: standard
    if ip:
        if hero_equity > 0.50:
            return ("BET", 0.55, "C-bet standard IP cu equity > 50%")
        else:
            return ("CHECK", 0, "Equity sub 50%, check în spate")
    else:
        if hero_equity > 0.55:
            return ("BET", 0.60, "C-bet OOP cu range avantage")
        else:
            return ("CHECK", 0, "Fără range advantage OOP")

    return ("CHECK", 0, "Default: verifică")
