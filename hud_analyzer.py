"""
HUD Analyzer — real-time opponent statistics from hand histories.
Integrates with hh_parser.py for PokerStars/GGPoker hand history parsing.

Key stats: VPIP, PFR, 3Bet%, Aggression Factor, Fold to C-Bet, WTSD%
"""
import json, os, re, math
from collections import defaultdict, Counter
from hh_parser import parse_pokerstars, analyze_hand


class PlayerStats:
    """HUD statistics for a single player."""

    def __init__(self, name):
        self.name = name
        self.hands = 0
        self.vpip_count = 0     # voluntarily put money in pot
        self.pfr_count = 0      # preflop raise
        self.threebet_count = 0
        self.fold_to_3bet_count = 0
        self.facing_3bet_count = 0
        self.cbet_count = 0
        self.cbet_opportunity = 0
        self.fold_to_cbet_count = 0
        self.facing_cbet_count = 0
        self.aggression_actions = 0  # bets + raises
        self.passive_actions = 0     # calls + checks
        self.saw_showdown = 0
        self.won_at_showdown = 0
        self.total_won = 0.0
        self.total_lost = 0.0
        self.sessions = set()

    @property
    def vpip(self):
        return self.vpip_count / max(1, self.hands) * 100

    @property
    def pfr(self):
        return self.pfr_count / max(1, self.hands) * 100

    @property
    def threebet_pct(self):
        return self.threebet_count / max(1, self.hands) * 100

    @property
    def fold_to_3bet(self):
        return self.fold_to_3bet_count / max(1, self.facing_3bet_count) * 100

    @property
    def cbet_pct(self):
        return self.cbet_count / max(1, self.cbet_opportunity) * 100

    @property
    def fold_to_cbet(self):
        return self.fold_to_cbet_count / max(1, self.facing_cbet_count) * 100

    @property
    def aggression_factor(self):
        return self.aggression_actions / max(1, self.passive_actions)

    @property
    def wtsd(self):
        return self.saw_showdown / max(1, self.hands) * 100

    def classify_opponent(self):
        """Classify opponent into a profile type."""
        if self.hands < 20:
            return 'standard'  # not enough data

        if self.vpip < 15 and self.pfr < 10:
            return 'nit'
        elif self.vpip < 20 and self.pfr < 15:
            return 'tight-rock'
        elif self.vpip > 35 and self.pfr > 25:
            return 'lag'
        elif self.vpip > 45:
            return 'maniac'
        elif self.aggression_factor < 1.0 and self.vpip > 30:
            return 'fish'
        else:
            return 'standard'

    def to_dict(self):
        return {
            'name': self.name, 'hands': self.hands,
            'vpip': round(self.vpip, 1), 'pfr': round(self.pfr, 1),
            '3bet': round(self.threebet_pct, 1),
            'fold_to_3bet': round(self.fold_to_3bet, 1),
            'cbet': round(self.cbet_pct, 1),
            'fold_to_cbet': round(self.fold_to_cbet, 1),
            'af': round(self.aggression_factor, 1),
            'wtsd': round(self.wtsd, 1),
            'type': self.classify_opponent(),
            'won': round(self.total_won, 1),
        }


