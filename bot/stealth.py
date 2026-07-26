"""
Stealth module — human-like mouse movement, timing, anti-detection.
Makes bot actions indistinguishable from human play patterns.

Key techniques:
- Bezier curve mouse paths with variable velocity
- Click position jitter (never same pixel)
- Response timing modeled on real human data
- Bet sizing with noise (not round numbers)
- Session pattern randomization
"""
import random
import time
import math
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from collections import deque


# ═══════════════════════════════════════════════════════════════
# TIMING — Human response delays (measured from real players)
# ═══════════════════════════════════════════════════════════════

@dataclass
class TimingProfile:
    """Human-like action timing ranges (seconds)."""
    # Your observed reaction times — you're faster than avg
    preflop_fold: Tuple[float, float] = (0.8, 2.5)    # fast fold
    preflop_raise: Tuple[float, float] = (1.5, 4.0)    # think a bit
    flop_decision: Tuple[float, float] = (2.0, 6.0)   # think more
    turn_decision: Tuple[float, float] = (2.5, 8.0)   # harder decisions
    river_decision: Tuple[float, float] = (3.0, 10.0) # hardest
    click_hold: Tuple[float, float] = (0.06, 0.18)    # button press duration
    between_actions: Tuple[float, float] = (0.3, 1.2)  # gap between clicks
    session_break_chance: float = 0.15  # 15% chance to take a "thinking break"
    break_duration: Tuple[float, float] = (5.0, 30.0)  # how long to pause


class HumanTimer:
    """Generates human-like delays with anti-pattern protection."""

    def __init__(self, profile: TimingProfile = None):
        self.profile = profile or TimingProfile()
        self._history = deque(maxlen=20)  # prevent repeating patterns
        self._session_start = time.time()

    def delay(self, min_s: float, max_s: float, reason: str = "") -> float:
        """Sleep for a random duration in [min_s, max_s], avoiding repeats."""
        t = random.uniform(min_s, max_s)

        # Anti-pattern: never repeat the last 3 delays
        while len(self._history) >= 3 and any(
            abs(t - h) < 0.05 for h in list(self._history)[-3:]
        ):
            t = random.uniform(min_s, max_s)

        # Add micro-jitter (human inconsistency)
        t += random.gauss(0, 0.02)
        t = max(0.1, t)

        self._history.append(t)
        time.sleep(t)
        return t

    def decision_delay(self, street: str = "flop") -> float:
        """Human-like thinking time before acting."""
        p = self.profile
        if street == "preflop":
            r = p.preflop_fold if random.random() < 0.4 else p.preflop_raise
        elif street == "flop":
            r = p.flop_decision
        elif street == "turn":
            r = p.turn_decision
        elif street == "river":
            r = p.river_decision
        else:
            r = p.flop_decision
        return self.delay(r[0], r[1], f"think_{street}")

    def click_hold(self) -> float:
        """Random mouse button hold duration."""
        p = self.profile
        return self.delay(p.click_hold[0], p.click_hold[1], "click")

    def between_actions(self) -> float:
        """Gap between sequential actions."""
        p = self.profile
        return self.delay(p.between_actions[0], p.between_actions[1], "gap")

    def maybe_break(self) -> bool:
        """Occasionally take a longer 'thinking' break."""
        if random.random() < self.profile.session_break_chance:
            t = random.uniform(*self.profile.break_duration)
            time.sleep(t)
            return True
        return False

    def session_age(self) -> float:
        """Minutes since session started."""
        return (time.time() - self._session_start) / 60.0


# ═══════════════════════════════════════════════════════════════
# MOUSE — Bezier curve movement with human-like acceleration
# ═══════════════════════════════════════════════════════════════

