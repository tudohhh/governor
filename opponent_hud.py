"""
HUD-based opponent profiles calibrated on real NL25-NL100 statistics.
Session tracking for dynamic adaptation.
"""

# Realistic stats per player type at NL25-NL100
PROFILES = {
    "standard": {
        "name": "Reg Standard",
        "desc": "Reg solid, echilibrat. 22/18/7.",
        "vpip": 22, "pfr": 18, "threebet": 7,
        "fold_to_cbet": 52, "fold_to_turn_cbet": 42,
        "fold_to_river_bet": 55,
        "cbet_flop": 65, "cbet_turn": 48,
        "bluff_frequency": 22,
        "aggression_factor": 2.5,
        "wtsd": 28,  # Went to showdown
        "notes": "Cel mai comun reg la NL50-NL100. Nu face greșeli mari.",
    },
    "nit": {
        "name": "Nit / Tight-Rock",
        "desc": "Ultra-tight, doar premium. 14/11/3.",
        "vpip": 14, "pfr": 11, "threebet": 3,
        "fold_to_cbet": 68, "fold_to_turn_cbet": 55,
        "fold_to_river_bet": 72,
        "cbet_flop": 55, "cbet_turn": 35,
        "bluff_frequency": 10,
        "aggression_factor": 1.8,
        "wtsd": 22,
        "notes": "Foldează la orice presiune. C-bet-ează rar. Value bet doar cu nuts.",
    },
    "lag": {
        "name": "LAG",
        "desc": "Loose-agresiv, range larg. 28/24/12.",
        "vpip": 28, "pfr": 24, "threebet": 12,
        "fold_to_cbet": 45, "fold_to_turn_cbet": 35,
        "fold_to_river_bet": 42,
        "cbet_flop": 78, "cbet_turn": 62,
        "bluff_frequency": 35,
        "aggression_factor": 3.8,
        "wtsd": 24,
        "notes": "Pune presiune constantă. C-bet-ează aproape orice. Poți prinde bluff-uri.",
    },
    "maniac": {
        "name": "Maniac",
        "desc": "Agresiv extrem, orice mână. 55/35/18.",
        "vpip": 55, "pfr": 35, "threebet": 18,
        "fold_to_cbet": 22, "fold_to_turn_cbet": 15,
        "fold_to_river_bet": 18,
        "cbet_flop": 85, "cbet_turn": 70,
        "bluff_frequency": 50,
        "aggression_factor": 5.5,
        "wtsd": 30,
        "notes": "Joacă orice, bluff-ează masiv. Value bet larg, nu blufa contra lui!",
    },
    "fish": {
        "name": "Fish / Calling Station",
        "desc": "Call la tot, pasiv. 42/8/2.",
        "vpip": 42, "pfr": 8, "threebet": 2,
        "fold_to_cbet": 30, "fold_to_turn_cbet": 25,
        "fold_to_river_bet": 28,
        "cbet_flop": 35, "cbet_turn": 20,
        "bluff_frequency": 15,
        "aggression_factor": 0.9,
        "wtsd": 38,
        "notes": "Chemă totul. Nu bluff-a! Doar value bet, mare. Plătește până la river.",
    },
}


class OpponentTracker:
    """Tracks opponent tendencies during a session and adapts strategy."""

    def __init__(self, base_type="standard"):
        profile = PROFILES.get(base_type, PROFILES["standard"])
        self.base_type = base_type
        self.fold_to_cbet = profile["fold_to_cbet"] / 100
        self.fold_to_turn_cbet = profile["fold_to_turn_cbet"] / 100
        self.fold_to_river_bet = profile["fold_to_river_bet"] / 100
        self.cbet_freq = profile["cbet_flop"] / 100
        self.bluff_freq = profile["bluff_frequency"] / 100
        self.aggression = profile["aggression_factor"]

        # Session tracking
        self.hands_played = 0
        self.folds_to_cbet_seen = 0
        self.cbets_seen = 0
        self.folds_to_river_seen = 0
        self.river_bets_faced = 0

    def observe_fold_to_cbet(self):
        self.hands_played += 1
        self.folds_to_cbet_seen += 1
        self.cbets_seen += 1
        self._update()

    def observe_call_cbet(self):
        self.hands_played += 1
        self.cbets_seen += 1
        self._update()

    def observe_fold_to_river(self):
        self.folds_to_river_seen += 1
        self.river_bets_faced += 1
        self._update()

    def observe_call_river(self):
        self.river_bets_faced += 1
        self._update()

    def _update(self):
        """Update estimates based on observed data (weighted toward base)."""
        if self.cbets_seen > 3:
            observed_fold_cbet = self.folds_to_cbet_seen / self.cbets_seen
            # Bayesian-ish: weight base 70%, observed 30%
            self.fold_to_cbet = self.fold_to_cbet * 0.70 + observed_fold_cbet * 0.30

        if self.river_bets_faced > 2:
            observed_fold_river = self.folds_to_river_seen / self.river_bets_faced
            self.fold_to_river_bet = self.fold_to_river_bet * 0.70 + observed_fold_river * 0.30

    def adapt_cbet_frequency(self, base_freq):
        """Adjust c-bet frequency based on opponent's fold tendency."""
        if self.fold_to_cbet > 0.65:
            return base_freq * 1.3  # C-bet more vs nits
        elif self.fold_to_cbet < 0.35:
            return base_freq * 0.6  # C-bet less vs stations
        return base_freq

    def get_profile(self):
        return PROFILES.get(self.base_type, PROFILES["standard"])

    def summary(self):
        return (f"{self.get_profile()['name']} | "
                f"Fold2CB: {self.fold_to_cbet:.0%} | "
                f"Fold2Riv: {self.fold_to_river_bet:.0%} | "
                f"Hands: {self.hands_played}")
