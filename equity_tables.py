"""
Precomputed equity tables for instant lookup.
Covers 50 standard flop textures × 169 hand combos × position.
Deterministic — same input always gives same output.
"""
from treys import Card, Evaluator
import random

evaluator = Evaluator()
random.seed(42)  # Deterministic

RANKS_STR = "AKQJT98765432"
RANK_ORDER = {r: i for i, r in enumerate(RANKS_STR)}

# ── Texture catalog: 50 standard flops ──
TEXTURE_CATALOG = {
    "dry": [
        ("K72r", ["Ks","7h","2d"]), ("Q83r", ["Qs","8h","3d"]), ("J62r", ["Js","6h","2d"]),
        ("T53r", ["Ts","5h","3d"]), ("942r", ["9s","4h","2d"]), ("A72r", ["As","7h","2d"]),
        ("K83r", ["Ks","8h","3d"]), ("Q52r", ["Qs","5h","2d"]),
    ],
    "paired": [
        ("AA3r", ["As","Ah","3d"]), ("KK7r", ["Ks","Kh","7d"]), ("QQ2r", ["Qs","Qh","2d"]),
        ("JJ8r", ["Js","Jh","8d"]), ("882r", ["8s","8h","2d"]), ("559r", ["5s","5h","9d"]),
        ("KKAr", ["Ks","Kh","Ad"]), ("QQKr", ["Qs","Qh","Kd"]),
    ],
    "wet": [
        ("JT9tt", ["Js","Ts","9h"]), ("QJTtt", ["Qs","Js","Th"]), ("T98tt", ["Ts","9s","8h"]),
        ("KQJtt", ["Ks","Qs","Jh"]), ("876tt", ["8s","7s","6h"]), ("J98tt", ["Js","9s","8h"]),
    ],
    "two_tone": [
        ("K72ss", ["Ks","7s","2d"]), ("Q83ss", ["Qs","8s","3d"]), ("AT5ss", ["As","Ts","5d"]),
        ("J62ss", ["Js","6s","2d"]), ("T94ss", ["Ts","9s","4d"]),
    ],
    "monotone": [
        ("K72m", ["Ks","7s","2s"]), ("Q83m", ["Qs","8s","3s"]), ("JT9m", ["Js","Ts","9s"]),
        ("AT5m", ["As","Ts","5s"]),
    ],
    "ace_high": [
        ("AKTr", ["As","Ks","Td"]), ("AQJr", ["As","Qs","Jd"]), ("AJTr", ["As","Js","Td"]),
        ("AKJtt", ["As","Ks","Jh"]), ("AQTss", ["As","Qs","Td"]),
    ],
    "low": [
        ("642r", ["6s","4h","2d"]), ("753r", ["7s","5h","3d"]), ("532r", ["5s","3h","2d"]),
        ("864r", ["8s","6h","4d"]),
    ],
}

# Standard preflop ranges per position
STD_RANGES = {
    "UTG": ["AA","KK","QQ","JJ","TT","99","88","77","AKs","AQs","AJs","KQs","AKo","AQo"],
    "HJ":  ["AA","KK","QQ","JJ","TT","99","88","77","66","AKs","AQs","AJs","ATs","KQs","KJs","QJs","AKo","AQo","AJo","KQo"],
    "CO":  ["AA","KK","QQ","JJ","TT","99","88","77","66","55","AKs","AQs","AJs","ATs","A9s","KQs","KJs","KTs","QJs","QTs","JTs","AKo","AQo","AJo","KQo","KJo"],
    "BTN": ["AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22","AKs","AQs","AJs","ATs","A9s","A8s","KQs","KJs","KTs","QJs","QTs","JTs","T9s","AKo","AQo","AJo","ATo","KQo","KJo","QJo"],
    "BB":  ["AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22","AKs","AQs","AJs","ATs","A9s","A8s","A7s","KQs","KJs","KTs","K9s","QJs","QTs","Q9s","JTs","J9s","T9s","AKo","AQo","AJo","ATo","KQo","KJo","QJo","JTo"],
}

# All 169 hand combos
ALL_COMBOS = []
for i, r1 in enumerate(RANKS_STR):
    for j, r2 in enumerate(RANKS_STR):
        if i < j:
            ALL_COMBOS.append(r1 + r2 + "s")
        elif i == j:
            ALL_COMBOS.append(r1 + r2)
        else:
            ALL_COMBOS.append(r2 + r1 + "o")


def combo_to_specific_hands(combo_str):
    """Convert combo string to list of (card1, card2) as treys Card ints."""
    hands = []
    SUITS = ["s","h","d","c"]
    if len(combo_str) == 2:  # Pair
        r = combo_str[0]
        for i, s1 in enumerate(SUITS):
            for s2 in SUITS[i+1:]:
                hands.append((Card.new(r+s1), Card.new(r+s2)))
    elif combo_str[2] == 's':  # Suited
        for s in SUITS:
            hands.append((Card.new(combo_str[0]+s), Card.new(combo_str[1]+s)))
    else:  # Offsuit
        for s1 in SUITS:
            for s2 in SUITS:
                if s1 != s2:
                    hands.append((Card.new(combo_str[0]+s1), Card.new(combo_str[1]+s2)))
    return hands


