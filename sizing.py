"""
Geometric bet sizing based on SPR (stack-to-pot ratio).
Plans bet sizes across remaining streets to get all-in by river.
"""
import math


def calculate_spr(stack, pot):
    """Stack-to-pot ratio."""
    return stack / pot if pot > 0 else float('inf')


def geometric_sizing_plan(stack, pot, streets_remaining):
    """
    Calculate equal-percentage bet sizes to get all-in.
    Returns list of (bet_pot_percent, bet_amount, pot_after) for each street.
    """
    if streets_remaining <= 0 or pot <= 0:
        return []

    spr = calculate_spr(stack, pot)
    if spr <= 0:
        return []

    # Geometric growth: same % of pot on each street
    # target: after N bets of x% pot, we're all-in
    # (1 + 2*x)^N = (pot + 2*stack) / pot
    growth_target = (pot + 2 * stack) / pot
    geo_pct = (growth_target ** (1.0 / streets_remaining) - 1) / 2

    plan = []
    current_pot = pot
    current_stack = stack

    for i in range(streets_remaining):
        bet = current_pot * geo_pct
        bet = min(bet, current_stack)  # Can't bet more than stack
        plan.append({
            "street": i + 1,
            "bet_pot_pct": geo_pct,
            "bet_amount": round(bet, 1),
            "pot_after": round(current_pot + bet * 2, 1),
            "stack_remaining": round(current_stack - bet, 1),
        })
        current_pot += bet * 2
        current_stack -= bet

    return plan


def recommend_sizing(board_texture, spr, streets_remaining, hero_equity, range_adv,
                     nut_ratio, blockers_boost, position="IP"):
    """
    Recommend optimal bet sizing based on complete situation.

    Returns dict: {sizing_pct, sizing_type, reasoning, plan}.
    """
    wetness = board_texture["wetness"]
    paired = board_texture["paired"]

    # Overbet spots (polarized situations)
    if nut_ratio > 2.5 and streets_remaining >= 1 and spr > 2:
        sizing = min(1.50, spr / 2)
        return {
            "sizing_pct": sizing,
            "sizing_type": "overbet",
            "reasoning": "Nut advantage extrem — overbet, range polarizat",
        }

    # River decisions
    if streets_remaining == 1:
        if hero_equity > 0.75:
            sizing = min(spr, 1.0)  # All-in or pot
            return {
                "sizing_pct": sizing,
                "sizing_type": "all_in",
                "reasoning": "River cu nuts — all-in pentru value maxim",
            }
        elif hero_equity > 0.60:
            return {
                "sizing_pct": 0.66,
                "sizing_type": "value",
                "reasoning": "River value bet standard",
            }
        elif hero_equity < 0.35 and blockers_boost > 1.2:
            return {
                "sizing_pct": 0.75,
                "sizing_type": "bluff",
                "reasoning": f"River bluff cu blocanți ({int((blockers_boost-1)*100)}% boost)",
            }
        else:
            return {
                "sizing_pct": 0,
                "sizing_type": "check",
                "reasoning": "River — fără value sau bluff, check",
            }

    # Multi-street geometric planning
    if range_adv == "hero" and hero_equity > 0.55:
        plan = geometric_sizing_plan(100, 7.5, streets_remaining)
        geo = plan[0]["bet_pot_pct"] if plan else 0.55

        # Adjust for texture
        if wetness == "dry":
            geo *= 0.6  # Smaller on dry
        elif wetness == "wet":
            geo *= 1.2  # Larger on wet

        geo = max(0.33, min(1.0, geo))
        return {
            "sizing_pct": geo,
            "sizing_type": "geometric",
            "reasoning": f"Plan geometric pe {streets_remaining} străzi, ajustat pentru {wetness}",
        }

    # Default by texture
    if wetness == "dry" or paired:
        return {"sizing_pct": 0.33, "sizing_type": "small", "reasoning": "Board uscat — c-bet mic"}
    elif wetness == "wet":
        if hero_equity > 0.50:
            return {"sizing_pct": 0.66, "sizing_type": "large", "reasoning": "Board umed — protejează equity"}
        else:
            return {"sizing_pct": 0, "sizing_type": "check", "reasoning": "Board umed, equity slabă — check"}
    else:
        return {"sizing_pct": 0.50, "sizing_type": "standard", "reasoning": "Semi-dry — sizing standard"}


def geometric_all_in_sizing(stack, pot, streets):
    """Simple wrapper: return the geometric bet % for N streets."""
    plan = geometric_sizing_plan(stack, pot, streets)
    return plan[0]["bet_pot_pct"] if plan else 0.75