class BezierMouse:
    """
    Human-like mouse movement using cubic bezier curves.
    Key human traits:
    - Curved paths (not straight lines)
    - Variable speed (faster in middle, slower at start/end)
    - Slight overshoot + correction on long moves
    - Click position jitter within targets
    """

    def __init__(self, speed_px_per_sec: float = 800):
        self.speed = speed_px_per_sec
        self._last_pos = (0, 0)
        self._move_history = deque(maxlen=30)

    def _bezier_point(self, p0, p1, p2, p3, t: float) -> Tuple[float, float]:
        """Cubic bezier: B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3"""
        mt = 1 - t
        mt2, mt3 = mt * mt, mt * mt * mt
        t2, t3 = t * t, t * t * t
        x = mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0]
        y = mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
        return (x, y)

    def _generate_control_points(self, start, end) -> Tuple:
        """Generate 2 control points for natural curve."""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.sqrt(dx * dx + dy * dy)

        # Curve offset proportional to distance, randomized
        offset = dist * random.uniform(0.15, 0.35)
        angle = math.atan2(dy, dx)

        # Perpendicular offset
        perp = angle + math.pi / 2 * random.choice([-1, 1])

        cp1 = (
            start[0] + dx * 0.3 + math.cos(perp) * offset * random.uniform(0.5, 1.0),
            start[1] + dy * 0.3 + math.sin(perp) * offset * random.uniform(0.5, 1.0),
        )
        cp2 = (
            start[0] + dx * 0.7 + math.cos(perp) * offset * random.uniform(-1.0, -0.5),
            start[1] + dy * 0.7 + math.sin(perp) * offset * random.uniform(-1.0, -0.5),
        )
        return cp1, cp2

    def move_to(self, x: int, y: int, duration_ms: float = None) -> float:
        """
        Move mouse from current position to (x, y) using bezier curve.
        Returns actual duration in seconds.
        """
        start = self._current_pos()
        end = (float(x), float(y))

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 2:
            return 0  # Already there

        # Duration: proportional to distance, with human variance
        if duration_ms is None:
            base_ms = (dist / self.speed) * 1000
            # Humans are inconsistent with speed
            variance = random.gauss(0, base_ms * 0.15)
            base_ms = max(50, base_ms + variance)

            # Longer moves have slight pauses (micro-adjustments)
            if dist > 200:
                base_ms += random.uniform(50, 200)
        else:
            base_ms = duration_ms

        duration_s = base_ms / 1000.0

        # Number of steps (50-80 fps equivalent for smooth movement)
        n_steps = max(10, int(base_ms / random.uniform(10, 16)))

        # Generate control points for bezier
        cp1, cp2 = self._generate_control_points(start, end)

        # Execute movement with variable speed
        for i in range(n_steps + 1):
            t = i / n_steps

            # Non-linear timing (ease-in-out)
            # Speed profile: slower at start and end, faster in middle
            t_adj = self._ease_in_out(t)

            px, py = self._bezier_point(start, cp1, cp2, end, t_adj)

            # Micro-jitter (human hand tremor, ~1-2px)
            if random.random() < 0.3:
                px += random.gauss(0, 1.5)
                py += random.gauss(0, 1.5)

            try:
                self._set_pos(int(px), int(py))
            except Exception:
                pass  # Platform-specific call

            # Variable step delay
            step_delay = duration_s / n_steps
            # Slightly slower at start (positioning) and end (precision)
            if t < 0.1 or t > 0.85:
                step_delay *= random.uniform(1.1, 1.4)
            time.sleep(step_delay)

        self._last_pos = end
        self._move_history.append((end, time.time()))
        return duration_s

    def _ease_in_out(self, t: float) -> float:
        """Smooth ease-in-out: slow->fast->slow."""
        # Cubic ease-in-out
        if t < 0.5:
            return 4 * t * t * t
        return 1 - pow(-2 * t + 2, 3) / 2

    def click(self, x: int = None, y: int = None, button: str = "left"):
        """Click at position with human-like characteristics."""
        if x is not None and y is not None:
            # Add position jitter (never click same pixel)
            jx = int(random.gauss(0, 3))  # 3px std dev
            jy = int(random.gauss(0, 3))
            self.move_to(x + jx, y + jy)

        # Human click: press, micro-delay, release
        try:
            self._mouse_down(button)
            hold_s = random.uniform(0.06, 0.15)  # human button press
            time.sleep(hold_s)
            self._mouse_up(button)
        except Exception:
            pass

    def jitter_mouse(self):
        """Occasional micro-movement (idle hands). Like a human adjusting grip."""
        if random.random() < 0.3:
            x, y = self._current_pos()
            dx = random.randint(-3, 3)
            dy = random.randint(-3, 3)
            self._set_pos(x + dx, y + dy)

    # Platform-specific — override these for your OS
    def _current_pos(self) -> Tuple[float, float]:
        try:
            import pyautogui
            return pyautogui.position()
        except ImportError:
            # Fallback: Quartz on macOS
            try:
                import Quartz
                pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
                return (pos.x, pos.y)
            except ImportError:
                return self._last_pos

    def _set_pos(self, x: int, y: int):
        try:
            import pyautogui
            pyautogui.moveTo(x, y, _pause=False)
        except ImportError:
            try:
                import Quartz
                ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventMouseMoved, (x, y), 0)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            except ImportError:
                pass

    def _mouse_down(self, button: str = "left"):
        try:
            import pyautogui
            pyautogui.mouseDown(button=button, _pause=False)
        except ImportError:
            pass

    def _mouse_up(self, button: str = "left"):
        try:
            import pyautogui
            pyautogui.mouseUp(button=button, _pause=False)
        except ImportError:
            pass


