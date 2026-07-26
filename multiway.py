"""
Multi-way pot logic — properly collision-checked.
3 and 4-handed postflop equity and decision making.
"""
import random
from treys import Card, Evaluator
from equity import all_cards, remove_cards, _range_to_combos

evaluator = Evaluator()
RANKS_STR = "AKQJT98765432"


def multiway_equity(hero_cards, villain_ranges, board_cards, trials=500):
    """
    Accurate multi-way equity with collision detection.
    Returns (equity, num_valid_trials).
    """
    if not villain_ranges:
        return 1.0

    deck = all_cards()
    dead = set(list(hero_cards) + list(board_cards))
    deck = remove_cards(deck, list(dead))

    # Pre-build valid combos (no overlap with hero/board)
    villain_combos_per_player = []
    for vrange in villain_ranges:
        combos = []
        for rs in vrange:
            for h in _range_to_combos(rs, deck):
                if h[0] not in dead and h[1] not in dead:
                    combos.append(h)
        if not combos:
            return 0.5  # Can't compute, fallback
        villain_combos_per_player.append(combos)

    wins = 0
    valid = 0
    for _ in range(trials):
        all_used = set(dead)
        villain_hands = []
        ok = True

        for vc_list in villain_combos_per_player:
            available = []
            for h in vc_list:
                if h[0] not in all_used and h[1] not in all_used:
                    available.append(h)
            if not available:
                ok = False
                break
            chosen = random.choice(available)
            villain_hands.append(chosen)
            all_used.add(chosen[0])
            all_used.add(chosen[1])

        if not ok:
            continue

        remaining = [c for c in deck if c not in all_used]
        needed = 5 - len(board_cards)
        if needed > 0 and len(remaining) >= needed:
            runout = random.sample(remaining, needed)
        elif needed <= 0:
            runout = []
        else:
            continue

        full_board = list(board_cards) + runout
        hero_score = evaluator.evaluate(list(hero_cards), full_board)
        villain_scores = [evaluator.evaluate(list(h), full_board) for h in villain_hands]
        best_villain = min(villain_scores)

        if hero_score < best_villain:
            wins += 1
        elif hero_score == best_villain:
            wins += 1.0 / (len(villain_hands) + 1)

        valid += 1

    if valid == 0:
        return 0.5
    return wins / valid


def multiway_fold_equity(fold_to_cbets):
    """Probability ALL opponents fold."""
    prob = 1.0
    for fe in fold_to_cbets:
        prob *= fe
    return prob


def multiway_sizing_adjustment(sizing, num_opponents):
    """Adjust sizing for multi-way: smaller with more opponents."""
    factors = {1: 1.0, 2: 0.85, 3: 0.65, 4: 0.50}
    return sizing * factors.get(num_opponents, 0.60)


def multiway_decision(hero_cards, villain_ranges, board_cards,
                      fold_to_cbets, opponent_types=None, position="IP",
                      pot=7.5, stack=100):
    """Complete multi-way decision."""
    num_opponents = len(villain_ranges)
    if num_opponents == 1:
        return {"action": "HEADS_UP", "sizing_pct": 0.55,
                "reasoning": "Folosește PostflopEngine pentru heads-up"}

    eq = multiway_equity(hero_cards, villain_ranges, board_cards)
    prob_fold = multiway_fold_equity(fold_to_cbets)

    from board_analyzer import analyze_flop
    flop = analyze_flop(board_cards)

    # Multi-way c-bet: much more selective
    if eq > 0.55 and prob_fold > 0.15:
        action, sizing, reason = "BET", 0.45, f"Multi-way ({num_opponents} opp) cu equity bună"
    elif eq > 0.40 and prob_fold > 0.30:
        action, sizing, reason = "BET", 0.35, f"Fold equity decentă în {num_opponents}-way"
    elif eq > 0.30 and num_opponents == 2:
        action, sizing, reason = "BET", 0.33, "3-handed — c-bet exploratoriu"
    else:
        action, sizing, reason = "CHECK", 0, f"Multi-way — equity insuficientă"

    sizing = multiway_sizing_adjustment(sizing, num_opponents)

    return {
        "num_opponents": num_opponents,
        "hero_equity": round(eq, 3),
        "prob_all_fold": round(prob_fold, 3),
        "action": action,
        "sizing_pct": round(sizing, 2),
        "sizing_bb": round(pot * sizing, 1),
        "reasoning": reason,
    }