class HudDatabase:
    """Database of all players encountered."""

    def __init__(self, db_path='hud_database.json'):
        self.db_path = db_path
        self.players = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path) as f:
                data = json.load(f)
                for name, stats in data.items():
                    p = PlayerStats(name)
                    for k, v in stats.items():
                        if hasattr(p, k) and k != 'name':
                            setattr(p, k, v)
                    self.players[name] = p

    def save(self):
        data = {name: p.to_dict() for name, p in self.players.items()}
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_player(self, name):
        if name not in self.players:
            self.players[name] = PlayerStats(name)
        return self.players[name]

    def process_hand(self, hand_text):
        """Process a single hand history and update all player stats."""
        hand = parse_pokerstars(hand_text)
        if not hand:
            return None

        hero = hand.hero_name
        hero_stats = self.get_player(hero)
        hero_stats.hands += 1

        # Update opponent stats too
        for player_name in hand.players:
            if player_name != hero:
                opp = self.get_player(player_name)
                opp.hands += 1

        # Analyze actions
        self._analyze_preflop(hand, hero_stats)
        self._analyze_postflop(hand, hero_stats)
        self._analyze_results(hand, hero_stats)

        return True

    def _analyze_preflop(self, hand, stats):
        """Analyze preflop actions."""
        hero = hand.hero_name

        for action in hand.actions_preflop:
            if action.player == hero:
                if action.action in ('raises', 'bets'):
                    stats.pfr_count += 1
                    stats.vpip_count += 1
                    stats.aggression_actions += 1
                elif action.action == 'calls':
                    stats.vpip_count += 1
                    stats.passive_actions += 1
                elif action.action == 'checks':
                    stats.passive_actions += 1

        # Detect 3-bet situations
        raise_count = 0
        for action in hand.actions_preflop:
            if action.action == 'raises':
                raise_count += 1
            if raise_count == 2:  # second raise = 3bet
                if action.player == hero:
                    stats.threebet_count += 1
                if action.player != hero:
                    stats.facing_3bet_count += 1
                    # Check if hero folded
                    for later in hand.actions_preflop:
                        if later.player == hero and later.action == 'folds':
                            stats.fold_to_3bet_count += 1

    def _analyze_postflop(self, hand, stats):
        """Analyze postflop actions."""
        hero = hand.hero_name

        for street_actions in [hand.actions_flop, hand.actions_turn, hand.actions_river]:
            for action in street_actions:
                if action.player == hero:
                    if action.action in ('raises', 'bets'):
                        stats.aggression_actions += 1
                    elif action.action in ('calls', 'checks'):
                        stats.passive_actions += 1

        # C-bet detection (simplified)
        if hand.actions_flop:
            preflop_raises = [a for a in hand.actions_preflop
                            if a.player == hero and a.action == 'raises']
            if preflop_raises:
                stats.cbet_opportunity += 1
                first_flop = hand.actions_flop[0]
                if first_flop.player == hero and first_flop.action in ('bets', 'raises'):
                    stats.cbet_count += 1

    def _analyze_results(self, hand, stats):
        """Analyze hand results."""
        if 'Won' in hand.result:
            try:
                amount = float(re.search(r'\$?([\d.]+)', hand.result).group(1))
                stats.total_won += amount
                stats.won_at_showdown += 1
            except (ValueError, AttributeError):
                pass


def generate_hud_display(players):
    """Generate HUD display data for all tracked players.
    Returns dict mapping player name → dict of stats."""
    display = {}
    for name, stats in players.items():
        if stats.hands > 0:
            display[name] = stats.to_dict()
    return display


def analyze_session(hand_texts):
    """Analyze a session of hands.
    hand_texts: list of hand history strings.
    Returns dict with session summary."""
    db = HudDatabase()
    for text in hand_texts:
        db.process_hand(text)

    db.save()
    return generate_hud_display(db.players)


if __name__ == "__main__":
    print("HUD Analyzer — Ready")
    print("=" * 30)

    # Simulate a session with sample data
    db = HudDatabase()

    # Create test stats
    for name, vpip, pfr, hands in [
        ('Hero', 22, 16, 100),
        ('Villain1', 12, 8, 45),
        ('Villain2', 38, 28, 60),
        ('Villain3', 55, 5, 30),
    ]:
        p = db.get_player(name)
        p.hands = hands
        p.vpip_count = int(vpip * hands / 100)
        p.pfr_count = int(pfr * hands / 100)

    print("\nPlayer stats:")
    for name, stats in db.players.items():
        if stats.hands > 0:
            s = stats.to_dict()
            print(f"  {name:15} VPIP:{s['vpip']:5.1f}% PFR:{s['pfr']:5.1f}% "
                  f"Type:{s['type']:12} Hands:{s['hands']}")
