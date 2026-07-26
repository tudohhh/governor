"""
Advanced board texture analysis: range advantage, nut advantage, fold equity.
"""
from board_analyzer import analyze_flop, _rank
from equity import all_cards, remove_cards
from treys import Card, Evaluator
import random

evaluator = Evaluator()
RANKS_STR = "AKQJT98765432"


def range_advantage(hero_position, villain_position, board_cards):
    """
    Determine who has range advantage on this board.
    Returns: "hero", "villain", or "neutral"
    """
    flop = analyze_flop(board_cards)
    high = flop["high_type"]
    paired = flop["paired"]

    # Early position ranges have more high cards
    early_pos = {"UTG", "HJ"}
    late_pos = {"CO", "BTN", "SB"}

    hero_early = hero_position in early_pos
    villain_early = villain_position in early_pos

    # High boards favor early position (more broadways in range)
    if high in ("ace-high", "broadway") and not paired:
        if hero_early and not villain_early:
            return "hero"
        elif villain_early and not hero_early:
            return "villain"
        else:
            return "neutral"

    # Low connected boards favor late position (more suited connectors)
    if high in ("mid", "low") and flop["connected"] in ("fully-connected", "semi-connected"):
        if not hero_early and hero_position != "BB":
            return "hero"
        elif not villain_early and villain_position != "BB":
            return "villain"
        else:
            return "neutral"

    # Paired boards: neutral, but favors the aggressor
    if paired:
        return "neutral"

    return "neutral"


def nut_advantage(hero_range_strs, villain_range_strs, board_cards):
    """
    Estimate who has more nut hands in their range.
    Returns ratio: hero_nuts / villain_nuts. >1 means hero has more nuts.
    """
    hero_nuts = _count_nut_combos(hero_range_strs, board_cards)
    villain_nuts = _count_nut_combos(villain_range_strs, board_cards)

    if villain_nuts == 0:
        return 2.0 if hero_nuts > 0 else 1.0

    return hero_nuts / villain_nuts


def _count_nut_combos(range_strs, board_cards):
    """Count how many combos in a range make strong hands on this board."""
    from equity import _range_to_combos

    deck = all_cards()
    deck = remove_cards(deck, board_cards)

    strong = 0
    total = 0
    for rs in range_strs:
        combos = _range_to_combos(rs, deck)
        for hero_cards in combos:
            total += 1
            # Check if this hand makes top pair+ or strong draw
            eq = _quick_equity(hero_cards, board_cards)
            if eq > 0.70:
                strong += 1

    return strong


def _quick_equity(hero, board):
    """Very rough equity estimate for nut counting."""
    # Simple heuristic based on hand strength
    hr1, hr2 = Card.int_to_str(hero[0])[0], Card.int_to_str(hero[1])[0]
    board_ranks = [Card.int_to_str(c)[0] for c in board]

    # Pair on board?
    if hr1 in board_ranks or hr2 in board_ranks:
        return 0.75
    # Overpair?
    hero_high = min(RANKS_STR.index(hr1), RANKS_STR.index(hr2))
    board_high = min(RANKS_STR.index(r) for r in board_ranks)
    if hero_high < board_high:
        return 0.80
    # Two high cards
    if hero_high <= 5:
        return 0.55
    return 0.40


def fold_equity_estimate(board_cards, villain_fold_to_cbet, board_texture=None):
    """
    Estimate fold equity on this board vs this opponent.
    """
    if board_texture is None:
        board_texture = analyze_flop(board_cards)

    wetness = board_texture["wetness"]
    paired = board_texture["paired"]

    # Base fold equity from opponent tendency
    base_fe = villain_fold_to_cbet

    # Adjust for board texture
    if wetness == "dry" and paired:
        base_fe += 0.10  # Paired boards: more folds
    elif wetness == "wet":
        base_fe -= 0.08  # Wet boards: less folds
    elif wetness == "dry":
        base_fe += 0.05

    return max(0.10, min(0.85, base_fe))


def geometric_sizing_recommendation(flop_texture, range_adv, nut_ratio, blockers_boost):
    """
    Recommend sizing strategy based on board + range dynamics.
    Returns (strategy, sizing_percent, reasoning).
    """
    wetness = flop_texture["wetness"]
    paired = flop_texture["paired"]

    # Polarized situations: use large sizing
    if nut_ratio > 2.0:
        return ("BET", 0.80, "Nut advantage mare — bet mare, range polarizat")
    if nut_ratio < 0.5:
        return ("CHECK", 0, "Villain are mai multe nuts — check")

    # Range advantage + dry board: bet small, wide range
    if range_adv == "hero" and (wetness == "dry" or paired):
        return ("BET", 0.33, "Range advantage pe board uscat — c-bet mic cu tot range-ul")

    # Blockers boost: can increase bluff frequency
    if blockers_boost > 1.2 and wetness in ("dry", "semi-dry"):
        return ("BET", 0.50, f"Blocanți puternici (+{int((blockers_boost-1)*100)}% bluff) — c-bet moderat")

    # Standard
    if wetness == "wet":
        return ("BET", 0.66, "Board umed — sizing mare, protejează equity")
    elif range_adv == "hero":
        return ("BET", 0.55, "Range advantage moderat")
    else:
        return ("CHECK", 0, "Fără avantaj clar — check")
