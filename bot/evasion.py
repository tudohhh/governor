"""
Anti-Detection / Evasion module — sistemic countermeasures.
Goes beyond human-like input to evade poker client scanners.

LAYERS:
  1. Process — hide bot from client process scanning
  2. Behavioral — avoid ML-detectable patterns
  3. Temporal — natural session rhythms, breaks, variance
  4. Spatial — table selection, seat positioning
  5. Bet sizing — avoid algorithmic-looking bets
  6. Multi-table — coordinate actions across tables
"""
import random, time, math, os, sys
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict


# ═══════════════════════════════════════════════════════════════
# LAYER 1: PROCESS CAMOUFLAGE
# ═══════════════════════════════════════════════════════════════

class ProcessCamouflage:
    """
    Techniques to hide the bot process from poker client scanners.
    Poker clients scan running processes for known bot signatures.
    """

    @staticmethod
    def get_disguise_names():
        """Process names that look innocent."""
        return [
            "Spotify Helper", "Adobe Update Service", "iCloud Photos",
            "Microsoft Teams Helper", "Discord PTB Helper", "OneDrive Sync",
            "Google Chrome Helper (Renderer)", "Steam Client WebHelper",
            "Creative Cloud Helper", "Dropbox File Provider",
            "Zoom Helper (Plugin)", "VMware Tools Core",
            "Citrix Receiver Helper", "Evernote Helper",
            "Logitech Options Daemon", "Android File Transfer Agent",
        ]

    @staticmethod
    def check_for_scanners():
        """Check if poker client is scanning processes (macOS)."""
        suspicious = []
        try:
            import subprocess
            # Check for common anti-cheat processes
            ps = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            for keyword in ['poker', 'scan', 'anticheat', 'gameguard', 'warden',
                          'easyanticheat', 'battleye', 'xprotect']:
                if keyword in ps.stdout.lower():
                    suspicious.append(keyword)
        except Exception:
            pass
        return suspicious

    @staticmethod
    def recommend():
        """Return OS-specific recommendations."""
        if sys.platform == 'darwin':
            return [
                "Run bot from a renamed process: launchctl setenv BOT_ALIAS 'Spotify Helper'",
                "Use sandbox-exec to isolate bot from client process tree",
                "Consider running in a lightweight VM (UTM/Parallels) if client is aggressive",
            ]
        elif sys.platform == 'win32':
            return [
                "Use process hollowing or DLL sideloading cautiously",
                "Rename python.exe to something benign like SpotifyHelper.exe",
                "Set window title to match a common application",
            ]
        return ["Research platform-specific process hiding"]


# ═══════════════════════════════════════════════════════════════
# LAYER 2: BEHAVIORAL EVASION
# ═══════════════════════════════════════════════════════════════

@dataclass
class BehavioralProfile:
    """Player archetype that the bot can emulate."""
    name: str
    vpip_range: Tuple[float, float]
    pfr_range: Tuple[float, float]
    threebet_range: Tuple[float, float]
    cbet_range: Tuple[float, float]
    fold_to_cbet_range: Tuple[float, float]
    aggression_range: Tuple[float, float]
    decision_speed_range: Tuple[float, float]  # seconds
    preflop_timing_range: Tuple[float, float]
    postflop_timing_range: Tuple[float, float]
    random_mistake_rate: float  # % of time making suboptimal plays
    chat_frequency: float        # % of hands with chat messages


