"""
Multi-way pot logic: 3 and 4-handed postflop decisions.
Adjusts equity calcs, bet sizing, and fold equity for multiple opponents.
"""
import random
from treys import Card, Evaluator
from equity import all_cards, remove_cards, _range_to_combos

evaluator = Evaluator()
RANKS_STR = "AKQJT98765432"


def multiway_equity(hero_cards, villain_ranges, board_cards, trials=300):
    """
    Calculate hero equity vs multiple villains.
    villain_ranges: list of lists of range strings.
    """
    if not villain_ranges:
        return 1.0

    deck = all_cards()
    dead = list(hero_cards) + list(board_cards)
    deck = remove_cards(deck, dead)

    # Pre-build villain combo lists
    villain_combos_per_player = []
    for vrange in villain_ranges:
        combos = []
        for rs in vrange:
            combos.extend(_range_to_combos(rs, deck))
        if not combos:
            return 0.5  # Can't calculate
        villain_combos_per_player.append(combos)

    wins = 0
    for _ in range(trials):
        # Pick one hand per villain
        villain_hands = []
        used_cards = set(dead)
        valid = True
        for vc_list in villain_combos_per_player:
            available = [c for c in vc_list
                        if c[0] not in used_cards and c[1] not in used_cards]
            if not available:
                valid = False
                break
            chosen = random.choice(available)
            villain_hands.append(chosen)
            used_cards.add(chosen[0])
            used_cards.add(chosen[1])

        if not valid:
            continue

        all_used = list(used_cards)
        remaining = remove_cards(deck, [c for h in villain_hands for c in h])
        needed = 5 - len(board_cards)
        runout = random.sample(remaining, needed) if needed > 0 else []
        full_board = list(board_cards) + runout

        hero_score = evaluator.evaluate(list(hero_cards), full_board)
        villain_scores = [evaluator.evaluate(list(h), full_board) for h in villain_hands]
        best_villain = min(villain_scores)  # Lower = better in treys

        if hero_score < best_villain:
            wins += 1
        elif hero_score == best_villain:
            wins += 1.0 / (len(villain_hands) + 1)

    return wins / max(1, trials)


def multiway_fold_equity(fold_to_cbet_per_player, num_players=2):
    """
    Probability ALL opponents fold to a c-bet.
    Each opponent folds independently.
    """
    prob_all_fold = 1.0
    for fe in fold_to_cbet_per_player:
        prob_all_fold *= fe
    return prob_all_fold


def multiway_sizing_adjustment(base_sizing_pct, num_opponents):
    """
    Adjust bet sizing for multi-way pots.
    In multi-way, bet smaller to keep ranges wide, or larger to isolate.
    """
    if num_opponents >= 3:
        return base_sizing_pct * 0.7  # Smaller, more cautious
    elif num_opponents == 2:
        return base_sizing_pct * 0.85
    return base_sizing_pct


def multiway_cbet_recommendation(hero_equity_mw, prob_all_fold, board_texture, num_opponents):
    """
    Whether to c-bet multi-way.
    Much more selective than heads-up.
    """
    if num_opponents >= 3:
        # 3-way+: only bet with strong equity
        if hero_equity_mw > 0.45 and prob_all_fold > 0.25:
            return "BET", 0.40, "Multi-way cu equity > 45% și fold equity decentă"
        return "CHECK", 0, "Multi-way — prea mulți adversari, check"
    elif num_opponents == 2:
        if hero_equity_mw > 0.40 and prob_all_fold > 0.30:
            return "BET", 0.50, "3-handed cu equity și fold equity"
        return "CHECK", 0, "3-handed — așteaptă o mână mai bună"

    return "BET", 0.55, "Heads-up standard"


def multiway_decision(hero_cards, villain_ranges, board_cards,
                      fold_to_cbets, opponent_types, position="IP",
                      pot=7.5, stack=100):
    """
    Complete multi-way postflop decision.
    Returns dict with action recommendation.
    """
    num_opponents = len(villain_ranges)
    if num_opponents == 1:
        return {"note": "heads-up — use PostflopEngine"}

    eq = multiway_equity(hero_cards, villain_ranges, board_cards)
    prob_fold = multiway_fold_equity(fold_to_cbets, num_opponents)

    from board_analyzer import analyze_flop
    flop = analyze_flop(board_cards)

    action, sizing, reason = multiway_cbet_recommendation(
        eq, prob_fold, flop, num_opponents
    )

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
