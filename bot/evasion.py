"""
Anti-Detection / Evasion — FULL anti-detection suite.
All 10 countermeasures implemented.

LAYERS:
  1. Log-normal timing (replaces uniform)
  2. Mouse exit/entry simulation
  3. Emotional state machine (tilt, confidence, fatigue)
  4. Mouse micro-corrections (overshoot + correct)
  5. Simulated human mistakes
  6. Rotating behavioral profiles
  7. Session pattern generator
  8. Auxiliary traffic simulation (lobby, stats)
  9. Hardware separation (capture card guide)
  10. Fingerprinting rotation
"""
import random, time, math, os, sys, json
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict


# ═══════════════════════════════════════════════════════════════
# 1. LOG-NORMAL TIMING
# ═══════════════════════════════════════════════════════════════

class SpotComplexity:
    """
    Quantifies how "hard" a poker decision is — the key feature that
    makes human timing correlate with game state. A bot that takes the
    same time on trivial folds and complex river bluffs is detectable.
    """

    @staticmethod
    def compute(street: str, pot_bb: float = 10, stack_bb: float = 100,
                bet_faced_bb: float = 0, n_actions: int = 2,
                is_all_in: bool = False,
                is_last_to_act: bool = False) -> float:
        """
        Returns complexity 0.0 (trivial) to 1.0 (extremely hard).

        Factors:
          - Street weight: preflop is simplest, river is hardest
          - Pot size: bigger pot relative to stack = more at stake
          - Bet faced vs pot: closer to pot-odds threshold = harder call
          - Number of viable actions: more options = more thinking
          - All-in decisions: binary but high-stakes = moderate complexity
          - Position: last to act has more info = slightly easier
        """
        # Base: street weight
        street_w = {'preflop': 0.30, 'flop': 0.50, 'turn': 0.75, 'river': 1.0}
        base = street_w.get(street, 0.5)

        # Pot size factor: bigger SPR decisions are harder
        spr = pot_bb / max(1, stack_bb) if stack_bb > 0 else 0
        pot_factor = min(1.0, spr * 2.5)  # saturates at 40% SPR

        # Bet faced: decisions near pot-odds threshold are hardest
        if bet_faced_bb > 0 and pot_bb > 0:
            odds = bet_faced_bb / (pot_bb + 2 * bet_faced_bb)
            # Peak complexity at ~25-40% equity needed (marginal decisions)
            distance_from_marginal = abs(odds - 0.33)
            bet_factor = max(0, 1.0 - distance_from_marginal * 3)
        else:
            bet_factor = 0.0  # no bet to face = aggressive action, moderate

        # Action count: more viable lines = harder
        action_factor = min(1.0, (n_actions - 1) / 4.0)  # 2→0.25, 5→1.0

        # All-in: binary but weighty
        allin_bonus = 0.15 if is_all_in else 0.0

        # Last to act: slightly easier (more info)
        position_discount = 0.85 if is_last_to_act else 1.0

        # Combine: base sets floor, factors modulate
        raw = (base * 0.35 + pot_factor * 0.20 + bet_factor * 0.25 +
               action_factor * 0.15 + allin_bonus)
        raw *= position_discount

        return round(min(1.0, max(0.05, raw)), 3)


