"""
ICM (Independent Chip Model) calculator for tournament poker.
Computes tournament equity and push/fold Nash equilibria.
"""
import math
import itertools


def icm_equity(stacks, payouts):
    """
    Calculate ICM equity for each player.
    stacks: list of chip counts
    payouts: list of payout percentages (should sum to 1.0)

    Returns list of equities (probability-weighted payouts).
    """
    n = len(stacks)
    total_chips = sum(stacks)
    equities = [0.0] * n

    # For each payout position
    for position, payout in enumerate(payouts):
        if payout <= 0:
            continue

        for player in range(n):
            stack = stacks[player]
            if stack <= 0:
                continue

            # Probability this player finishes in this position
            prob = _finish_probability(player, position, stacks, total_chips)
            equities[player] += prob * payout

    return equities


def _finish_probability(player, position, stacks, total_chips):
    """Probability that 'player' finishes exactly at 'position'."""
    n = len(stacks)
    if position == 0:
        # First place: proportional to chip count
        return stacks[player] / total_chips if total_chips > 0 else 0

    # For subsequent positions: sum over who wins first, then player wins next
    prob = 0.0
    for winner in range(n):
        if winner == player or stacks[winner] <= 0:
            continue

        prob_winner_wins = stacks[winner] / total_chips
        if prob_winner_wins <= 0:
            continue

        # Remove winner, recalculate remaining
        remaining_stacks = [s for i, s in enumerate(stacks) if i != winner]
        remaining_total = sum(remaining_stacks)
        if position <= len(remaining_stacks):
            prob += (prob_winner_wins *
                     _finish_probability_simple(player if player < winner else player - 1,
                                                position - 1, remaining_stacks, remaining_total))

    return prob


def _finish_probability_simple(player, position, stacks, total):
    """Simplified: just chip proportion."""
    if position == 0:
        return stacks[player] / total if total > 0 else 0
    return stacks[player] / total if total > 0 else 0


def icm_push_fold(stacks, blinds, payouts, hand_equity, position="SB"):
    """
    Simplified push/fold Nash equilibrium for short stacks.
    Determines whether pushing is +$EV compared to folding.

    stacks: list of chip counts (hero is first)
    blinds: (sb, bb) amounts
    payouts: payout structure
    hand_equity: equity of hero's hand vs calling range

    Returns dict with recommendation.
    """
    hero_stack = stacks[0]
    sb, bb = blinds
    pot_before = sb + bb

    # Estimate villain calling range based on stack depth
    villain_stack = min(stacks[1:]) if len(stacks) > 1 else hero_stack
    effective_stack = min(hero_stack, villain_stack)

    # ICM: folding equity (what happens if we fold)
    stacks_fold = list(stacks)
    if position == "SB":
        stacks_fold[0] -= sb  # Posted SB
    else:
        stacks_fold[0] -= bb  # Posted BB

    eq_fold = icm_equity(stacks_fold, payouts)[0]

    # ICM: push equity
    # Villain calling range tightens as stacks get shorter
    if effective_stack <= 5 * bb:
        villain_call_pct = 0.30  # Very tight
    elif effective_stack <= 10 * bb:
        villain_call_pct = 0.40
    elif effective_stack <= 15 * bb:
        villain_call_pct = 0.50
    else:
        villain_call_pct = 0.60

    hero_double_stack = min(hero_stack * 2, hero_stack + effective_stack)
    stacks_win = list(stacks)
    stacks_win[0] = hero_double_stack + pot_before
    if len(stacks_win) > 1:
        opponent_idx = 1
        stacks_win[opponent_idx] = stacks[opponent_idx] - effective_stack
        stacks_win[opponent_idx] = max(0, stacks_win[opponent_idx])

    eq_win = icm_equity(stacks_win, payouts)[0]

    # When called and lose
    stacks_lose = list(stacks)
    stacks_lose[0] = 0
    eq_lose = 0.0

    # Combined EV
    ev_push = (villain_call_pct * (hand_equity * eq_win + (1 - hand_equity) * eq_lose) +
               (1 - villain_call_pct) * icm_equity([hero_stack + pot_before if i == 0 else s
                                                    for i, s in enumerate(stacks)], payouts)[0])

    ev_diff = ev_push - eq_fold

    if ev_diff > 0.005:
        return {
            "action": "PUSH",
            "ev_push": round(ev_push, 4),
            "ev_fold": round(eq_fold, 4),
            "ev_diff": round(ev_diff, 4),
            "reasoning": f"Push +$EV: +{ev_diff*100:.1f}% ROI",
        }
    else:
        return {
            "action": "FOLD",
            "ev_push": round(ev_push, 4),
            "ev_fold": round(eq_fold, 4),
            "ev_diff": round(ev_diff, 4),
            "reasoning": f"Fold: push -$EV ({ev_diff*100:.1f}%)",
        }


def tournament_stage_adjustment(stacks, blinds, payout_structure):
    """
    Adjust strategy based on tournament stage.
    Returns stage name and strategy modifiers.
    """
    total_chips = sum(stacks)
    avg_stack = total_chips / len(stacks)
    bb = blinds[1]

    hero_bb = stacks[0] / bb if bb > 0 else float('inf')

    if hero_bb <= 10:
        stage = "push_fold"
        aggression = 2.0
        open_size = "all_in"
    elif hero_bb <= 25:
        stage = "short_stack"
        aggression = 1.5
        open_size = "2.0x"
    elif hero_bb <= 50:
        stage = "mid_stack"
        aggression = 1.2
        open_size = "2.3x"
    elif hero_bb <= 100:
        stage = "deep"
        aggression = 1.0
        open_size = "2.5x"
    else:
        stage = "very_deep"
        aggression = 0.9
        open_size = "3.0x"

    # Bubble factor: near the money, play tighter
    players_remaining = len(stacks)
    players_paid = sum(1 for p in payout_structure if p > 0)
    bubble_proximity = max(0, players_remaining - players_paid)

    if bubble_proximity <= 3 and players_remaining > players_paid:
        aggression -= 0.3  # Tighten up near bubble
        stage += " (bubble)"

    return {
        "stage": stage,
        "hero_bb": round(hero_bb, 1),
        "aggression_modifier": aggression,
        "open_size": open_size,
        "bubble_proximity": bubble_proximity,
    }
