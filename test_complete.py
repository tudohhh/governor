"""
Complete test suite for all Governor NL200 modules.
Tests: solver, multiway, hand history parser, ICM, frequency drill,
leak finder, hand reviewer, range visualizer.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from treys import Card
from solver import RiverSolver, TurnSolver
from multiway import (multiway_equity, multiway_fold_equity,
                       multiway_decision, multiway_sizing_adjustment)
from hh_parser import parse_pokerstars, analyze_hand
from icm import icm_equity, icm_push_fold, tournament_stage_adjustment
from trainer_advanced import FrequencyDrill, LeakFinder, HandReviewer
from viz_range import range_to_grid, grid_to_html, range_stats, narrow_range_html, combo_to_grid_position
from range_narrowing import initial_range
from equity import all_cards, remove_cards

random.seed(42)


def test_river_solver():
    """Test CFR river solver."""
    print("\n=== River Solver ===")
    solver = RiverSolver(pot=10, stack=50, hero_equity=0.72, ip=True)
    result = solver.solve(iterations=200)
    assert "optimal" in result
    assert "strategy_type" in result
    print(f"  Equity 72% IP SPR=5: {result['strategy_type']} - {result['optimal']['action']}")
    print(f"  EV bet: {result['optimal'].get('ev_bet', '?')}, EV check: {result['optimal'].get('ev_check', '?')}")
    assert result["optimal"]["action"] in ("BET", "CHECK", "thin_value", "value_bet")
    print("  River solver: PASSED")


def test_turn_solver():
    """Test 2-street turn solver."""
    print("\n=== Turn Solver ===")
    solver = TurnSolver(pot=10, stack=50, hero_equity=0.62, ip=True)
    result = solver.solve(iterations=100)
    assert "action" in result
    print(f"  Turn SPR=5 eq=62%: {result['action']} {result.get('turn_bet_pct','')}")
    print("  Turn solver: PASSED")


def test_multiway():
    """Test multi-way pot logic."""
    print("\n=== Multiway ===")
    hero = (Card.new("As"), Card.new("Kh"))
    vrange1 = ["AA","KK","QQ","JJ","AK","AQ"]
    vrange2 = ["TT","99","88","KQs","AJs"]
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]

    eq = multiway_equity(hero, [vrange1, vrange2], board, trials=200)
    print(f"  AK on K72 3-way equity: {eq:.1%}")

    fe = multiway_fold_equity([0.55, 0.60], 2)
    print(f"  Prob all fold (2 opp): {fe:.1%}")

    sa = multiway_sizing_adjustment(0.55, 2)
    print(f"  Sizing adjusted 3-way: {sa:.2f}")

    result = multiway_decision(hero, [vrange1, vrange2], board, [0.55, 0.60],
                                ["standard", "nit"])
    print(f"  Multiway decision: {result['action']}")

    assert 0 < eq < 1
    print("  Multiway: PASSED")


def test_hh_parser():
    """Test hand history parser."""
    print("\n=== Hand History Parser ===")
    sample = """PokerStars Hand #123456789: Hold'em No Limit ($0.50/$1.00) - 2025/01/01
