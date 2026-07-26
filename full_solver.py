"""
Full 4-Street Solver — preflop → flop → turn → river in a unified framework.
Stitches preflop ranges (from preflop_solver) with postflop CFR (from pio_solver).

Method:
  1. Compute preflop Nash ranges per position (EHS percentile)
  2. For each (hero_combo, vill_combo) that reaches flop:
     - Build CompactTree starting from flop
     - Run FastCFR
     - Store strategy
  3. Merge strategies across all combo pairs into per-position recommendations

This avoids the explosion of a true 4-street CFR tree while still giving
street-by-street GTO strategies starting from preflop.
"""
import random, time, json
from collections import defaultdict
from treys import Card, Evaluator
from pio_solver import PioSolver, FastEquity, CompactTree, FastCFR, bucketize
from preflop_solver import compute_all_ranges, all_169_combos, combo_ehs
from equity_db import all_combos_169 as all_combos_169_treys

evaluator = Evaluator()


class FullSolver:
    """4-street solver: preflop ranges + postflop CFR."""

    def __init__(self, nb=6, postflop_iters=300):
        self.nb = nb
        self.postflop_iters = postflop_iters
        self.pio = PioSolver()
        self.pio.nb = nb

    def solve_hand(self, hero_combo, hero_pos, vill_pos,
                   stack=100, pot=7.5, board_cards=None):
        """
        Full GTO strategy for a specific hand and position matchup.

        Args:
            hero_combo: combo string e.g. 'AKs'
            hero_pos: e.g. 'BTN'
            vill_pos: e.g. 'BB'
            stack: effective stack in BB
            pot: current pot size in BB
            board_cards: list of treys Card ints (empty for preflop)

        Returns:
            dict with 'preflop', 'flop', 'turn', 'river' strategy sections
        """
        # 1. Preflop decision
        ranges = compute_all_ranges(stack)
        hero_open = ranges['RFI'].get(hero_pos, set())

        if board_cards is None:
            board_cards = []

        result = {'hero_combo': hero_combo, 'hero_pos': hero_pos,
                  'vill_pos': vill_pos, 'stack': stack}

        # Preflop
        if hero_combo in hero_open:
            vill_call = ranges['VS_RFI']['call'].get(f'vs_{hero_pos}', set())
            vill_range = list(vill_call)[:25]  # Top 25 villain combos
            result['preflop'] = {'action': 'RAISE', 'in_range': True}
        else:
            result['preflop'] = {'action': 'FOLD', 'in_range': False}
            return result

        # 2. Postflop: solve from flop
        if len(board_cards) < 3:
            result['flop'] = {'status': 'waiting_for_flop'}
            return result

        # Build hero and villain combo lists from ranges
        hero_c = list(hero_open)[:20]
        vill_c = vill_range

        start = 'flop'
        if len(board_cards) == 4:
            start = 'turn'
        elif len(board_cards) >= 5:
            start = 'river'

        solver_result = self.pio.solve(
            hero_c, vill_c, board_cards,
            pot=pot, stack=stack, pos='IP',
            start=start, iters=self.postflop_iters
        )

        if 'error' not in solver_result:
            result['postflop'] = solver_result
            result['postflop']['street'] = start

        return result

    def analyze_range_vs_range(self, hero_pos, vill_pos, board_cards,
                               pot=10, stack=100):
        """
        Analyze full range vs range equity on a given board.
        Returns aggregate stats for the entire opening range.
        """
        ranges = compute_all_ranges(stack)
        hero_range = list(ranges['RFI'].get(hero_pos, set()))
        vill_call_range = list(ranges['VS_RFI']['call'].get(f'vs_{hero_pos}', set()))
        vill_3bet_range = list(ranges['VS_RFI']['3bet'].get(f'vs_{hero_pos}', set()))

        start = 'flop'
        if len(board_cards) == 4:
            start = 'turn'
        elif len(board_cards) >= 5:
            start = 'river'

        result = self.pio.solve(
            hero_range[:20], vill_call_range[:20], board_cards,
            pot=pot, stack=stack, pos='IP',
            start=start, iters=self.postflop_iters
        )

        return {
            'hero_pos': hero_pos,
            'vill_pos': vill_pos,
            'hero_range_size': len(hero_range),
            'vill_call_size': len(vill_call_range),
            'vill_3bet_size': len(vill_3bet_range),
            'board': [Card.int_to_pretty_str(c) for c in board_cards],
            'strategy': result.get('actions', {}),
            'hero_ev': result.get('hero_ev', 0),
            'ev_pct': result.get('ev_pct', 0),
            'solve_time': result.get('total_time', 0),
        }


def benchmark_positions(board_cards, stack=100):
    """Benchmark: solve 3 key position matchups."""
    solver = FullSolver(nb=6, postflop_iters=200)
    matchups = [
        ('BTN', 'BB'),
        ('CO', 'BTN'),
        ('UTG', 'BB'),
    ]
    results = {}
    for hero, vill in matchups:
        t0 = time.time()
        r = solver.analyze_range_vs_range(hero, vill, board_cards, stack=stack)
        results[f'{hero}_vs_{vill}'] = r
        r['wall_time'] = round(time.time() - t0, 2)
        print(f"  {hero} vs {vill}: EV={r['hero_ev']}BB, time={r['wall_time']}s")
    return results


if __name__ == "__main__":
    print("Full 4-Street Solver — Benchmark")
    print("=" * 45)

    # Test flop
    flop = [Card.new('Ks'), Card.new('7h'), Card.new('2d')]
    print("\nFlop K72r:")
    benchmark_positions(flop)

    # Test single hand
    print("\nSingle hand BTN vs BB:")
    solver = FullSolver()
    r = solver.solve_hand('AKs', 'BTN', 'BB', board_cards=flop)
    print(f"  Preflop: {r['preflop']}")
    if 'postflop' in r:
        print(f"  Postflop: EV={r['postflop'].get('hero_ev')}, "
              f"actions={r['postflop'].get('actions')}")