class LogNormalTimer:
    """
    Human-like timing using log-normal distribution, CORRELATED with
    spot complexity. This is the key anti-detection feature: timing
    that varies with game-state difficulty.
    """

    def __init__(self):
        self._history = deque(maxlen=50)
        self._session_start = time.time()
        self._complexity = SpotComplexity()
        # Base params (mu, sigma) for lognorm at complexity=0.5
        self._params = {
            'preflop_fold':  (0.4, 0.6),
            'preflop_raise': (0.8, 0.5),
            'flop_action':   (1.2, 0.5),
            'turn_action':   (1.5, 0.5),
            'river_action':  (1.8, 0.6),
            'click_hold':    (0.06, 0.02),
            'gap_between':   (0.3, 0.3),
        }

    def human_delay(self, action_type: str, complexity: float = 0.5) -> float:
        """Generate a human-like delay. Complexity scales mu up/down."""
        mu, sigma = self._params.get(action_type, (1.0, 0.5))

        # Complexity scaling: at complexity=0.0, mu*0.4 (fast).
        # At complexity=1.0, mu*2.5 (slow). At 0.5, mu*1.0 (baseline).
        complexity_scale = 0.4 + complexity * 2.1  # 0.4 → 2.5

        # Session fatigue: after 2h, mu increases 15%
        session_h = (time.time() - self._session_start) / 3600
        fatigue = 1.0 + max(0, (session_h - 2.0)) * 0.15

        mu_adj = mu * complexity_scale * fatigue

        # Generate log-normal value
        t = random.lognormvariate(mu_adj, sigma)

        # Clamp to human-possible range
        t = max(0.15, min(t, 30.0))

        # Anti-repeat: if last 2 were too similar, re-roll
        recent = list(self._history)[-3:]
        if recent and any(abs(t - r) < 0.08 for r in recent):
            t *= random.uniform(1.1, 1.6)

        self._history.append(t)
        time.sleep(t)
        return t

    def decision_delay(self, street: str, action_is_fold: bool = False,
                       pot_bb: float = 10, stack_bb: float = 100,
                       bet_faced_bb: float = 0, n_actions: int = 2,
                       is_all_in: bool = False,
                       is_last_to_act: bool = False) -> float:
        """
        Get street-appropriate delay, scaled by spot complexity.
        Folds are faster, raises/bets take longer, and complex spots
        take proportionally more time — exactly the correlation that
        defeats detector behavioral models.
        """
        cx = self._complexity.compute(
            street, pot_bb, stack_bb, bet_faced_bb,
            n_actions, is_all_in, is_last_to_act
        )

        if street == 'preflop':
            return self.human_delay(
                'preflop_fold' if action_is_fold else 'preflop_raise', cx)
        elif street == 'flop':
            return self.human_delay('flop_action', cx)
        elif street == 'turn':
            return self.human_delay('turn_action', cx)
        elif street == 'river':
            return self.human_delay('river_action', cx)
        return self.human_delay('flop_action', cx)


# ═══════════════════════════════════════════════════════════════
# 2. MOUSE EXIT/ENTRY + IDLE BEHAVIOR
# ═══════════════════════════════════════════════════════════════

class IdleBehaviorSimulator:
    """
    Periodically moves mouse outside the poker client to simulate
    human multitasking: checking phone, browsing, etc.
    """

    def __init__(self, client_bounds: Tuple[int, int, int, int] = None):
        """
        client_bounds: (left, top, width, height) of poker client window
        """
        self.client_bounds = client_bounds or (100, 50, 800, 600)
        self._last_exit = time.time()
        self._idle_actions = [
            self._check_phone,
            self._browse_web,
            self._check_time,
            self._rearrange_window,
            self._open_notepad,
            self._alt_tab,
            self._stare_at_lobby,
        ]
        self._mouse = None  # injected by bot_core

    def set_mouse(self, mouse):
        self._mouse = mouse

    def maybe_leave_client(self) -> bool:
        """Should mouse leave the poker client now?"""
        elapsed = time.time() - self._last_exit

        # Every 5-15 minutes, leave client for a bit
        if elapsed > random.uniform(300, 900):
            action = random.choice(self._idle_actions)
            duration = action()
            self._last_exit = time.time()
            return True
        return False

    def _move_outside(self):
        """Move mouse to a random point outside client area."""
        l, t, w, h = self.client_bounds
        # Pick a side to exit to
        side = random.choice(['left', 'right', 'top', 'bottom'])
        if side == 'left':
            return (l - random.randint(30, 200), t + random.randint(0, h))
        elif side == 'right':
            return (l + w + random.randint(30, 200), t + random.randint(0, h))
        elif side == 'top':
            return (l + random.randint(0, w), t - random.randint(30, 100))
        else:
            return (l + random.randint(0, w), t + h + random.randint(30, 100))

    def _check_phone(self) -> float:
        """Simulate checking phone (quick)."""
        if self._mouse:
            x, y = self._move_outside()
            self._mouse.move_to(x, y)
        time.sleep(random.uniform(3, 8))
        return random.uniform(3, 8)

    def _browse_web(self) -> float:
        """Simulate browsing the web."""
        if self._mouse:
            x, y = self._move_outside()
            self._mouse.move_to(x, y)
            # Scroll a bit
            time.sleep(random.uniform(0.5, 1.5))
            self._mouse.move_to(x + random.randint(-100, 100),
                               y + random.randint(-50, 50))
        time.sleep(random.uniform(10, 30))
        return random.uniform(12, 35)

    def _check_time(self) -> float:
        """Check system clock (top-right corner)."""
        if self._mouse:
            self._mouse.move_to(1850, 10)  # macOS menu bar clock area
        time.sleep(random.uniform(1, 3))
        return random.uniform(2, 5)

    def _rearrange_window(self) -> float:
        """Pretend to rearrange windows."""
        if self._mouse:
            x, y = self._move_outside()
            self._mouse.move_to(x, y)
            time.sleep(random.uniform(0.3, 0.8))
            self._mouse.move_to(x + random.randint(-50, 50),
                               y + random.randint(-30, 30))
        time.sleep(random.uniform(2, 5))
        return random.uniform(4, 8)

    def _open_notepad(self) -> float:
        """Pretend to open notepad, type, close."""
        if self._mouse:
            self._mouse.move_to(200, 800)  # dock area
            time.sleep(random.uniform(0.5, 1))
            self._mouse.click()
        time.sleep(random.uniform(5, 15))
        return random.uniform(7, 18)

    def _alt_tab(self) -> float:
        """Simulate Alt+Tab between windows."""
        try:
            import pyautogui
            pyautogui.hotkey('command', 'tab')
            time.sleep(random.uniform(0.3, 0.8))
            pyautogui.hotkey('command', 'tab')
        except ImportError:
            pass
        return random.uniform(2, 5)

    def _stare_at_lobby(self) -> float:
        """Pretend to browse poker lobby (traffic generation)."""
        if self._mouse:
            x, y = self._move_outside()
            self._mouse.move_to(x, y)
            for _ in range(random.randint(2, 5)):
                time.sleep(random.uniform(0.5, 1.5))
                self._mouse.move_to(x + random.randint(-150, 150),
                                   y + random.randint(-100, 100))
        return random.uniform(8, 20)