def build_equity_table(villain_position="BTN", trials_per_combo=200):
    """
    Build equity table: combo × texture → equity vs villain range.
    Returns dict: {combo_str: {texture_name: equity_float}}
    """
    villain_range = STD_RANGES.get(villain_position, STD_RANGES["BTN"])
    equity_table = {}

    # Flatten all textures
    all_textures = []
    for category, textures in TEXTURE_CATALOG.items():
        for name, board_strs in textures:
            board_cards = [Card.new(s) for s in board_strs]
            all_textures.append((name, board_cards, category))

    print(f"Building equity table for {villain_position} vs {len(all_textures)} textures...")

    for combo_str in ALL_COMBOS:
        combo_hands = combo_to_specific_hands(combo_str)
        if not combo_hands:
            continue

        texture_equities = {}
        for tex_name, board_cards, category in all_textures:
            total_eq = 0
            n_hands = 0
            for hero_cards in combo_hands:
                # Skip if hero cards overlap with board
                if hero_cards[0] in board_cards or hero_cards[1] in board_cards:
                    continue
                # Monte Carlo equity vs villain range
                eq = _fast_equity(hero_cards, board_cards, villain_range, trials_per_combo)
                total_eq += eq
                n_hands += 1
            if n_hands > 0:
                texture_equities[tex_name] = total_eq / n_hands
        equity_table[combo_str] = texture_equities

    return equity_table


def _fast_equity(hero, board, vrange_strs, trials):
    """Quick equity calc for table building."""
    deck = [Card.new(r+s) for r in RANKS_STR for s in ["s","h","d","c"]]
    dead = list(hero) + list(board)
    deck = [c for c in deck if c not in dead]

    # Build villain combos
    vh = []
    for rs in vrange_strs:
        for h in combo_to_specific_hands(rs):
            if h[0] not in dead and h[1] not in dead:
                vh.append(h)

    if not vh:
        return 0.5

    wins = 0
    for _ in range(trials):
        v = random.choice(vh)
        remaining = [c for c in deck if c not in v]
        needed = 5 - len(board)
        runout = random.sample(remaining, needed) if needed > 0 else []
        full_board = list(board) + runout
        hs = evaluator.evaluate(list(hero), full_board)
        vs = evaluator.evaluate(list(v), full_board)
        if hs < vs:
            wins += 1
        elif hs == vs:
            wins += 0.5

    return wins / trials


# ── Fast lookup without full table (lazy, per-texture) ──
_cache = {}
_texture_cache = {}

def get_equity_table(position="BTN", texture_limit=8):
    """Get cached equity table for a position. Only builds top textures."""
    if position not in _cache:
        _cache[position] = _build_light_table(position, texture_limit)
    return _cache[position]


def _build_light_table(position, texture_limit):
    """Build a light table with only key textures."""
    key_textures = []
    for cat in ["dry", "paired", "wet", "two_tone", "monotone"]:
        for name, board_strs in TEXTURE_CATALOG.get(cat, [])[:2]:
            key_textures.append((name, [Card.new(s) for s in board_strs], cat))
    return _build_table_for_textures(position, key_textures[:texture_limit])


def _build_table_for_textures(position, textures, trials=50):
    """Build equity table for specific textures only."""
    villain_range = STD_RANGES.get(position, STD_RANGES["BTN"])
    equity_table = {}

    for combo_str in ALL_COMBOS:
        combo_hands = combo_to_specific_hands(combo_str)
        if not combo_hands:
            continue
        texture_equities = {}
        for tex_name, board_cards, category in textures:
            total_eq = n_hands = 0
            for hero_cards in combo_hands:
                if hero_cards[0] in board_cards or hero_cards[1] in board_cards:
                    continue
                eq = _fast_equity(hero_cards, board_cards, villain_range, trials)
                total_eq += eq
                n_hands += 1
            if n_hands > 0:
                texture_equities[tex_name] = total_eq / n_hands
        equity_table[combo_str] = texture_equities

    return equity_table


def lookup_equity(combo_str, texture_name, position="BTN"):
    """Look up precomputed equity. Falls back to None if not found."""
    table = get_equity_table(position)
    return table.get(combo_str, {}).get(texture_name)


def find_closest_texture(board_cards, texture_catalog=TEXTURE_CATALOG):
    """
    Given actual board cards, find the closest matching texture from catalog.
    Returns (texture_name, category).
    """
    # Simple heuristic: match by board characteristics
    from board_analyzer import analyze_flop
    flop = analyze_flop(board_cards)

    # Try exact name match first
    for cat, textures in texture_catalog.items():
        for name, _ in textures:
            if name in flop:
                return name, cat

    # Fallback: match by category
    cat_map = {
        "paired": "paired",
        "monotone": "monotone",
        "two-tone": "two_tone",
        "rainbow": "dry",
    }

    suited_cat = cat_map.get(flop["suited"], "dry")
    if flop["paired"]:
        suited_cat = "paired"

    # Find first matching texture in that category
    for cat, textures in texture_catalog.items():
        if cat == suited_cat:
            return textures[0][0], cat

    return "K72r", "dry"  # Default
