"""
Bayesian range narrowing: update villain's estimated range after each action.
Tracks what combos villain could have after calling, raising, or folding.
"""
import random
from equity import all_cards, remove_cards, _range_to_combos
from treys import Card, Evaluator

evaluator = Evaluator()
RANKS_STR = "AKQJT98765432"


def initial_range(villain_position, action_preflop="call"):
    """
    Get villain's initial range entering the flop.
    action_preflop: "call" (called a raise) or "raise" (3-bet)
    """
    from app import GTO_RANGES

    if action_preflop == "3bet":
        ranges_3b = GTO_RANGES.get("VS_RFI", {}).get("3bet", {})
        for k in ranges_3b:
            if villain_position in k:
                result = ranges_3b.get(k, set())
                return list(result) if isinstance(result, set) else result
        return list(ranges_3b.get(f"vs_{villain_position}", set()))

    # Calling range
    ranges_call = GTO_RANGES.get("VS_RFI", {}).get("call", {})
    for k, v in ranges_call.items():
        if villain_position in k:
            return list(v) if isinstance(v, set) else v

    # Default: wide calling range
    default = ["AA","KK","QQ","JJ","TT","AK","AQ"]
    result = GTO_RANGES.get("RFI", {}).get("CO", default)
    return list(result) if isinstance(result, set) else result


def narrow_after_flop_call(villain_range_strs, board_cards):
    """
    After villain calls a flop c-bet, remove air from their range.
    Keep: pairs, draws, overcards with backdoors.
    """
    narrowed = []
    deck = all_cards()
    deck = remove_cards(deck, board_cards)

    for combo in villain_range_strs:
        hands = _range_to_combos(combo, deck)
        kept = 0
        total = len(hands)
        for hero_cards in hands:
            eq = _rough_equity(hero_cards, board_cards)
            if eq > 0.15:  # Keep if has any equity
                kept += 1

        if total > 0 and kept / total > 0.3:
            narrowed.append(combo)

    return narrowed if narrowed else villain_range_strs


def narrow_after_turn_call(villain_range_strs, board_cards, flop_was_wet=False):
    """
    After villain calls turn barrel, range tightens further.
    Keep: top pair+, strong draws only.
    """
    narrowed = []
    deck = all_cards()
    deck = remove_cards(deck, board_cards)

    for combo in villain_range_strs:
        hands = _range_to_combos(combo, deck)
        kept = 0
        total = len(hands)
        for hero_cards in hands:
            eq = _rough_equity(hero_cards, board_cards)
            threshold = 0.20 if flop_was_wet else 0.30
            if eq > threshold:
                kept += 1

        if total > 0 and kept / total > 0.4:
            narrowed.append(combo)

    return narrowed if narrowed else villain_range_strs[:len(villain_range_strs)//2]


def narrow_after_raise(villain_range_strs, board_cards):
    """
    Villain raised — their range is very strong.
    Keep: top pair good kicker, two pair+, strong draws (combo draws).
    """
    narrowed = []
    deck = all_cards()
    deck = remove_cards(deck, board_cards)

    for combo in villain_range_strs:
        hands = _range_to_combos(combo, deck)
        kept = 0
        total = len(hands)
        for hero_cards in hands:
            eq = _rough_equity(hero_cards, board_cards)
            if eq > 0.50:
                kept += 1

        if total > 0 and kept / total > 0.5:
            narrowed.append(combo)

    return narrowed if narrowed else villain_range_strs[:max(1, len(villain_range_strs)//4)]


def estimate_villain_equity_distribution(villain_range_strs, board_cards, samples=5):
    """
    Instead of one equity number, get distribution: {tier: count}.
    Returns: {strong: N, medium: N, weak: N}
    """
    deck = all_cards()
    deck = remove_cards(deck, board_cards)

    strong = medium = weak = 0
    all_hands = []
    for combo in villain_range_strs:
        hands = _range_to_combos(combo, deck)
        all_hands.extend(hands)

    sampled = random.sample(all_hands, min(samples, len(all_hands))) if all_hands else []

    for hero_cards in sampled:
        eq = _rough_equity(hero_cards, board_cards)
        if eq > 0.65:
            strong += 1
        elif eq > 0.30:
            medium += 1
        else:
            weak += 1

    total = len(sampled) or 1
    return {
        "strong": round(strong / total * 100),
        "medium": round(medium / total * 100),
        "weak": round(weak / total * 100),
    }


def _rough_equity(hero_cards, board_cards):
    """Quick equity estimation without full Monte Carlo."""
    hr1, hr2 = (Card.int_to_str(c)[0] for c in hero_cards)
    board_ranks = [Card.int_to_str(c)[0] for c in board_cards]

    # Pairs
    pair_count = 0
    if hr1 in board_ranks:
        pair_count += 1
    if hr2 in board_ranks:
        pair_count += 1
    if hr1 == hr2:
        pair_count += 1

    if pair_count >= 2:
        return 0.85
    if pair_count == 1:
        return 0.65

    # Overcards
    hero_ranks_idx = [RANKS_STR.index(hr1), RANKS_STR.index(hr2)]
    board_high_idx = min(RANKS_STR.index(r) for r in board_ranks)

    overcards = sum(1 for idx in hero_ranks_idx if idx < board_high_idx)

    if overcards == 2:
        return 0.40
    if overcards == 1:
        return 0.25

    # Draw potential
    hero_suits = [Card.get_suit_int(c) for c in hero_cards]
    board_suits = [Card.get_suit_int(c) for c in board_cards]
    suited_cards = 0
    for hs in hero_suits:
        if board_suits.count(hs) >= 2:
            suited_cards += 1

    if suited_cards >= 1:
        return 0.30  # Flush draw

    return 0.08  # Air