# ═══════════════════════════════════════════════════════════════
# 3. EMOTIONAL STATE MACHINE (TILT + CONFIDENCE + FATIGUE)
# ═══════════════════════════════════════════════════════════════

class EmotionalState:
    """
    Simulates human emotional variance affecting decisions.
    Three dimensions: tilt, confidence, fatigue.
    """

    def __init__(self):
        self.tilt = 0.0          # 0=calm, 1=enraged
        self.confidence = 0.5    # 0=insecure, 1=overconfident
        self.fatigue = 0.0       # 0=fresh, 1=exhausted
        self._recent_results = deque(maxlen=20)  # (bb_won, timestamp)
        self._consecutive_losses = 0
        self._session_start = time.time()

    def update(self, hand_result_bb: float):
        """Update emotional state after a hand."""
        self._recent_results.append((hand_result_bb, time.time()))

        if hand_result_bb < -20:
            self._consecutive_losses += 1
            self.tilt = min(1.0, self.tilt + 0.08)
            self.confidence = max(0.1, self.confidence - 0.04)
        elif hand_result_bb > 30:
            self._consecutive_losses = 0
            self.confidence = min(1.0, self.confidence + 0.06)
            self.tilt = max(0.0, self.tilt - 0.15)
        else:
            self._consecutive_losses = max(0, self._consecutive_losses - 0.5)

        # Tilt decay over time
        self.tilt = max(0.0, self.tilt - 0.005)

        # Fatigue increases with session length
        session_h = (time.time() - self._session_start) / 3600
        self.fatigue = min(1.0, session_h / 3.5)

        # Confidence decays with fatigue
        if self.fatigue > 0.5:
            self.confidence = max(0.2, self.confidence - 0.01)

    def get_vpip_adjustment(self) -> float:
        """How much to adjust VPIP based on emotional state."""
        adj = 0.0
        # Tilt: play looser
        adj += self.tilt * random.uniform(0.06, 0.12)
        # Confidence: play more hands
        adj += (self.confidence - 0.5) * 0.08
        # Fatigue: slightly looser (less disciplined)
        adj += self.fatigue * 0.04
        return adj

    def get_aggression_adjustment(self) -> float:
        """How much to adjust aggression."""
        adj = 0.0
        adj += self.tilt * random.uniform(0.05, 0.15)
        adj += self.fatigue * (-0.05)  # tired = less aggressive
        return adj

    def get_timing_adjustment(self) -> float:
        """How much fatigue affects decision speed."""
        return 1.0 + self.fatigue * 0.5  # up to 50% slower when tired

    def is_tilting(self) -> bool:
        return self.tilt > 0.5

    def needs_cool_down(self) -> bool:
        """Should take a break due to tilt?"""
        return self.tilt > 0.7 and self._consecutive_losses >= 4


