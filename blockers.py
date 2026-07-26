"""
Blocker analysis: calculate how hero's cards block villain's range.
Key concept: if you hold A♠ on a board with flush draw,
villain has fewer flush draw combos → you can bluff more.
"""
from treys import Card

RANKS_STR = "AKQJT98765432"
SUITS = ["s","h","d","c"]


def count_blocked_combos(hero_cards, villain_range_strs, board_cards):
    """
    Count how many combos from villain's range are blocked by hero cards.
    Returns (total_combos, blocked_combos, block_percent).
    """
    hero_ranks = set()
    hero_suits = set()
    for c in hero_cards:
        s = Card.int_to_str(c)
        hero_ranks.add(s[0])
        hero_suits.add(Card.get_suit_int(c))

    board_ranks = set()
    board_suits = set()
    for c in board_cards:
        s = Card.int_to_str(c)
        board_ranks.add(s[0])
        board_suits.add(Card.get_suit_int(c))

    total = 0
    blocked = 0

    for combo in villain_range_strs:
        if len(combo) == 2:  # Pair
            r = combo[0]
            if r in hero_ranks or r in board_ranks:
                # Some combos blocked
                all_combos = 6  # 6 combos per pair
                blocked_ranks = (1 if r in hero_ranks else 0) + (1 if r in board_ranks else 0)
                if blocked_ranks == 1:
                    blocked += 3  # 3 combos blocked
                    total += 6
                elif blocked_ranks >= 2:
                    blocked += 6  # All blocked
                    total += 6
                else:
                    total += 6
            else:
                total += 6

        elif len(combo) == 3 and combo[2] == 's':  # Suited
            r1, r2 = combo[0], combo[1]
            suits_blocked = 0
            if r1 in hero_ranks:
                suits_blocked += 1
            if r2 in hero_ranks:
                suits_blocked += 1
            if r1 in board_ranks:
                suits_blocked += 1
            if r2 in board_ranks:
                suits_blocked += 1

            total += 4
            if suits_blocked >= 2:
                blocked += 2  # ~2 suited combos blocked
            elif suits_blocked == 1:
                blocked += 1

        else:  # Offsuit
            r1, r2 = combo[0], combo[1]
            ranks_blocked = 0
            if r1 in hero_ranks:
                ranks_blocked += 1
            if r2 in hero_ranks:
                ranks_blocked += 1
            if r1 in board_ranks:
                ranks_blocked += 1
            if r2 in board_ranks:
                ranks_blocked += 1

            total += 12
            if ranks_blocked >= 2:
                blocked += 6
            elif ranks_blocked == 1:
                blocked += 3

    block_pct = blocked / total * 100 if total > 0 else 0
    return {
        "total_combos": total,
        "blocked_combos": blocked,
        "block_percent": round(block_pct, 1),
        "remaining_combos": total - blocked,
    }


def bluff_equity_boost(hero_cards, villain_range, board_cards):
    """
    Calculate how much extra fold equity you have due to blockers.
    Returns multiplier for bluff frequency.
    """
    block_info = count_blocked_combos(hero_cards, villain_range, board_cards)
    block_pct = block_info["block_percent"]

    # If you block >10% of villain's continue range, you get extra fold equity
    if block_pct > 25:
        return 1.5  # 50% more bluff frequency
    elif block_pct > 15:
        return 1.3
    elif block_pct > 8:
        return 1.15
    else:
        return 1.0


def key_blockers(hero_cards, board_cards):
    """
    Identify which specific blockers hero holds.
    Returns list of blocker descriptions.
    """
    blockers = []
    hero_strs = [Card.int_to_str(c) for c in hero_cards]
    board_strs = [Card.int_to_str(c) for c in board_cards]

    hero_ranks = set(s[0] for s in hero_strs)
    board_ranks = set(s[0] for s in board_strs)
    hero_suits = set(Card.get_suit_int(c) for c in hero_cards)
    board_suits = set(Card.get_suit_int(c) for c in board_cards)

    # Flush blocker
    if len(board_suits) <= 2 and len(hero_suits & board_suits) > 0:
        blockers.append("flush blocker")

    # Straight blocker
    all_ranks = hero_ranks | board_ranks
    rank_indices = sorted([RANKS_STR.index(r) for r in all_ranks])
    for i in range(len(rank_indices) - 2):
        if rank_indices[i+2] - rank_indices[i] <= 4:
            blockers.append("straight blocker")
            break

    # Top pair blocker
    top_board_rank = min(board_ranks, key=lambda r: RANKS_STR.index(r))
    if top_board_rank in hero_ranks:
        blockers.append(f"top pair blocker ({top_board_rank})")

    # Overpair blocker
    board_high_idx = min(RANKS_STR.index(r) for r in board_ranks)
    for r in hero_ranks:
        if RANKS_STR.index(r) < board_high_idx:
            blockers.append(f"overcard blocker ({r})")
            break

    return blockers


def blocker_effect_summary(hero_cards, villain_range, board_cards):
    """One-line summary of blocker effects."""
    info = count_blocked_combos(hero_cards, villain_range, board_cards)
    kb = key_blockers(hero_cards, board_cards)
    boost = bluff_equity_boost(hero_cards, villain_range, board_cards)

    parts = []
    if kb:
        parts.append(", ".join(kb))
    if boost > 1.0:
        parts.append(f"+{int((boost-1)*100)}% bluff freq")

    if not parts:
        return "fără blocanți relevanți"

    return " · ".join(parts)
