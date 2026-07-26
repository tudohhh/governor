"""
Advanced tests for NL100 postflop engine.
Tests: blockers, range narrowing, sizing, equity tables, opponent HUD.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from treys import Card
from board_analyzer import analyze_flop
from equity import all_cards, remove_cards
from equity_tables import lookup_equity, find_closest_texture, get_equity_table
from blockers import count_blocked_combos, bluff_equity_boost, key_blockers, blocker_effect_summary
from board_texture_advanced import range_advantage, nut_advantage
from sizing import calculate_spr, geometric_sizing_plan, recommend_sizing
from range_narrowing import (narrow_after_flop_call, narrow_after_turn_call,
                              estimate_villain_equity_distribution, initial_range)
from opponent_hud import OpponentTracker, PROFILES
from postflop import PostflopEngine, create_engine

random.seed(42)

def test_equity_tables():
    """Test precomputed equity tables."""
    print("\n=== Equity Tables ===")
    eq = lookup_equity("AKs", "K72r", "BTN")
    assert eq is not None
    assert 0.65 < eq < 0.95, f"AKs on K72r vs BTN should be 65-95%, got {eq:.1%}"
    print(f"  AKs on K72r vs BTN: {eq:.1%} PASS")

    eq2 = lookup_equity("AA", "K72r", "BTN")
    assert eq2 is not None
    assert eq2 > 0.70, f"AA should dominate K72r, got {eq2:.1%}"
    print(f"  AA on K72r vs BTN: {eq2:.1%} PASS")
    print("  Equity tables: PASSED")


def test_blockers():
    """Test blocker analysis."""
    print("\n=== Blockers ===")
    hero = (Card.new("As"), Card.new("Kh"))
    board = [Card.new("Ks"), Card.new("7s"), Card.new("2d")]
    vrange = ["AA", "KK", "AKs", "AKo", "KQs"]

    info = count_blocked_combos(hero, vrange, board)
    assert info["block_percent"] > 5, f"Expected some blocking, got {info['block_percent']}%"
    print(f"  AK on Ks7s2d: blocks {info['block_percent']}%, remaining {info['remaining_combos']}/{info['total_combos']}")

    boost = bluff_equity_boost(hero, vrange, board)
    assert boost >= 1.0
    print(f"  Bluff boost: {boost}x")

    kb = key_blockers(hero, board)
    print(f"  Key blockers: {kb}")
    assert len(kb) > 0, "Should have at least one blocker type"

    summary = blocker_effect_summary(hero, vrange, board)
    print(f"  Summary: {summary}")
    print("  Blockers: PASSED")


def test_range_advantage():
    """Test range advantage calculation."""
    print("\n=== Range Advantage ===")
    board = [Card.new("As"), Card.new("Ks"), Card.new("Td")]
    ra = range_advantage("UTG", "BB", board)
    assert ra == "hero", f"UTG should have advantage on AKT, got {ra}"
    print(f"  AKT board UTG vs BB: advantage = {ra} PASS")

    board = [Card.new("7s"), Card.new("6h"), Card.new("2d")]
    ra = range_advantage("BTN", "UTG", board)
    print(f"  762 board BTN vs UTG: advantage = {ra} PASS")

    nut = nut_advantage(["AA","KK","AK"], ["QQ","JJ","TT"], board[:3])
    print(f"  Nut ratio: {nut:.2f} PASS")
    print("  Range advantage: PASSED")


def test_sizing():
    """Test geometric sizing."""
    print("\n=== Geometric Sizing ===")
    spr = calculate_spr(100, 7.5)
    assert abs(spr - 13.33) < 0.2, f"SPR should be ~13.3, got {spr:.1f}"
    print(f"  SPR (100/7.5): {spr:.1f} PASS")

    plan = geometric_sizing_plan(100, 7.5, 3)
    assert len(plan) == 3
    print(f"  3-street plan: {plan[0]['bet_pot_pct']*100:.0f}% / {plan[1]['bet_pot_pct']*100:.0f}% / {plan[2]['bet_pot_pct']*100:.0f}%")
    all_in = plan[2]["stack_remaining"]
    assert all_in < 5, f"Should be nearly all-in by river, remaining {all_in}"
    print(f"  Stack remaining after river: {all_in:.1f}BB PASS")

    flop = analyze_flop([Card.new("Ks"), Card.new("7h"), Card.new("2d")])
    rec = recommend_sizing(flop, spr, 3, 0.55, "hero", 1.5, 1.2, "IP")
    assert rec["sizing_pct"] > 0, "Should recommend a bet"
    print(f"  Sizing rec (equity 55%, hero adv): {rec['sizing_type']} {rec['sizing_pct']*100:.0f}%")
    print("  Sizing: PASSED")


def test_range_narrowing():
    """Test range narrowing logic."""
    print("\n=== Range Narrowing ===")
    vrange = initial_range("BB")
    print(f"  Initial BB range: {len(vrange)} combos")

    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]
    narrowed = narrow_after_flop_call(vrange, board)
    assert len(narrowed) <= len(vrange), "Narrowed should be <= original"
    print(f"  After flop call on K72: {len(narrowed)} combos (was {len(vrange)})")

    board_turn = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("8c")]
    narrowed2 = narrow_after_turn_call(narrowed, board_turn)
    assert len(narrowed2) <= len(narrowed)
    print(f"  After turn call on K728: {len(narrowed2)} combos")

    dist = estimate_villain_equity_distribution(narrowed2, board_turn)
    print(f"  Equity distribution: strong={dist['strong']}% medium={dist['medium']}% weak={dist['weak']}%")
    print("  Range narrowing: PASSED")


def test_opponent_hud():
    """Test opponent tracking."""
    print("\n=== Opponent HUD ===")
    tracker = OpponentTracker("nit")
    assert abs(tracker.fold_to_cbet - 0.68) < 0.01
    print(f"  Nit fold_to_cbet: {tracker.fold_to_cbet:.0%} PASS")

    # Simulate session
    for _ in range(5):
        tracker.observe_fold_to_cbet()
    tracker.observe_call_cbet()
    print(f"  After 5 folds + 1 call: fold_to_cbet = {tracker.fold_to_cbet:.0%}")
    print(f"  Summary: {tracker.summary()}")

    assert PROFILES["standard"]["vpip"] == 22
    assert PROFILES["lag"]["threebet"] == 12
    assert PROFILES["fish"]["pfr"] == 8
    print("  All profiles valid PASS")
    print("  Opponent HUD: PASSED")


def test_integration():
    """Integration test: full hand simulation."""
    print("\n=== Integration: Full Hand ===")
    random.seed(123)
    hero = (Card.new("As"), Card.new("Ks"))
    vrange = initial_range("BB")
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]

    engine = PostflopEngine(hero, vrange, position="IP", hero_position="BTN",
                             villain_position="BB", opponent_type="standard")

    flop_result = engine.decide_flop(board)
    assert "action" in flop_result and "reasoning" in flop_result
    print(f"  Flop K72: {flop_result['action']} — {flop_result['reasoning'][:70]}")
    print(f"  Equity: {flop_result['equity_str']}, Range adv: {flop_result['range_advantage']}")
    print(f"  Blockers: {flop_result['blockers']}")

    board_turn = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("8c")]
    turn_result = engine.decide_turn(board_turn, flop_action="BET")
    print(f"  Turn 8c: {turn_result['action']} — {turn_result.get('reasoning', '')[:70]}")

    board_river = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("8c"), Card.new("3h")]
    river_result = engine.decide_river(board_river, action_history=["BET", "BET"])
    print(f"  River 3h: {river_result['action']} — {river_result.get('reasoning', '')[:70]}")

    if "villain_distribution" in river_result:
        print(f"  Villain range: {river_result['villain_distribution']}")

    print("  Integration: PASSED")


def test_create_engine():
    """Test engine factory."""
    print("\n=== Engine Factory ===")
    random.seed(42)
    engine = create_engine("AKs", villain_position="BB", hero_position="BTN",
                            opponent_type="standard")
    assert engine.hero_cards is not None
    assert engine.position == "IP"
    assert engine.opponent_type == "standard"
    print(f"  Created engine: {engine.hero_position} vs {engine.villain_position} {engine.position}")

    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]
    result = engine.decide_flop(board)
    print(f"  AKs on K72: {result['action']} {result.get('sizing_bb', '')}BB")
    print(f"  Opponent: {engine.get_opponent_summary()}")
    print("  Engine factory: PASSED")


if __name__ == "__main__":
    test_equity_tables()
    test_blockers()
    test_range_advantage()
    test_sizing()
    test_range_narrowing()
    test_opponent_hud()
    test_integration()
    test_create_engine()
    print("\n" + "=" * 50)
    print("ALL ADVANCED TESTS PASSED")
    print("=" * 50)