# Pre-built behavioral profiles
PROFILES = {
    "TAG_reg": BehavioralProfile(
        name="Tight-Aggressive Regular",
        vpip_range=(18, 24), pfr_range=(14, 18),
        threebet_range=(5, 9), cbet_range=(55, 70),
        fold_to_cbet_range=(45, 60),
        aggression_range=(2.0, 3.5),
        decision_speed_range=(2.0, 6.0),
        preflop_timing_range=(1.0, 4.0),
        postflop_timing_range=(2.5, 8.0),
        random_mistake_rate=0.04,
        chat_frequency=0.02,
    ),
    "LAG_pro": BehavioralProfile(
        name="Loose-Aggressive Pro",
        vpip_range=(28, 35), pfr_range=(22, 30),
        threebet_range=(9, 15), cbet_range=(65, 80),
        fold_to_cbet_range=(35, 50),
        aggression_range=(2.5, 4.5),
        decision_speed_range=(1.5, 5.0),
        preflop_timing_range=(0.8, 3.0),
        postflop_timing_range=(2.0, 6.0),
        random_mistake_rate=0.06,
        chat_frequency=0.05,
    ),
    "NIT_rocker": BehavioralProfile(
        name="Tight-Passive Nit",
        vpip_range=(10, 15), pfr_range=(6, 10),
        threebet_range=(2, 4), cbet_range=(40, 55),
        fold_to_cbet_range=(55, 75),
        aggression_range=(1.0, 2.0),
        decision_speed_range=(4.0, 12.0),
        preflop_timing_range=(3.0, 8.0),
        postflop_timing_range=(4.0, 15.0),
        random_mistake_rate=0.02,
        chat_frequency=0.0,
    ),
    "FISH_rec": BehavioralProfile(
        name="Recreational Fish",
        vpip_range=(40, 60), pfr_range=(4, 12),
        threebet_range=(1, 4), cbet_range=(30, 50),
        fold_to_cbet_range=(25, 45),
        aggression_range=(0.5, 1.5),
        decision_speed_range=(1.0, 4.0),
        preflop_timing_range=(0.5, 2.5),
        postflop_timing_range=(1.0, 4.0),
        random_mistake_rate=0.15,
        chat_frequency=0.10,
    ),
}


class BehavioralEvasion:
    """
    Emulate a specific player archetype to avoid pattern detection.
    ML-based detection looks for deviations from human play patterns.
    """

    def __init__(self, profile: BehavioralProfile = None):
        self.profile = profile or PROFILES["TAG_reg"]
        self._action_history = deque(maxlen=200)
        self._session_start = time.time()
        self._current_vpip = random.uniform(*self.profile.vpip_range)
        self._current_pfr = random.uniform(*self.profile.pfr_range)
        self._mistake_today = 0
        self._hands_played = 0

        # Recalibrate stats periodically (humans have hot/cold streaks)
        self._recalibrate()

    def _recalibrate(self):
        """Periodically shift stats within profile range (hot/cold streaks)."""
        p = self.profile
        self._current_vpip = random.uniform(*p.vpip_range)
        self._current_pfr = random.uniform(*p.pfr_range)
        self._decision_speed = random.uniform(*p.decision_speed_range)
        self._next_recalibrate = self._hands_played + random.randint(30, 80)

    def should_play_hand(self, combo_strength: float) -> bool:
        """Decide whether to play a hand based on VPIP profile.
        combo_strength: 0-1 hand strength (from EHS or solver equity)."""
        self._hands_played += 1

        if self._hands_played >= self._next_recalibrate:
            self._recalibrate()

        # Map combo strength to play probability matching VPIP
        # Stronger hands = higher play probability
        threshold = 1.0 - self._current_vpip / 100.0

        # Add variance (tilt factor, table dynamics)
        threshold += random.gauss(0, 0.05)

        return combo_strength > threshold

    def inject_mistake(self, solver_action: str) -> str:
        """Occasionally override solver with a 'human' mistake."""
        if random.random() < self.profile.random_mistake_rate:
            self._mistake_today += 1
            mistakes = {
                'FOLD': random.choice(['CALL', 'CHECK']),
                'CHECK': 'BET_33',
                'BET_33': 'CHECK',
                'BET_66': 'BET_33',
                'CALL': 'FOLD',
            }
            return mistakes.get(solver_action.replace('BET ', 'BET_'), solver_action)
        return solver_action

    def get_timing(self, street: str) -> float:
        """Get human-like decision timing for this profile."""
        p = self.profile
        if street == 'preflop':
            base = random.uniform(*p.preflop_timing_range)
        else:
            base = random.uniform(*p.postflop_timing_range)

        # Add micro-variance and time-of-session fatigue
        session_hours = (time.time() - self._session_start) / 3600
        fatigue = 1.0 + max(0, (session_hours - 1.5) * 0.15)
        return base * fatigue * random.gauss(1.0, 0.1)

    def get_stats_snapshot(self) -> Dict:
        """Current behavioral stats (for anti-pattern verification)."""
        return {
            'vpip': round(self._current_vpip, 1),
            'pfr': round(self._current_pfr, 1),
            'profile': self.profile.name,
            'hands': self._hands_played,
            'mistakes': self._mistake_today,
            'session_hours': round((time.time() - self._session_start) / 3600, 1),
        }