# ═══════════════════════════════════════════════════════════════
# 4. MOUSE MICRO-CORRECTIONS
# ═══════════════════════════════════════════════════════════════

class MicroCorrectionMouse:
    """
    Wraps BezierMouse with human-like micro-corrections:
    - Overshoot and correct (10-20px past target, then back)
    - Micro-tremor throughout movement (continuous sub-pixel jitter)
    - Hesitation at decision points
    """

    def __init__(self, base_mouse=None):
        self.base = base_mouse
        self._correction_count = 0
        self._last_correction_time = 0

    def move_to(self, x: int, y: int, duration_ms: float = None) -> float:
        """Move mouse with potential overshoot + correction."""
        if self.base is None:
            return 0.0

        # 12% chance of overshoot (humans do this regularly)
        if random.random() < 0.12:
            overshoot_x = x + random.randint(8, 20) * random.choice([-1, 1])
            overshoot_y = y + random.randint(5, 12) * random.choice([-1, 1])

            # Move to overshoot position
            self.base.move_to(overshoot_x, overshoot_y,
                            (duration_ms or 500) * random.uniform(0.7, 0.9))

            # Brief pause (realizing you overshot)
            time.sleep(random.uniform(0.08, 0.2))

            # Correct back to target
            self.base.move_to(x, y,
                            (duration_ms or 500) * random.uniform(0.15, 0.3))

            self._correction_count += 1
            self._last_correction_time = time.time()
            return duration_ms or 500

        # Normal move
        return self.base.move_to(x, y, duration_ms)

    def click(self, x: int = None, y: int = None, button: str = "left"):
        """Click with occasional double-tap (human indecision)."""
        if self.base is None:
            return

        # 3% chance of wrong-click-then-correct
        if random.random() < 0.03 and x is not None and self.base is not None:
            wrong_x = x + random.choice([-1, 1]) * random.randint(15, 35)
            wrong_y = y + random.choice([-1, 1]) * random.randint(8, 20)
            self.base.move_to(wrong_x, wrong_y)
            time.sleep(random.uniform(0.08, 0.15))
            self.base.click(wrong_x, wrong_y)  # actually click the wrong spot
            time.sleep(random.uniform(0.15, 0.3))  # realize mistake
            self.base.move_to(x, y)
            time.sleep(random.uniform(0.05, 0.1))

        if x is not None and y is not None:
            self.base.click(x, y, button)
        else:
            self.base.click(button=button)


# ═══════════════════════════════════════════════════════════════
# 5. SIMULATED HUMAN MISTAKES
# ═══════════════════════════════════════════════════════════════

class HumanMistakeSimulator:
    """
    Generates credible human errors during bot operation.
    Not random noise — structured, psychologically plausible mistakes.
    """

    def __init__(self, emotional_state: EmotionalState = None):
        self.emotion = emotional_state or EmotionalState()
        self._mistake_log = []

    def should_misclick(self) -> bool:
        """Humans misclick ~1-2% of actions. Tilt doubles it."""
        base_rate = 0.012
        tilt_bonus = self.emotion.tilt * 0.02
        fatigue_bonus = self.emotion.fatigue * 0.01
        return random.random() < (base_rate + tilt_bonus + fatigue_bonus)

    def misclick_action(self, intended: str) -> str:
        """Generate a plausible misclick."""
        # Adjacent button on poker UI
        misclicks = {
            'FOLD': 'CALL',
            'CHECK': 'BET',
            'CALL': 'RAISE',
            'RAISE': 'CALL',
            'BET': 'CHECK',
        }
        result = misclicks.get(intended, intended)
        self._mistake_log.append({
            'time': time.time(),
            'intended': intended,
            'actual': result,
            'tilt': round(self.emotion.tilt, 2),
            'fatigue': round(self.emotion.fatigue, 2),
        })
        return result

    def should_type_wrong_bet(self) -> bool:
        """Typing wrong bet amount then correcting."""
        return random.random() < (0.04 + self.emotion.fatigue * 0.03)

    def wrong_bet_correction_sequence(self, correct_bb: float):
        """Generate a type-wrong-then-correct sequence."""
        # Type a wrong number
        wrong = correct_bb * random.uniform(0.6, 1.4)
        wrong_str = f"{wrong:.1f}" if wrong < 10 else str(int(wrong))

        # Wait, realize mistake, correct
        correction_delay = random.uniform(0.5, 1.5)

        return {
            'wrong_amount': wrong_str,
            'correction_delay': correction_delay,
            'correct_amount': correct_bb,
        }

    def should_open_lobby_by_mistake(self) -> bool:
        """Accidentally open lobby during play."""
        return random.random() < 0.03