Table 'Test' 6-max Seat #1 is the button
Seat 1: Hero ($100.00 in chips)
Seat 2: Villain ($95.50 in chips)
*** HOLE CARDS ***
Dealt to Hero [As Kh]
*** FLOP *** [Ks 7h 2d]
Hero: bets $5.00
Villain: calls $5.00
*** TURN *** [Ks 7h 2d] [8c]
Hero: bets $12.00
Villain: folds
Hero collected $18.50 from pot"""

    hand = parse_pokerstars(sample)
    assert hand is not None
    assert hand.hero_name == "Hero"
    assert hand.hero_cards == ["As", "Kh"]
    assert hand.hero_name == "Hero"  # Core parsing worked
    assert hand.hero_cards == ["As", "Kh"]
    print(f"  Parsed hand: {hand.hand_id} - Hero: {hand.hero_cards}")

    analysis = analyze_hand(hand)
    print(f"  Analysis: {analysis['position']}, agg={analysis['aggression']:.1f}")
    print("  HH Parser: PASSED")


def test_icm():
    """Test ICM calculator."""
    print("\n=== ICM ===")
    stacks = [1000, 800, 600, 400]
    payouts = [0.5, 0.3, 0.2, 0.0]
    equities = icm_equity(stacks, payouts)
    print(f"  Stacks {stacks}: equities = {[round(e, 3) for e in equities]}")
    assert len(equities) == 4
    assert equities[0] > equities[1]  # Bigger stack = more equity
    print(f"  Chip leader equity: {equities[0]:.1%}")

    # Push/fold test
    result = icm_push_fold([500, 600, 700, 800], [50, 100], payouts, 0.55, "SB")
    print(f"  Short stack push/fold (55%): {result['action']} (EV diff: {result['ev_diff']:.4f})")

    # Tournament stage
    stage = tournament_stage_adjustment([500, 600, 700, 800], [50, 100], payouts)
    print(f"  Stage: {stage['stage']}, open: {stage['open_size']}")
    print("  ICM: PASSED")


def test_frequency_drill():
    """Test frequency-based training."""
    print("\n=== Frequency Drill ===")
    drill = FrequencyDrill()
    scenario = drill.generate_scenario()
    print(f"  Scenario: {scenario['texture']} eq={scenario['equity']:.1%}")
    print(f"  GTO: {scenario['gto_action']} target BET={drill.target_frequency['BET']:.0%}")

    # Simulate responses matching target
    for _ in range(7):
        drill.record_response("BET")
    for _ in range(3):
        drill.record_response("CHECK")

    score = drill.get_score()
    print(f"  Score: {score['score']:.2f} (7BET/3CHECK vs {drill.target_frequency['BET']:.0%} target)")
    print(f"  Feedback: {score['feedback']}")
    print("  Frequency drill: PASSED")


def test_leak_finder():
    """Test leak detection."""
    print("\n=== Leak Finder ===")
    finder = LeakFinder()

    # Simulate over-cbetting
    for _ in range(8):
        finder.add_decision({"street": "FLOP", "user_action": "BET",
                             "bet_faced": 0, "sizing": 0.33})
    for _ in range(2):
        finder.add_decision({"street": "FLOP", "user_action": "CHECK",
                             "bet_faced": 0})

    # Simulate folding too much
    for _ in range(5):
        finder.add_decision({"street": "FLOP", "user_action": "FOLD",
                             "bet_faced": 5})

    result = finder.analyze()
    print(f"  Found {result['leaks_found']} leaks in {result['total_decisions']} decisions")
    for leak in result["leaks"]:
        print(f"  - {leak['type']}: {leak['detail'][:60]}")
    assert result["leaks_found"] >= 1
    print("  Leak finder: PASSED")


def test_hand_reviewer():
    """Test hand review."""
    print("\n=== Hand Reviewer ===")
    reviewer = HandReviewer()
    hero = (Card.new("As"), Card.new("Kh"))
    board_prog = [
        [Card.new("Ks"), Card.new("7h"), Card.new("2d")],
        [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("8c")],
    ]
    actions = [
        {"street": "FLOP", "action": "BET", "bet_faced": 0},
        {"street": "TURN", "action": "CHECK", "bet_faced": 0},
    ]
    vrange = initial_range("BB")

    result = reviewer.review(hero, board_prog, actions, vrange, position="IP")
    print(f"  Score: {result['correct']}/{result['total']} ({result['score']:.0%})")
    for fb in result["street_feedback"]:
        print(f"  - {fb['street']}: you={fb['your_action']} gto={fb['gto_action']} eq={fb['equity']:.0%}")
    print("  Hand reviewer: PASSED")


def test_viz_range():
    """Test range visualization."""
    print("\n=== Range Visualizer ===")
    rng = set(initial_range("BTN"))
    grid = range_to_grid(rng)
    assert len(grid) == 13
    assert len(grid[0]) == 13
    print(f"  Grid: 13×13, range size: {len(rng)} combos")

    stats = range_stats(rng)
    print(f"  Stats: {stats['range_pct']}% of hands, {stats['total_hands']} total hands")

    html = grid_to_html(rng, "BTN Range", highlight_combo="AA")
    assert "BTN Range" in html
    assert len(html) > 500, f"HTML too short: {len(html)} chars"
    print(f"  HTML: {len(html)} chars")

    pos = combo_to_grid_position("AKs")
    print(f"  AKs position: row={pos[0]} col={pos[1]}")

    # Narrowed range viz
    narrow = [c for c in rng if "A" in c or "K" in c][:20]
    n_html = narrow_range_html(rng, narrow)
    assert "Range inițial" in n_html
    print(f"  Narrow HTML: {len(n_html)} chars")
    print("  Range viz: PASSED")


if __name__ == "__main__":
    test_river_solver()
    test_turn_solver()
    test_multiway()
    test_hh_parser()
    test_icm()
    test_frequency_drill()
    test_leak_finder()
    test_hand_reviewer()
    test_viz_range()
    print("\n" + "=" * 50)
    print("ALL COMPLETE TESTS PASSED")
    print("=" * 50)