# ═══════════════════════════════════════════════════════════════
# LAYER 3: TEMPORAL EVASION
# ═══════════════════════════════════════════════════════════════

class TemporalEvasion:
    """
    Natural session rhythms — when and how long to play.
    Poker sites detect bots by consistent play schedules.
    """

    def __init__(self):
        # Human session patterns (minutes)
        self.session_patterns = [
            (25, 65),   # short session
            (60, 120),  # medium
            (90, 180),  # long grind
            (35, 75),   # medium-short
        ]
        self._current_pattern = random.choice(self.session_patterns)
        self._session_start = time.time()
        self._breaks_taken = 0
        self._max_hands_per_hour = random.randint(60, 90)  # single table
        self._hand_times = deque(maxlen=60)

    def should_continue(self) -> bool:
        """Should the bot keep playing this session?"""
        elapsed = (time.time() - self._session_start) / 60
        max_duration = sum(self._current_pattern)
        return elapsed < max_duration

    def should_take_break(self) -> bool:
        """Should the bot sit out for a break?"""
        elapsed = (time.time() - self._session_start) / 60

        # First break: after first segment
        if self._breaks_taken == 0 and elapsed > self._current_pattern[0]:
            self._breaks_taken += 1
            return True

        # Additional breaks: ~15% chance after 45 min
        if elapsed > 45 and random.random() < 0.15:
            return True

        return False

    def break_duration(self) -> float:
        """How long to break (minutes)."""
        # Human breaks: bathroom, coffee, phone, etc.
        break_types = [
            random.uniform(2, 5),     # quick
            random.uniform(5, 12),    # normal
            random.uniform(10, 25),   # long
            random.uniform(2, 4),     # quick check phone
        ]
        return random.choice(break_types)

    def hands_per_hour_target(self) -> int:
        """Target hands per hour (single table ~60-90 for human)."""
        return self._max_hands_per_hour

    def register_hand_time(self):
        """Track hand completion time for pace monitoring."""
        self._hand_times.append(time.time())

    def current_pace(self) -> float:
        """Current hands per hour rate."""
        if len(self._hand_times) < 2:
            return 0
        elapsed_hours = (self._hand_times[-1] - self._hand_times[0]) / 3600
        if elapsed_hours < 0.01:
            return 0
        return len(self._hand_times) / elapsed_hours

    def is_playing_too_fast(self) -> bool:
        """Check if bot is playing faster than human pace."""
        pace = self.current_pace()
        return pace > self._max_hands_per_hour * 1.15

    def time_of_day_factor(self) -> float:
        """
        Different times of day = different play styles.
        Late night = looser, more aggressive (tired players).
        """
        hour = time.localtime().tm_hour
        if 2 <= hour <= 6:
            return 1.3   # late night: looser
        elif 9 <= hour <= 12:
            return 1.0   # morning: standard
        elif 13 <= hour <= 17:
            return 0.9   # afternoon: slightly tighter (regs)
        elif 18 <= hour <= 23:
            return 1.1   # evening: more recs = slightly looser
        return 1.0


# ═══════════════════════════════════════════════════════════════
# LAYER 4: SPATIAL EVASION (Table/Seat Selection)
# ═══════════════════════════════════════════════════════════════