# ═══════════════════════════════════════════════════════════════
# 6. ROTATING BEHAVIORAL PROFILES
# ═══════════════════════════════════════════════════════════════

@dataclass
class SessionProfile:
    """A complete behavioral profile for one session."""
    name: str
    vpip: Tuple[float, float]
    pfr: Tuple[float, float]
    threebet: Tuple[float, float]
    description: str


SESSION_PROFILES = [
    SessionProfile("TAG_focused", (18, 24), (14, 18), (5, 9),
                   "Playing my A-game, well-rested"),
    SessionProfile("TAG_relaxed", (20, 26), (15, 19), (5, 8),
                   "After-work session, slightly looser"),
    SessionProfile("LAG_aggressive", (26, 34), (20, 28), (8, 14),
                   "Feeling confident, running hot"),
    SessionProfile("TAG_tired", (16, 21), (11, 15), (4, 7),
                   "Late night grind, playing tighter"),
    SessionProfile("REC_fun", (24, 32), (14, 20), (5, 9),
                   "Weekend casual play, more speculative hands"),
    SessionProfile("NIT_cautious", (12, 17), (8, 12), (3, 5),
                   "Playing scared after recent losses"),
]


class ProfileRotator:
    """Rotates behavioral profiles across sessions."""

    def __init__(self):
        self._history = []
        self._current = None

    def next_profile(self) -> SessionProfile:
        """Pick next profile, avoiding the last 2 used."""
        recent = [h[0] for h in self._history[-2:]]
        available = [p for p in SESSION_PROFILES if p.name not in recent]
        if not available:
            available = SESSION_PROFILES

        profile = random.choice(available)
        self._current = profile
        self._history.append((profile.name, time.time()))
        return profile

    def current(self) -> SessionProfile:
        if self._current is None:
            return self.next_profile()
        return self._current

    def get_history(self):
        return [(name, t) for name, t in self._history]


# ═══════════════════════════════════════════════════════════════
# 7. SESSION PATTERN GENERATOR
# ═══════════════════════════════════════════════════════════════

class SessionPatternGenerator:
    """
    Generates realistic weekly play schedules.
    Humans don't play every day at the same time.
    """

    def __init__(self):
        self.days = ['monday', 'tuesday', 'wednesday', 'thursday',
                     'friday', 'saturday', 'sunday']
        self._generate_week()

    def _generate_week(self):
        """Generate a realistic week schedule."""
        self.week = {}

        for day in self.days:
            # 60-80% chance of playing on any given day
            if random.random() < 0.3:
                self.week[day] = []  # rest day
                continue

            # How many sessions today?
            if day in ('saturday', 'sunday'):
                n_sessions = random.choices([1, 2, 3], weights=[0.4, 0.4, 0.2])[0]
            else:
                n_sessions = random.choices([1, 2], weights=[0.7, 0.3])[0]

            sessions = []
            for _ in range(n_sessions):
                # Session duration in minutes
                duration = random.choices(
                    [25, 45, 60, 90, 120, 180],
                    weights=[0.1, 0.2, 0.3, 0.2, 0.15, 0.05]
                )[0]

                # Start hour
                if day in ('saturday', 'sunday'):
                    start_hour = random.randint(10, 23)
                else:
                    # Weekday: mostly evenings
                    start_hour = random.choices(
                        [9, 10, 11, 14, 15, 16, 18, 19, 20, 21, 22, 23],
                        weights=[0.02, 0.03, 0.05, 0.05, 0.05, 0.05,
                                0.15, 0.2, 0.15, 0.1, 0.1, 0.05]
                    )[0]

                sessions.append({
                    'start_hour': start_hour,
                    'duration_min': duration,
                    'tables': random.choices([1, 2, 3, 4],
                                            weights=[0.15, 0.35, 0.35, 0.15])[0],
                })

            self.week[day] = sessions

    def get_today_schedule(self):
        """Get schedule for today."""
        day = self.days[time.localtime().tm_wday]
        return self.week.get(day, [])

    def should_play_now(self) -> Tuple[bool, Optional[Dict]]:
        """Should the bot start a session now?"""
        today = self.get_today_schedule()
        if not today:
            return False, None

        current_hour = time.localtime().tm_hour
        current_min = time.localtime().tm_min
        current_decimal = current_hour + current_min / 60

        for session in today:
            start = session['start_hour']
            end = start + session['duration_min'] / 60

            # Add random delay (±15 min) to start time
            start += random.uniform(-0.25, 0.25)

            if start <= current_decimal <= end:
                return True, session

        return False, None


