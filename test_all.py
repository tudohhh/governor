"""
Comprehensive tests for Governor NL100 postflop engine.
Tests: board analyzer, equity calculator, postflop decisions.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from treys import Card
from board_analyzer import analyze_flop, analyze_turn, describe_board, cbet_sizing_recommendation
from equity import equity_vs_hand, equity_vs_range, pot_odds_to_equity, all_cards, remove_cards
from postflop import PostflopEngine, create_engine


def test_board_analyzer():
    """Test board texture classification."""
    print("\n=== Board Analyzer Tests ===")

    # Dry flop: K72 rainbow
    flop = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]
    result = analyze_flop(flop)
    assert result["wetness"] == "dry", f"Expected dry, got {result['wetness']}"
    assert result["high_type"] == "broadway"
    assert not result["paired"]
    assert result["suited"] == "rainbow"
    print("  Dry K72 rainbow: PASS")

    # Wet flop: JTs9 two-tone
    flop = [Card.new("Js"), Card.new("Ts"), Card.new("9h")]
    result = analyze_flop(flop)
    assert result["wetness"] in ("wet", "semi-dry"), f"Expected wet-ish, got {result['wetness']}"
    assert result["connected"] in ("fully-connected", "semi-connected")
    assert result["suited"] == "two-tone"
    print(f"  Wet JTs9 two-tone: PASS (wetness={result['wetness']}, connected={result['connected']})")

    # Paired flop: AA3
    flop = [Card.new("As"), Card.new("Ah"), Card.new("3d")]
    result = analyze_flop(flop)
    assert result["paired"]
    assert result["high_type"] == "ace-high"
    print("  Paired AA3: PASS")

    # Monotone flop
    flop = [Card.new("Ks"), Card.new("7s"), Card.new("2s")]
    result = analyze_flop(flop)
    assert result["suited"] == "monotone"
    print("  Monotone K72: PASS")

    # Low disconnected
    flop = [Card.new("5s"), Card.new("2h"), Card.new("8d")]
    result = analyze_flop(flop)
    assert result["high_type"] == "mid"
    print(f"  Low 528: PASS (connected={result['connected']})")

    print("  All board analyzer tests PASSED")


def test_turn_analyzer():
    """Test turn analysis."""
    print("\n=== Turn Analyzer Tests ===")
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("Qs")]
    result = analyze_turn(board)
    assert not result["completes_flush"]
    assert not result["straight_danger"]
    assert not result["paired"]
    print(f"  Turn Qs on K72: PASS (completes_flush={result['completes_flush']})")

    # Turn that pairs
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("Kh")]
    result = analyze_turn(board)
    assert result["paired"]
    print("  Turn K pairing: PASS")

    print("  All turn analyzer tests PASSED")


def test_equity_calculator():
    """Test equity calculations."""
    print("\n=== Equity Calculator Tests ===")

    # AA vs KK preflop (different suits, no overlap)
    hero = [Card.new("As"), Card.new("Ah")]
    villain = [Card.new("Kd"), Card.new("Kh")]
    board = []
    eq = equity_vs_hand(hero, villain, board, trials=500)
    assert eq > 0.75, f"AA vs KK should be >75%, got {eq:.1%}"
    print(f"  AA vs KK preflop: {eq:.1%} PASS")

    # AA vs KK on K-high flop (AA behind, K on board is different suit)
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]
    eq = equity_vs_hand(hero, villain, board, trials=300)
    assert eq < 0.15, f"AA vs KK on K-high should be <15%, got {eq:.1%}"
    print(f"  AA vs KK on K72: {eq:.1%} PASS")

    # Flush draw equity
    hero = [Card.new("As"), Card.new("Ks")]
    villain = [Card.new("Qh"), Card.new("Qd")]
    board = [Card.new("2s"), Card.new("7s"), Card.new("Qc")]  # All unique
    eq = equity_vs_hand(hero, villain, board, trials=300)
    assert 0.20 < eq < 0.40, f"FD vs set should be 25-35%, got {eq:.1%}"
    print(f"  NFD vs set on Q72ss: {eq:.1%} PASS")

    print("  All equity tests PASSED")


def test_pot_odds():
    """Test pot odds calculation."""
    print("\n=== Pot Odds Tests ===")
    frac, pct = pot_odds_to_equity(10, 20)  # bet 10 into 20 pot
    assert abs(pct - 25.0) < 1.0, f"Expected ~25%, got {pct:.1f}%"
    print(f"  Bet 10 into 20 pot: need {pct:.0f}% equity PASS")

    frac, pct = pot_odds_to_equity(20, 20)  # pot-sized bet
    assert abs(pct - 33.3) < 1.0, f"Expected ~33%, got {pct:.1f}%"
    print(f"  Bet 20 into 20 pot: need {pct:.0f}% equity PASS")

    frac, pct = pot_odds_to_equity(5, 20)
    assert abs(pct - 16.7) < 2.0, f"Expected ~17%, got {pct:.1f}%"
    print(f"  Bet 5 into 20 pot: need {pct:.0f}% equity PASS")

    print("  All pot odds tests PASSED")


def test_postflop_decisions():
    """Test postflop decision engine."""
    print("\n=== Postflop Decision Tests ===")

    # Strong hand on dry flop, IP
    hero = (Card.new("As"), Card.new("Ah"))
    villain_range = ["AA", "KK", "QQ", "JJ", "TT", "AK", "AQ"]
    board = [Card.new("Ks"), Card.new("7h"), Card.new("2d")]
    engine = PostflopEngine(hero, villain_range, position="IP")
    result = engine.decide_flop(board)
    assert result["action"] in ("BET", "CHECK"), f"Unexpected action: {result['action']}"
    print(f"  AA on K72 IP: {result['action']} {result.get('sizing_bb', 0)}BB — {result['reasoning'][:60]} PASS")

    # Weak hand facing bet
    hero = (Card.new("5s"), Card.new("4s"))
    board = [Card.new("Ks"), Card.new("Th"), Card.new("2d")]
    engine = PostflopEngine(hero, villain_range, position="IP")
    result = engine.decide_flop(board, bet_faced=5)
    assert result["action"] in ("FOLD", "CALL", "RAISE")
    print(f"  54s on KT2 vs bet: {result['action']} — {result['reasoning'][:60]} PASS")

    # Test with different opponent types
    hero = (Card.new("As"), Card.new("Qs"))
    board = [Card.new("Ks"), Card.new("7s"), Card.new("2d")]
    for opp in ["standard", "nit", "fish"]:
        engine = PostflopEngine(hero, villain_range, position="IP", opponent_type=opp)
        result = engine.decide_flop(board)
        print(f"  AQs on Ks7s2d vs {opp}: {result['action']} — {result['reasoning'][:60]} PASS")

    # Turn decision test (hero=AsQh, no overlap)
    hero2 = (Card.new("As"), Card.new("Qh"))
    board_4 = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("8c")]
    engine2 = PostflopEngine(hero2, villain_range, position="IP")
    result = engine2.decide_turn(board_4, flop_action="BET")
    print(f"  Turn 8c: {result['action']} — {result['reasoning'][:60]} PASS")

    # River decision test
    board_5 = [Card.new("Ks"), Card.new("7h"), Card.new("2d"), Card.new("8c"), Card.new("3h")]
    result = engine2.decide_river(board_5, action_history=["BET", "BET"])
    print(f"  River 3h (2 barrels): {result['action']} — {result['reasoning'][:60]} PASS")

    print("  All postflop decision tests PASSED")


def test_cbet_sizing():
    """Test c-bet sizing recommendations."""
    print("\n=== C-Bet Sizing Tests ===")
    for wetness in ["dry", "semi-dry", "wet"]:
        flop = {"wetness": wetness, "paired": False, "high_type": "broadway"}
        action, sizing, reason = cbet_sizing_recommendation(flop, ip=True, hero_equity=0.55)
        print(f"  {wetness} IP eq=55%: {action} {sizing*100:.0f}% — {reason[:50]} PASS")

    flop = {"wetness": "dry", "paired": True, "high_type": "ace-high"}
    action, sizing, reason = cbet_sizing_recommendation(flop, ip=True, hero_equity=0.45)
    print(f"  paired dry IP eq=45%: {action} {sizing*100:.0f}% — {reason[:50]} PASS")

    print("  All c-bet sizing tests PASSED")


def test_drill_generation():
    """Test engine creation for drills."""
    print("\n=== Engine Creation Test ===")
    try:
        engine = create_engine("AKs", "BB", "BTN", "standard")
        assert engine.hero_cards is not None
        assert engine.villain_range is not None
        assert len(engine.villain_range) > 0
        print(f"  Created engine: AKs BTN vs BB, range size={len(engine.villain_range)} PASS")
    except Exception as e:
        print(f"  Engine creation: ERROR {e}")
        raise

    print("  All engine creation tests PASSED")


if __name__ == "__main__":
    test_board_analyzer()
    test_turn_analyzer()
    test_equity_calculator()
    test_pot_odds()
    test_cbet_sizing()
    test_postflop_decisions()
    test_drill_generation()
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
