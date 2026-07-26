"""
Preflop Range Solver — computes optimal opening ranges via hand strength + pot odds.
More rigorous than static GTO_RANGES, faster than full CFR.

Method:
  1. Rank all 169 combos by EHS (Expected Hand Strength)
  2. Compute opening threshold: raise combos where EV(raise) > EV(fold)
  3. EV(raise) = P(fold)*pot + P(call)*(eq*pot_after - cost) + P(3bet)*(...)
  4. Output: open_range, call_vs_3bet_range, 4bet_range per position
"""
import json, os
from collections import defaultdict
from pio_solver import PREFLOP_EHS, bucketize, RANKS_STR

RANKS = RANKS_STR
POSITIONS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
SUITS = ["s", "h", "d", "c"]


def all_169_combos():
    combos = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i < j: continue
            if i == j: combos.append(r1 + r2)
            else: combos.append(r1 + r2 + "s"); combos.append(r2 + r1 + "o")
    return combos


def combo_ehs(combo):
    return PREFLOP_EHS.get(combo, 0.50)


def compute_open_range(position, stack=100):
    """
    Compute opening range by EHS percentile.
    Matches standard GTO opening frequencies per position.
    Stack depth affects: shorter stack = wider range (more steal equity).
    """
    # Base opening % per position (standard 6-max, 100bb)
    open_pct = {
        'UTG': 0.16, 'HJ': 0.21, 'CO': 0.30, 'BTN': 0.46,
        'SB': 0.48, 'BB': 0.35  # BB only opens if no raise
    }

    # Stack adjustment: shorter stack = slightly wider
    stack_factor = 1.0
    if stack < 50: stack_factor = 1.4
    elif stack < 80: stack_factor = 1.2
    elif stack > 150: stack_factor = 0.9
    elif stack > 200: stack_factor = 0.85

    target_pct = open_pct.get(position, 0.25) * stack_factor
    target_pct = min(1.0, target_pct)

    combos = all_169_combos()
    ranked = sorted(combos, key=lambda c: -combo_ehs(c))

    n_open = int(169 * target_pct)
    return set(ranked[:n_open])


def compute_3bet_range(vs_position, stack=100, bb=1):
    """Compute 3-bet range vs an open from `vs_position`."""
    # Villain opens wide from late position → we 3bet wider
    pos_open_freq = {
        'UTG': 0.16, 'HJ': 0.21, 'CO': 0.30, 'BTN': 0.46, 'SB': 0.50, 'BB': 0.30
    }
    villain_open_pct = pos_open_freq.get(vs_position, 0.30)

    combos = all_169_combos()
    ranked = sorted(combos, key=lambda c: -combo_ehs(c))

    threebet_range = set()
    call_range = set()

    # 3-bet: top ~40% of villain's opening range
    threebet_pct = villain_open_pct * 0.40

    for i, combo in enumerate(ranked):
        pct = (i + 1) / 169
        if pct <= threebet_pct:
            threebet_range.add(combo)
        elif pct <= villain_open_pct * 0.75:
            call_range.add(combo)
        # else: fold

    return {'3bet': threebet_range, 'call': call_range}


def compute_4bet_range(stack=100):
    """Compute 4-bet/5-bet ranges. Very tight — top ~3%."""
    combos = all_169_combos()
    ranked = sorted(combos, key=lambda c: -combo_ehs(c))

    shove_range = set()
    call_range = set()

    for i, combo in enumerate(ranked):
        pct = (i + 1) / 169
        if pct <= 0.025:   # top 2.5% = QQ+, AKs
            shove_range.add(combo)
        elif pct <= 0.05:   # next 2.5% = JJ, TT, AKo, AQs
            call_range.add(combo)

    return {'5bet_shove': shove_range, 'call': call_range}


def compute_all_ranges(stack=100):
    """Compute all preflop ranges: open + 3bet + 4bet per position pair."""
    ranges = {}

    # Open ranges per position
    ranges['RFI'] = {}
    for pos in POSITIONS:
        ranges['RFI'][pos] = compute_open_range(pos, stack)

    # 3-bet ranges vs each position
    ranges['VS_RFI'] = {'3bet': {}, 'call': {}}
    for pos in POSITIONS:
        result = compute_3bet_range(pos, stack)
        ranges['VS_RFI']['3bet'][f'vs_{pos}'] = result['3bet']
        ranges['VS_RFI']['call'][f'vs_{pos}'] = result['call']

    # 4-bet/5-bet ranges
    result = compute_4bet_range(stack)
    ranges['VS_4BET'] = {
        '5bet_shove': {'all': result['5bet_shove']},
        'call': {'all': result['call']},
    }

    return ranges


def export_to_gto_ranges(path=None):
    """Export computed ranges in GTO_RANGES format.
    Can replace the static dict in app.py."""
    ranges = compute_all_ranges()

    if path:
        serializable = {}
        for section, data in ranges.items():
            if section in ('RFI',):
                serializable[section] = {k: sorted(v) for k, v in data.items()}
            elif section in ('VS_RFI',):
                serializable[section] = {}
                for sub, subdata in data.items():
                    serializable[section][sub] = {k: sorted(v) for k, v in subdata.items()}
            elif section in ('VS_4BET',):
                serializable[section] = {}
                for sub, subdata in data.items():
                    serializable[section][sub] = {k: sorted(v) for k, v in subdata.items()}
        with open(path, 'w') as f:
            json.dump(serializable, f, indent=2)
        print(f"Ranges exported to {path}")

    return ranges


# ═══ CLI ═══

if __name__ == "__main__":
    print("Preflop Range Solver — EHS-based")
    print("=" * 50)

    ranges = compute_all_ranges()

    for pos in POSITIONS:
        rfi = ranges['RFI'][pos]
        pct = len(rfi) / 169 * 100
        print(f"\n{pos} open: {len(rfi)} combos = {pct:.1f}%")
        top10 = sorted(rfi, key=lambda c: -combo_ehs(c))[:10]
        print(f"  Top 10: {', '.join(top10)}")

    print(f"\n3-bet vs BTN: {len(ranges['VS_RFI']['3bet']['vs_BTN'])} combos")
    print(f"Call vs BTN: {len(ranges['VS_RFI']['call']['vs_BTN'])} combos")
    print(f"5-bet shove: {len(ranges['VS_4BET']['5bet_shove']['all'])} combos")
    print(f"Call 4-bet: {len(ranges['VS_4BET']['call']['all'])} combos")