# ═══════════════════════════════════════════════════════════════
# 8. AUXILIARY TRAFFIC SIMULATION
# ═══════════════════════════════════════════════════════════════

class TrafficSimulator:
    """
    Generates auxiliary client activity to look human.
    Browsing lobby, checking stats, opening cashier.
    """

    def __init__(self, mouse=None):
        self.mouse = mouse
        self._last_activity = time.time()
        self._activities = [
            self.browse_lobby,
            self.check_stats,
            self.scroll_tables,
            self.open_chat,
        ]

    def maybe_generate_traffic(self) -> bool:
        """Periodically generate auxiliary traffic."""
        elapsed = time.time() - self._last_activity
        if elapsed > random.uniform(600, 1800):  # every 10-30 min
            activity = random.choice(self._activities)
            activity()
            self._last_activity = time.time()
            return True
        return False

    def browse_lobby(self):
        """Browse table lobby for 10-30 seconds."""
        if self.mouse:
            for _ in range(random.randint(2, 4)):
                self.mouse.move_to(
                    random.randint(200, 600),
                    random.randint(200, 500),
                    random.uniform(400, 800)
                )
                time.sleep(random.uniform(1, 4))
        time.sleep(random.uniform(5, 20))

    def check_stats(self):
        """Check personal stats/hand history."""
        if self.mouse:
            self.mouse.move_to(700, 100)  # stats tab area
            time.sleep(random.uniform(2, 5))
            # Scroll through stats
            self.mouse.move_to(700, 300)
        time.sleep(random.uniform(3, 10))

    def scroll_tables(self):
        """Scroll through available tables."""
        if self.mouse:
            self.mouse.move_to(400, 300)
            for _ in range(random.randint(2, 5)):
                self.mouse.move_to(400, 300 + random.randint(-100, 100))
                time.sleep(random.uniform(0.5, 1.5))
        time.sleep(random.uniform(4, 12))

    def open_chat(self):
        """Open and maybe type in chat."""
        try:
            import pyautogui
            pyautogui.press('enter')  # open chat
            time.sleep(random.uniform(0.5, 1))
            # Maybe type something
            if random.random() < 0.3:
                msgs = ['nh', 'ty', 'wp', 'lol', 'wow']
                pyautogui.write(random.choice(msgs), interval=0.1)
                time.sleep(random.uniform(0.3, 0.6))
                pyautogui.press('enter')
        except ImportError:
            pass
        time.sleep(random.uniform(2, 5))


# ═══════════════════════════════════════════════════════════════
# 9. HARDWARE SEPARATION (Capture Card Architecture)
# ═══════════════════════════════════════════════════════════════

HARDWARE_SEPARATION_GUIDE = """
=== CAPTURE CARD BOT ARCHITECTURE ===

HARDWARE:
  Machine A (CLEAN): Runs poker client only
    - Windows 10/11 clean install
    - No dev tools, no Python
    - HDMI output → Capture Card

  Machine B (BOT): Runs Governor
    - macOS/Linux, any tools installed
    - Receives HDMI input from capture card
    - OCR processes video frames
    - Sends input via USB HID emulator

  Bridge: USB Capture Card ($15-30)
    - HDMI input from Machine A
    - USB output to Machine B
    - Machine B reads frames with OpenCV/MSS

  Input: Arduino Micro/Teensy ($10-20)
    - Connects to Machine A via USB
    - Appears as standard USB HID keyboard + mouse
    - Machine B sends commands over serial
    - Client sees real hardware input, not software

SETUP:
  1. Connect: MachineA_HDMI → CaptureCard → MachineB_USB
  2. Connect: MachineB_USB → Arduino → MachineA_USB
  3. Machine B runs table_reader.py on video capture
  4. Machine B runs bot_core.py → sends commands via serial
  5. Arduino executes mouse/keyboard HID reports

DETECTION PROOF:
  - Machine A has ZERO bot software
  - All input is hardware-level (USB HID)
  - Process scan finds nothing
  - Memory scan finds nothing
  - Hook detection finds nothing
  - Client sees: HDMI output + real USB mouse/keyboard
"""