class SpatialEvasion:
    """Natural table and seat selection patterns."""

    @staticmethod
    def select_seat(available_positions: List[str]) -> str:
        """
        Pick a seat that looks natural.
        Humans don't always sit in the same position.
        """
        if not available_positions:
            return 'BTN'

        # Humans have position preferences but vary them
        preferences = {
            'BTN': 0.25, 'CO': 0.20, 'HJ': 0.15,
            'UTG': 0.05, 'SB': 0.10, 'BB': 0.10,
        }

        # Weight by availability
        weights = []
        positions = []
        for pos in available_positions:
            positions.append(pos)
            weights.append(preferences.get(pos, 0.05))

        total = sum(weights)
        weights = [w / total for w in weights]

        r = random.random()
        cum = 0
        for pos, w in zip(positions, weights):
            cum += w
            if r <= cum:
                return pos

        return available_positions[0]

    @staticmethod
    def should_switch_table(current_hands: int) -> bool:
        """Decide whether to switch tables (natural behavior)."""
        if current_hands < 20:
            return False

        # Humans switch tables occasionally
        prob = 0.05  # base 5% per hand check

        # After a big loss, more likely to switch
        prob *= 1.5

        return random.random() < prob

    @staticmethod
    def select_stake_level(bankroll_bb: float) -> str:
        """Choose appropriate stake based on bankroll (in BB)."""
        if bankroll_bb < 20:
            return 'NL2'
        elif bankroll_bb < 50:
            return 'NL5'
        elif bankroll_bb < 100:
            return 'NL10'
        elif bankroll_bb < 200:
            return 'NL25'
        elif bankroll_bb < 500:
            return 'NL50'
        elif bankroll_bb < 1000:
            return 'NL100'
        else:
            return 'NL200'


# ═══════════════════════════════════════════════════════════════
# LAYER 5: BET SIZING EVASION
# ═══════════════════════════════════════════════════════════════

class BetSizingEvasion:
    """
    Make bet sizes look human, not solver-computed.
    Solvers output precisely calculated sizes; humans use heuristics.
    """

    @staticmethod
    def humanize_sizing(solver_pct: float, street: str, pot_bb: float) -> float:
        """
        Convert solver bet sizing (%) to a human-like amount.

        Humans:
        - Preflop: use fixed sizes (2.5bb, 3bb, 3.5bb)
        - Flop: use slider or preset buttons (33%, 50%, 66%, 75%, pot)
        - Turn: similar but larger
        - River: often pot or overbet, or small block bet
        """
        # Snap to common human sizing buckets
        buckets = {
            'preflop': [(0.20, 0.32, 0.25), (0.33, 0.45, 0.35),
                       (0.46, 0.60, 0.50), (0.61, 1.0, 0.75)],
            'flop':    [(0, 0.15, 0.05), (0.25, 0.40, 0.33),
                       (0.50, 0.60, 0.50), (0.65, 0.80, 0.66),
                       (0.85, 1.2, 1.0)],
            'turn':    [(0, 0.15, 0.05), (0.30, 0.45, 0.33),
                       (0.55, 0.70, 0.66), (0.75, 1.0, 0.75),
                       (1.0, 2.0, 1.5)],
            'river':   [(0, 0.15, 0.05), (0.30, 0.45, 0.33),
                       (0.55, 0.70, 0.66), (0.75, 1.0, 0.75),
                       (1.0, 1.5, 1.25)],
        }

        for lo, hi, snap in buckets.get(street, buckets['flop']):
            if lo <= solver_pct <= hi:
                # Add micro-noise to the snapped value
                noise = random.gauss(0, snap * 0.03)
                return max(0.01, snap + noise)

        return solver_pct

    @staticmethod
    def randomize_bet_sequence(actions: List[str]) -> List[str]:
        """
        Occasionally alter bet sizing sequence.
        Humans don't always use the same size in the same spot.
        """
        if random.random() < 0.08:  # 8% deviation
            # Swap between similar sizes
            swaps = {'BET 33%': 'BET 50%', 'BET 50%': 'BET 33%',
                    'BET 66%': 'BET 75%', 'BET 75%': 'BET 66%'}
            return [swaps.get(a, a) for a in actions]
        return actions


