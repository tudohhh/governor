"""
Complete test suite v2 — real CFR solver, proper ICM, fixed multiway,
redesigned frequency drill, improved leak finder, compact range viz.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from treys import Card
from solver import RiverGame, cfr, CFRNode
from multiway import multiway_equity, multiway_decision, multiway_fold_equity
from hh_parser import parse_pokerstars, analyze_hand
from icm import icm_equity, icm_push_fold, tournament_stage_adjustment
from trainer_advanced import FrequencyDrill, LeakFinder, HandReviewer
from viz_range import range_to_grid, grid_to_html, range_stats, combo_to_grid_position
from range_narrowing import initial_range

random.seed(42)


def test_real_cfr():
    """Test the real CFR solver."""
    print("\n=== Real CFR Solver ===")
    game = RiverGame(pot=10, stack=50, hero_equity=0.72, ip=True)
    result = game.solve(iterations=500)
    assert "strategy" in result
    assert len(result["strategy"]) > 0
    print(f"  River eq=72% SPR=5: {result['strategy']}")
    print(f"  Explanation: {result['explanation']}")
    # Should recommend some betting with 72% equity
    strat = result["strategy"]
    bet_actions = [k for k in strat if "bet" in k]
    assert len(bet_actions) > 0 or strat.get("check", 0) < 0.5, "Should bet with 72% equity"
    print("  Real CFR: PASSED")

    # Low equity scenario
    game2 = RiverGame(pot=10, stack=50, hero_equity=0.22, ip=True)
    result2 = game2.solve(iterations=500)
    print(f"  River eq=22% SPR=5: {result2['strategy']}")
    check_freq = result2["strategy"].get("check", 0)
    assert check_freq > 0.3, f"Should mostly check with 22% equity, check={check_freq}"
    print("  Real CFR equity 22%: PASSED")


def test_icm_real():
    """Test the real ICM implementation."""
    print("\n=== Real ICM ===")

    # Standard 4-player payout
    stacks = [1000, 800, 600, 400]
    payouts = [0.5, 0.3, 0.2, 0.0]
    eqs = icm_equity(stacks, payouts)
    print(f"  ICM: {[round(e, 3) for e in eqs]}")

    # Basic sanity: more chips = more equity
    assert eqs[0] > eqs[1] > eqs[2], f"Expected decreasing equity: {eqs}"
    # Chip leader should have 30-35% with 1000/2800 = 35.7% chips
    assert 0.30 < eqs[0] < 0.38, f"Chip leader too far off: {eqs[0]:.3f}"
    print(f"  Chip leader 1000/2800: {eqs[0]:.1%} ICM equity (raw: 35.7%)")

    # Push/fold test
    result = icm_push_fold([500, 700, 800, 1000], [50, 100], payouts, 0.58, "SB")
    print(f"  Push/fold 10BB: {result['action']} EV diff={result['ev_diff']:.4f} risk={result.get('risk_premium',0):.4f}")

    # Tournament stage
    stage = tournament_stage_adjustment([1500, 2000, 1800, 1200], [100, 200], payouts)
    print(f"  Stage: {stage['stage']} | open: {stage['open_size']} | hero: {stage['hero_bb']}BB")
    assert "stage" in stage
    print("  Real ICM: PASSED")


def test_multiway_fixed():
    """Test fixed multiway equity."""
    print("\n=== Multiway Fixed ===")
    hero = (Card.new("As"), Card.new("Kh"))
    vrange1 = ["AA","KK","QQ","JJ","AK","AQ"]
    vrange2 = ["TT","99","88","KQs","AJs"]
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]

    eq = multiway_equity(hero, [vrange1, vrange2], board, trials=300)
    print(f"  AK on K72 3-way: {eq:.1%}")
    assert 0.20 < eq < 0.80, f"Equity out of range: {eq:.1%}"
    # Should NOT be exactly 0.5
    assert eq != 0.5, "Equity stuck at default 0.5"

    fe = multiway_fold_equity([0.55, 0.60])
    assert abs(fe - 0.33) < 0.01, f"Fold equity should be 33%, got {fe}"
    print(f"  Fold equity 2 opp: {fe:.1%}")

    result = multiway_decision(hero, [vrange1, vrange2], board, [0.55, 0.60])
    print(f"  3-way decision: {result['action']}")
    assert result["num_opponents"] == 2
    print("  Multiway: PASSED")


def test_frequency_drill_v2():
    """Test redesigned frequency drill."""
    print("\n=== Frequency Drill v2 ===")
    drill = FrequencyDrill(num_scenarios=5)
    scenario = drill.generate()
    assert scenario is not None
    print(f"  First scenario: {scenario['texture']} eq={scenario['equity']:.1%} gto={scenario['gto_action']}")
    print(f"  Total scenarios generated: {len(drill.scenarios)}")

    # Record varied responses
    for i in range(len(drill.scenarios)):
        sc = drill.current_scenario()
        if sc is None:
            break
        action = "BET" if i < 3 else "CHECK"
        drill.record(action)

    results = drill.results()
    print(f"  Score: {results['score']:.2f}, Alt: {results['alternation_score']:.2f}")
    print(f"  Bet actual/expected: {results['bet_actual']:.2f}/{results['bet_expected']:.2f}")
    assert results["total"] > 0
    print("  Frequency drill: PASSED")


def test_leak_finder_real():
    """Test leak finder with real patterns."""
    print("\n=== Leak Finder ===")
    lf = LeakFinder()

    # Simulate over-cbetting session: hero cbets 90% on flop
    for _ in range(15):
        lf.add_decision({"street": "flop", "aggressor": "hero", "action": "bet", "sizing": 0.33})
    lf.add_decision({"street": "flop", "aggressor": "hero", "action": "check"})

    # Fold too much to cbets
    for _ in range(8):
        lf.add_decision({"street": "flop", "aggressor": "villain", "action": "fold"})

    # No check-raises
    for _ in range(20):
        lf.add_decision({"street": "flop", "aggressor": "villain", "action": "call"})

    result = lf.analyze()
    print(f"  Leaks: {result['leaks_count']} in {result['total']} decisions")
    for leak in result["leaks"]:
        print(f"  - [{leak['severity']}] {leak['type']}")
    # Should find cbet too high and fold too much
    assert result["leaks_count"] >= 2, f"Expected at least 2 leaks, got {result['leaks_count']}"
    print("  Leak finder: PASSED")


def test_compact_viz():
    """Test compact range visualizer."""
    print("\n=== Compact Range Viz ===")
    rng = set(initial_range("BTN"))
    html = grid_to_html(rng, "BTN Range")
    print(f"  HTML size: {len(html)} chars (was ~23K)")
    assert len(html) < 8000, f"HTML should be compact, got {len(html)} chars"
    assert "rg-table" in html
    assert "@media" in html  # Light mode support
    print("  Compact, light+dark: PASSED")

    stats = range_stats(rng)
    print(f"  {stats['total_combos']} combos, {stats['range_pct']}% of hands")
    print("  Range viz: PASSED")


if __name__ == "__main__":
    test_real_cfr()
    test_icm_real()
    test_multiway_fixed()
    test_frequency_drill_v2()
    test_leak_finder_real()
    test_compact_viz()
    print("\n" + "=" * 50)
    print("ALL FIXED TESTS PASSED")
    print("=" * 50)