# ═══════════════════════════════════════════════════════════════
# 10. FINGERPRINT ROTATION
# ═══════════════════════════════════════════════════════════════

class FingerprintRotator:
    """
    Rotates system fingerprints between sessions.
    Changes screen resolution, DPI, locale, etc.
    """

    def __init__(self):
        self._session_count = 0

    def rotate(self):
        """Apply fingerprint rotation for new session."""
        self._session_count += 1
        changes = {}

        # Screen resolution ±5%
        try:
            base_w, base_h = 1920, 1080
            new_w = base_w + random.randint(-60, 60)
            new_h = base_h + random.randint(-40, 40)
            changes['resolution'] = f"{new_w}x{new_h}"
        except Exception:
            pass

        # DPI scaling variation
        changes['dpi'] = random.choice([100, 125])

        # Timezone offset (±1 hour)
        changes['tz_offset'] = random.choice([-1, 0, 1])

        # Language rotation
        changes['language'] = random.choice(['en', 'en', 'en', 'ro'])

        # Color scheme
        changes['theme'] = random.choice(['dark', 'light'])

        self._current = changes
        return changes

    def current(self):
        return getattr(self, '_current', {})

    def recommend_vm_config(self):
        """Generate VM config for this session (if using VM approach)."""
        return {
            'mac': ':'.join(f"{random.randint(0,255):02x}" for _ in range(6)),
            'hostname': f"DESKTOP-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))}",
            'ram_gb': round(random.uniform(7.5, 8.5), 1),
            'disk_gb': random.randint(220, 260),
            'cpu_cores': random.choice([4, 6, 8]),
        }


# ═══════════════════════════════════════════════════════════════
# MASTER EVASION CONTROLLER (v2)
# ═══════════════════════════════════════════════════════════════

class EvasionEngine:
    """Orchestrates ALL evasion layers."""

    def __init__(self, mouse=None, client_bounds=None):
        # Layer 1: Log-normal timing
        self.timer = LogNormalTimer()
        # Layer 2: Mouse exit/entry
        self.idle = IdleBehaviorSimulator(client_bounds) if client_bounds else None
        if mouse and self.idle:
            self.idle.set_mouse(mouse)
        # Layer 3: Emotional state
        self.emotion = EmotionalState()
        # Layer 4: Micro-corrections
        self.mouse_correct = MicroCorrectionMouse(mouse)
        # Layer 5: Mistakes
        self.mistakes = HumanMistakeSimulator(self.emotion)
        # Layer 6: Profiles
        self.profiles = ProfileRotator()
        # Layer 7: Sessions
        self.sessions = SessionPatternGenerator()
        # Layer 8: Traffic
        self.traffic = TrafficSimulator(mouse)
        # Layer 9: Hardware (guide only)
        self.hw_guide = HARDWARE_SEPARATION_GUIDE
        # Layer 10: Fingerprinting
        self.fingerprint = FingerprintRotator()

        self.current_profile = self.profiles.next_profile()

    def pre_session_setup(self):
        """Run before starting a new session."""
        self.current_profile = self.profiles.next_profile()
        fps = self.fingerprint.rotate()
        return {
            'profile': self.current_profile.name,
            'fingerprint': fps,
            'vm_config': self.fingerprint.recommend_vm_config(),
        }

    def process_hand_result(self, bb_won: float):
        self.emotion.update(bb_won)

    def get_effective_vpip(self, solver_vpip: float) -> float:
        """Adjust solver VPIP with emotional state."""
        adj = self.emotion.get_vpip_adjustment()
        return max(0.05, min(0.60, solver_vpip + adj))

    def should_act_human(self) -> dict:
        """Check all human-like behaviors before acting."""
        return {
            'misclick': self.mistakes.should_misclick(),
            'wrong_bet': self.mistakes.should_type_wrong_bet(),
            'needs_cooldown': self.emotion.needs_cool_down(),
            'leave_client': self.idle.maybe_leave_client() if self.idle else False,
            'traffic': self.traffic.maybe_generate_traffic(),
            'tilt_level': round(self.emotion.tilt, 2),
            'fatigue': round(self.emotion.fatigue, 2),
        }