# ═══════════════════════════════════════════════════════════════
# LAYER 6: MULTI-TABLE COORDINATION
# ═══════════════════════════════════════════════════════════════

class MultiTableCoordinator:
    """
    Coordinate actions across multiple tables for natural appearance.
    Humans have attention bottlenecks that bots don't.
    """

    def __init__(self, max_tables=4):
        self.max_tables = max_tables
        self.active_tables = 0
        self._last_action_table = None
        self._action_queue = deque()
        self._attention_focus = 0  # which table has attention (0-indexed)

    def can_act(self, table_id: int) -> bool:
        """Check if bot can act on this table now.
        Humans can only attend to one table at a time."""
        # Switch attention every few seconds (human scanning pattern)
        if time.time() % random.uniform(2, 5) < 0.1:
            self._attention_focus = table_id

        return self._attention_focus == table_id

    def schedule_action(self, table_id: int, action: str):
        """Queue an action with human-like multi-table delay."""
        # Humans take 0.5-2s between actions on different tables
        delay = random.uniform(0.5, 2.0) if table_id != self._last_action_table else 0
        self._action_queue.append((time.time() + delay, table_id, action))
        self._last_action_table = table_id

    def get_next_action(self):
        """Get the next ready action from the queue."""
        if self._action_queue and self._action_queue[0][0] <= time.time():
            return self._action_queue.popleft()
        return None

    def optimal_table_count(self, session_minutes: float) -> int:
        """Humans vary table count over session."""
        if session_minutes < 15:
            return 1  # warming up
        elif session_minutes < 45:
            return min(2, self.max_tables)  # settling in
        elif session_minutes < 120:
            return min(random.randint(2, self.max_tables), self.max_tables)  # grinding
        else:
            return min(random.randint(1, 3), self.max_tables)  # tired, reducing


# ═══════════════════════════════════════════════════════════════
# Master Evasion Controller
# ═══════════════════════════════════════════════════════════════

class EvasionEngine:
    """Orchestrates all evasion layers."""

    def __init__(self, profile_name='TAG_reg'):
        self.behavior = BehavioralEvasion(PROFILES.get(profile_name, PROFILES['TAG_reg']))
        self.temporal = TemporalEvasion()
        self.spatial = SpatialEvasion()
        self.sizing = BetSizingEvasion()
        self.multitable = MultiTableCoordinator()
        self.process = ProcessCamouflage()

    def pre_session_check(self) -> Dict:
        """Check before starting a session."""
        scanners = self.process.check_for_scanners()
        return {
            'scanners_detected': scanners,
            'safe_to_start': len(scanners) == 0,
            'recommendations': self.process.recommend(),
        }

    def should_play(self, hand_strength: float) -> bool:
        return self.behavior.should_play_hand(hand_strength)

    def get_decision_timing(self, street: str) -> float:
        return self.behavior.get_timing(street)

    def humanize_action(self, solver_action: str, street: str, pot_bb: float):
        """Process a solver action through all evasion layers."""
        # 1. Inject occasional human mistake
        action = self.behavior.inject_mistake(solver_action)

        # 2. Humanize bet sizing
        if 'BET' in action:
            try:
                pct = float(action.split('%')[0].split()[-1]) / 100
                human_pct = self.sizing.humanize_sizing(pct, street, pot_bb)
                action = f"{action.split('%')[0].rsplit(' ', 1)[0]} {human_pct*100:.0f}%"
            except (ValueError, IndexError):
                pass

        return action

    def get_session_status(self) -> Dict:
        """Get current evasion state."""
        return {
            'behavior': self.behavior.get_stats_snapshot(),
            'session_minutes': round(self.temporal._session_start and
                (time.time() - self.temporal._session_start) / 60, 1),
            'hands_per_hour': round(self.temporal.current_pace(), 1),
            'multitable': self.multitable.active_tables,
        }
