"""
Action executor — translates solver decisions into human-like table actions.
Uses BezierMouse + HumanTimer from stealth module.
"""
import time
import random
from typing import Dict, Optional
from .stealth import BezierMouse, HumanTimer, BetSizingStealth, PatternAvoidance
from .table_reader import TableConfig, GameState


class ActionExecutor:
    """
    Executes poker actions on the table with full stealth profile.
    Supports: fold, check, call, bet (typed or slider), raise.
    """

    def __init__(self, config: TableConfig = None,
                 mouse: BezierMouse = None,
                 timer: HumanTimer = None):
        self.config = config or TableConfig()
        self.mouse = mouse or BezierMouse()
        self.timer = timer or HumanTimer()
        self.bet_stealth = BetSizingStealth()
        self.pattern = PatternAvoidance()
        self._last_action_time = 0

    def execute(self, decision: Dict, state: GameState) -> str:
        """
        Execute a poker action decision.

        decision dict from bot_core/decision engine:
        {
            'action': 'BET',       # FOLD, CHECK, CALL, BET, RAISE
            'amount': 3.5,         # BB (for bet/raise)
            'freq': 65.0,          # solver frequency (%)
            'sizing': '33%',       # sizing label
        }
        Returns the executed action string.
        """
        action = decision.get("action", "CHECK").upper()
        amount = decision.get("amount", 0)

        # Apply pattern variability
        action = self.pattern.vary_decision(action, decision.get("freq", 100))

        # Human-like thinking delay before acting
        self.timer.decision_delay(state.street.value)

        # Occasional micro-mouse-jitter (idle hands)
        self.mouse.jitter_mouse()

        # Execute based on action type
        result = action
        if action == "FOLD":
            self._click_button(self.config.fold_button)
            result = "FOLD"
        elif action == "CHECK":
            self._click_button(self.config.check_button)
            result = "CHECK"
        elif action == "CALL":
            self._click_button(self.config.call_button)
            result = "CALL"
        elif action in ("BET", "RAISE"):
            self._execute_bet(amount, is_raise=(action == "RAISE"))
            result = f"{action}_{amount:.1f}BB"
        else:
            self._click_button(self.config.check_button)  # safe default
            result = "CHECK"

        self.timer.between_actions()
        self.pattern.record_action(result)
        self._last_action_time = time.time()
        return result

    def _click_button(self, button_region):
        """Click a button with human-like movement."""
        rx, ry, rw, rh = button_region
        # Random position within button (never the center)
        abs_x, abs_y, abs_w, abs_h = self._region_abs(button_region)
        target_x = abs_x + random.randint(abs_w // 4, 3 * abs_w // 4)
        target_y = abs_y + random.randint(abs_h // 4, 3 * abs_h // 4)

        self.mouse.move_to(target_x, target_y)
        self.timer.click_hold()  # brief pause before click
        self.mouse.click(target_x, target_y)

    def _execute_bet(self, amount_bb: float, is_raise: bool = False):
        """Execute a bet or raise with human-like slider/typing behavior."""
        button = self.config.raise_button if is_raise else self.config.call_button

        # Click the raise/bet button area
        self._click_button(button)

        # Small delay (human reading the bet input)
        time.sleep(random.uniform(0.2, 0.5))

        # Method 1: Simulate slider drag (most human-like)
        if random.random() < 0.6:  # 60% slider, 40% type
            self._simulate_slider(amount_bb)
        else:
            self._type_bet_amount(amount_bb)

        # Confirm bet (click bet/raise button again or press Enter)
        time.sleep(random.uniform(0.15, 0.35))

        # Press Enter to confirm
        try:
            import pyautogui
            pyautogui.press("enter")
        except ImportError:
            self._click_button(button)

    def _simulate_slider(self, target_bb: float):
        """Simulate human dragging the bet slider."""
        slider_region = self.config.bet_slider
        rx, ry, rw, rh = self._region_abs(slider_region)

        # Slider goes from 0 (left) to pot (right)
        # Target position along the slider x-axis
        # Estimate pot from slider range — heuristic
        slider_value = min(1.0, target_bb / 20)  # approximate
        target_x = rx + int(rw * slider_value)
        target_y = ry + rh // 2 + random.randint(-3, 3)

        # Human slider: overshoot, then correct
        overshoot = min(rx + rw, max(rx, target_x + random.choice([-1, 1]) * random.randint(8, 28)))
        self.mouse.move_to(overshoot, target_y)
        time.sleep(random.uniform(0.1, 0.2))

        # Correct
        self.mouse.move_to(target_x, target_y)
        time.sleep(random.uniform(0.05, 0.1))

    def _type_bet_amount(self, amount_bb: float):
        """Type bet amount via keyboard (less human-like, but common)."""
        # Humanize the amount (add noise)
        amount = self.bet_stealth.humanize_bet(amount_bb, 10)

        # Format as string
        if amount < 1:
            amount_str = f"{amount:.2f}"
        elif amount < 10:
            amount_str = f"{amount:.1f}"
        else:
            amount_str = f"{int(amount)}"

        # Click bet input field
        input_region = self.config.bet_input
        self._click_button(input_region)

        # Clear existing value
        try:
            import pyautogui
            pyautogui.hotkey("command", "a")  # select all
            time.sleep(0.05)
        except ImportError:
            pass

        # Type each character with human-like rhythm
        for char in amount_str:
            try:
                import pyautogui
                pyautogui.write(char, interval=random.uniform(0.05, 0.15))
            except ImportError:
                pass

        time.sleep(random.uniform(0.1, 0.25))

    def _region_abs(self, region_frac):
        """Convert fractional region to absolute screen coords."""
        rx, ry, rw, rh = region_frac
        x = self.config.table_left + int(rx * self.config.table_width)
        y = self.config.table_top + int(ry * self.config.table_height)
        w = int(rw * self.config.table_width)
        h = int(rh * self.config.table_height)
        return x, y, w, h

    def emergency_fold(self):
        """Emergency: fold immediately (triggered on errors or timeouts)."""
        try:
            self._click_button(self.config.fold_button)
        except Exception:
            pass

    def sit_out_next_hand(self):
        """Sit out next hand — for session management / stealth breaks."""
        try:
            import pyautogui
            # Common hotkey or button position varies per site
            pyautogui.hotkey("command", "s")  # PokerStars sit out
        except ImportError:
            pass