# ═══════════════════════════════════════════════════════════════
# ANTI-DETECTION — Bet sizing & behavioral camouflage
# ═══════════════════════════════════════════════════════════════

class BetSizingStealth:
    """Makes bet sizes look human, not algorithmically precise."""

    @staticmethod
    def humanize_bet(target_bb: float, pot_bb: float) -> float:
        """
        Add human-like noise to bet sizing.
        Humans don't bet exactly 66.7% pot — they round, use sliders, type.
        """
        # Convert to chips/actual amount
        target_pct = target_bb / pot_bb if pot_bb > 0 else 0.66

        # Human rounding patterns:
        if target_pct < 0.4:
            # Small bets: humans round to nearest 0.5BB or nice fraction
            noise = random.gauss(0, 0.15)
            result = target_bb + noise
            result = round(result * 2) / 2  # round to 0.5BB
        elif target_pct < 0.8:
            # Medium bets: slider imprecision, ±5% of intended
            noise_pct = random.gauss(0, 0.03)
            result = target_bb * (1 + noise_pct)
            result = round(result, 1)
        else:
            # Large/overbet: often round numbers
            result = round(target_bb + random.gauss(0, 0.4), 1)

        return max(0.5, result)

    @staticmethod
    def slider_simulation(target_pct: float) -> List[float]:
        """
        Simulate human using a slider: approach target with corrections.
        Returns sequence of intermediate values.
        """
        steps = []
        current = 0.0

        # Overshoot then correct
        overshoot = target_pct * random.uniform(1.05, 1.2)
        steps.append(overshoot)

        # Correct downward
        correction = target_pct * random.uniform(0.95, 1.02)
        steps.append(correction)

        return steps


# ═══════════════════════════════════════════════════════════════
# PATTERN AVOIDANCE
# ═══════════════════════════════════════════════════════════════

class PatternAvoidance:
    """Prevents detectable behavioral patterns across sessions."""

    def __init__(self):
        self._action_counts = {}
        self._timestamps = deque(maxlen=100)

    def vary_decision(self, solver_action: str, solver_freq: float) -> str:
        """
        Occasionally deviate from pure GTO for camouflage.
        Humans sometimes make 'mistakes' — 5-8% deviation rate.
        """
        if random.random() < 0.06:  # 6% humanization
            alternatives = {
                "CHECK": "BET_33", "BET_33": "CHECK",
                "BET_66": "BET_33", "BET_100": "BET_66",
                "FOLD": "CALL", "CALL": "FOLD",
                "BET": "CHECK", "RAISE": "CALL",
            }
            normalized = solver_action.upper()
            if "%" in normalized:
                normalized = normalized.split("%")[0].strip()
            alt = alternatives.get(normalized)
            if alt:
                return alt
        return solver_action

    def record_action(self, action: str):
        """Track actions so we can detect if bot gets too predictable."""
        self._action_counts[action] = self._action_counts.get(action, 0) + 1
        self._timestamps.append((time.time(), action))

    def is_repetitive(self, action: str, window: int = 10) -> bool:
        """Check if the same action is being repeated suspiciously."""
        if len(self._timestamps) < 3:
            return False
        recent_actions = list(self._timestamps)[-window:]
        # Count actions in recent history (timestamps store (time, action_str) tuples)
        count = sum(1 for entry in recent_actions if isinstance(entry, tuple) and entry[1] == action)
        return count > window * 0.8
