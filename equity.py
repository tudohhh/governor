"""
Equity calculator using Monte Carlo simulation.
Estimates hand vs hand and hand vs range equity.
"""
import random
from treys import Card, Evaluator

evaluator = Evaluator()

# Card generation utilities
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]  # treys format

def all_cards():
    """Generate all 52 cards as treys ints."""
    return [Card.new(r + s) for r in RANKS for s in SUITS]

def cards_from_str(s):
    """Parse treys-format string like 'AsKh' into list of ints."""
    cards = []
    i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i] == "1" and s[i+1] == "0":
            cards.append(Card.new(s[i:i+3]))
            i += 3
        else:
            cards.append(Card.new(s[i:i+2]))
            i += 2
    return cards

def remove_cards(deck, to_remove):
    """Remove specific cards from a deck."""
    return [c for c in deck if c not in to_remove]


def equity_vs_range(hero_cards, villain_range_strs, board_cards, trials=500):
    """
    Monte Carlo equity of hero hand vs villain range on given board.
    villain_range_strs: list of treys-format strings like ["AA", "KK", "AKs"]
    Returns equity as float 0-1.
    """
    deck = all_cards()
    dead = list(hero_cards) + list(board_cards)
    deck = remove_cards(deck, dead)

    # Convert villain range strings to actual card combinations
    villain_combos = []
    for rs in villain_range_strs:
        combos = _range_to_combos(rs, deck)
        villain_combos.extend(combos)

    if not villain_combos:
        return 0.5

    wins = 0
    # Safety check
    all_input = list(hero_cards) + list(board_cards)
    if len(set(all_input)) != len(all_input):
        return 0.5  # Invalid: duplicate cards

    for _ in range(trials):
        # Pick random villain hand from range
        v_hand = random.choice(villain_combos)
        # Remove those cards from deck
        remaining = remove_cards(deck, list(v_hand))
        # Deal remaining board cards
        needed = 5 - len(board_cards)
        if needed > 0:
            runout = random.sample(remaining, needed)
        else:
            runout = []
        full_board = list(board_cards) + runout

        hero_score = evaluator.evaluate(list(hero_cards), full_board)
        villain_score = evaluator.evaluate(list(v_hand), full_board)

        if hero_score < villain_score:
            wins += 1
        elif hero_score == villain_score:
            wins += 0.5

    return wins / trials


def equity_vs_hand(hero_cards, villain_cards, board_cards, trials=300):
    """Monte Carlo equity: specific hand vs specific hand."""
    if len(board_cards) >= 5:
        hero_score = evaluator.evaluate(list(hero_cards), list(board_cards[:5]))
        villain_score = evaluator.evaluate(list(villain_cards), list(board_cards[:5]))
        if hero_score < villain_score:
            return 1.0
        elif hero_score == villain_score:
            return 0.5
        return 0.0

    deck = all_cards()
    dead = list(hero_cards) + list(villain_cards) + list(board_cards)
    deck = remove_cards(deck, dead)

    wins = 0
    for _ in range(trials):
        needed = 5 - len(board_cards)
        runout = random.sample(deck, needed)
        full_board = list(board_cards) + runout
        hero_score = evaluator.evaluate(list(hero_cards), full_board)
        villain_score = evaluator.evaluate(list(villain_cards), full_board)
        if hero_score < villain_score:
            wins += 1
        elif hero_score == villain_score:
            wins += 0.5

    return wins / trials


def pot_odds_to_equity(bet_size, pot_size):
    """
    Convert bet size to required equity to call.
    Returns (fraction, percentage).
    """
    call_amount = bet_size
    total_pot_after = pot_size + bet_size * 2  # pot + his bet + your call
    if total_pot_after == 0:
        return (0, 0)
    fraction = call_amount / total_pot_after
    return (fraction, fraction * 100)


def eq_to_string(equity):
    """Format equity as readable string."""
    return f"{equity * 100:.0f}%"


def _range_to_combos(range_str, deck):
    """
    Convert a range string like 'AKs', 'AA', 'KQo' to list of card tuples.
    """
    result = []
    available = set(deck)

    if len(range_str) == 2:  # Pocket pair: "AA"
        r = range_str[0]
        suited_cards = [Card.new(r + s) for s in SUITS]
        suited_cards = [c for c in suited_cards if c in available]
        for i in range(len(suited_cards)):
            for j in range(i + 1, len(suited_cards)):
                result.append((suited_cards[i], suited_cards[j]))

    elif len(range_str) == 3:
        r1, r2, t = range_str[0], range_str[1], range_str[2]
        if t == "s":  # Suited
            for s in SUITS:
                c1 = Card.new(r1 + s)
                c2 = Card.new(r2 + s)
                if c1 in available and c2 in available:
                    result.append((c1, c2))
        elif t == "o":  # Offsuit
            for s1 in SUITS:
                for s2 in SUITS:
                    if s1 != s2:
                        c1 = Card.new(r1 + s1)
                        c2 = Card.new(r2 + s2)
                        if c1 in available and c2 in available:
                            result.append((c1, c2))
        else:  # Both suited and offsuit (e.g., "AK" with no suffix)
            for s in SUITS:
                c1 = Card.new(r1 + s)
                c2 = Card.new(r2 + s)
                if c1 in available and c2 in available:
                    result.append((c1, c2))
            for s1 in SUITS:
                for s2 in SUITS:
                    if s1 != s2:
                        c1 = Card.new(r1 + s1)
                        c2 = Card.new(r2 + s2)
                        if c1 in available and c2 in available:
                            result.append((c1, c2))

    return result


# Simplified GTO postflop ranges (what villain continues with)
VILLAIN_CONTINUE_VS_CBET = {
    "standard": {
        "dry": ["AA", "KK", "QQ", "JJ", "TT", "AK", "AQ", "KQ"],
        "wet": ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "AK", "AQ", "AJ", "KQ", "QJ", "JT"],
        "paired": ["AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "AK", "AQ"],
    }
}
