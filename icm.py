"""
Real ICM (Independent Chip Model) — properly implemented.
Computes exact conditional probabilities for all finish positions.
"""
import math
from itertools import permutations


def icm_equity(stacks, payouts):
    """
    Real ICM equity calculation.
    For each player, computes probability of finishing in each paid position,
    weighted by payout.

    Algorithm: P(player i finishes in position k) =
      sum over all other players j of:
        P(j wins) × P(i finishes k-1 in remaining field without j)

    With the base case: P(i wins) = stack_i / total_chips
    """
    n = len(stacks)
    total = sum(stacks)
    if total <= 0:
        return [0.0] * n

    equities = [0.0] * n

    for pos in range(len(payouts)):
        if payouts[pos] <= 0:
            continue
        for player in range(n):
            prob = _finish_prob(player, pos, stacks, total)
            equities[player] += prob * payouts[pos]

    return equities


def _finish_prob(player, position, stacks, total):
    """
    Exact probability that player finishes exactly at 'position' (0-indexed).
    Uses recursion with proper normalization.
    """
    n = len(stacks)
    if stacks[player] <= 0:
        return 0.0

    if position == 0:
        return stacks[player] / total if total > 0 else 0.0

    prob = 0.0
    for winner in range(n):
        if winner == player or stacks[winner] <= 0:
            continue

        prob_winner_first = stacks[winner] / total
        if prob_winner_first <= 0:
            continue

        # Remove winner, recalculate
        remaining = [s for i, s in enumerate(stacks) if i != winner]
        rem_total = sum(remaining)
        new_player_idx = player if player < winner else player - 1

        prob += prob_winner_first * _finish_prob(new_player_idx, position - 1,
                                                   remaining, rem_total)

    return prob


def icm_push_fold(stacks, blinds, payouts, hand_equity, position="SB"):
    """
    Push/fold ICM decision.
    Properly models risk premium near bubble.
    """
    hero_stack = stacks[0]
    sb, bb = blinds[0], blinds[1]
    pot_dead = sb + bb

    # Effective stack
    villain_stacks = stacks[1:]
    eff_stack = min(hero_stack, max(villain_stacks) if villain_stacks else hero_stack)

    # Calculate folding equity
    stacks_fold = list(stacks)
    if position == "SB":
        stacks_fold[0] = max(0, stacks_fold[0] - sb)
    elif position == "BB":
        stacks_fold[0] = max(0, stacks_fold[0] - bb)

    eq_fold = icm_equity(stacks_fold, payouts)[0]

    # Opponent calling range: tighter near bubble
    players_left = len(stacks)
    paid_spots = sum(1 for p in payouts if p > 0)
    bubble_factor = max(0, players_left - paid_spots)

    if bubble_factor <= 2:
        villain_call_pct = 0.20  # Very tight near bubble
    elif eff_stack <= 5 * bb:
        villain_call_pct = 0.30
    elif eff_stack <= 10 * bb:
        villain_call_pct = 0.40
    elif eff_stack <= 15 * bb:
        villain_call_pct = 0.50
    else:
        villain_call_pct = 0.60

    # Win/lose scenarios
    stacks_win = list(stacks)
    stacks_win[0] = hero_stack + eff_stack + pot_dead
    for i in range(1, len(stacks)):
        if stacks[i] == max(stacks[1:]):
            stacks_win[i] = max(0, stacks[i] - eff_stack)
            break

    eq_win = icm_equity(stacks_win, payouts)[0]
    eq_lose = 0.0  # Busted

    ev_push = (villain_call_pct * (hand_equity * eq_win + (1 - hand_equity) * eq_lose) +
               (1 - villain_call_pct) * icm_equity(
                   [hero_stack + pot_dead] + list(stacks[1:]), payouts)[0])

    ev_diff = ev_push - eq_fold

    risk_premium = (eq_fold - eq_win * hand_equity) if eq_fold > 0 else 0

    if ev_diff > 0.005:
        return {
            "action": "PUSH",
            "ev_push": round(ev_push, 4),
            "ev_fold": round(eq_fold, 4),
            "ev_diff": round(ev_diff, 4),
            "risk_premium": round(risk_premium, 4),
            "villain_call_pct": villain_call_pct,
            "reasoning": f"Push +$EV ({ev_diff*100:.1f}%), risk premium: {risk_premium*100:.1f}%",
        }
    else:
        return {
            "action": "FOLD",
            "ev_push": round(ev_push, 4),
            "ev_fold": round(eq_fold, 4),
            "ev_diff": round(ev_diff, 4),
            "risk_premium": round(risk_premium, 4),
            "reasoning": f"Fold: -$EV ({ev_diff*100:.1f}%)",
        }


def tournament_stage_adjustment(stacks, blinds, payout_structure):
    """Determine tournament stage and strategy adjustments."""
    total_chips = sum(stacks)
    avg_stack = total_chips / max(1, len(stacks))
    bb = blinds[1] if len(blinds) > 1 else blinds[0]

    hero_bb = stacks[0] / bb if bb > 0 else float('inf')

    if hero_bb <= 8:
        stage, agg, opens = "push_fold", 2.0, "all-in"
    elif hero_bb <= 20:
        stage, agg, opens = "short", 1.5, "2.0-2.2x"
    elif hero_bb <= 40:
        stage, agg, opens = "mid", 1.2, "2.2-2.5x"
    elif hero_bb <= 80:
        stage, agg, opens = "deep", 1.0, "2.5-3.0x"
    else:
        stage, agg, opens = "very_deep", 0.9, "3.0x+"

    players_left = len(stacks)
    paid = sum(1 for p in payout_structure if p > 0)
    bubble_prox = max(0, players_left - paid)

    if bubble_prox <= 3 and players_left > paid:
        stage += " (bubble)"
        agg -= 0.3

    return {
        "stage": stage,
        "hero_bb": round(hero_bb, 1),
        "aggression_modifier": round(agg, 2),
        "open_size": opens,
        "bubble_proximity": bubble_prox,
        "avg_stack_bb": round(avg_stack / bb, 1) if bb > 0 else 0,
    }
