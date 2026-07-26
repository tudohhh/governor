"""
Poker bot core — main loop integrating:
  table_reader  → screen capture & game state parsing
  Governor GTO  → decision engine (pio_solver + postflop)
  stealth       → human-like mouse, timing, anti-detection
  executor      → action execution on table

Usage:
  python -m bot.bot_core

Configurable per site via TableConfig in table_reader.py.
"""
import sys
import os
import time
import json
import random
import signal
import traceback
from typing import Optional, Dict

# Ensure governor root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .table_reader import TableReader, TableConfig, GameState, Street
from .stealth import BezierMouse, HumanTimer, TimingProfile, PatternAvoidance
from .executor import ActionExecutor


class PokerBot:
    """
    Main bot controller. Reads table, decides with GTO, executes with stealth.

    DESIGNED FOR EDUCATIONAL USE ONLY.
    Using bots on real-money poker sites violates Terms of Service.
    """

    def __init__(self, config: TableConfig = None,
                 auto_sitout_minutes: int = 45,
                 max_hands: int = 0):
        self.config = config or TableConfig()
        self.reader = TableReader(self.config)
        self.mouse = BezierMouse()
        self.timer = HumanTimer(TimingProfile())
        self.pattern = PatternAvoidance()
        self.executor = ActionExecutor(self.config, self.mouse, self.timer)

        # Session management
        self.auto_sitout_minutes = auto_sitout_minutes  # 0 = disabled
        self.max_hands = max_hands  # 0 = unlimited
        self.hands_played = 0
        self._running = False
        self._session_log = []
        self._next_jitter = random.randint(6, 15)

        # Solver — lazy init
        self._solver = None
        self._postflop = None

        # Signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    # ═══ Solver lazy loading ═══

    def _get_solver(self):
        if self._solver is None:
            from pio_solver import PioSolver
            self._solver = PioSolver()
        return self._solver

    def _get_postflop_engine(self, state: GameState, villain_range):
        """Create a PostflopEngine configured for current hand."""
        from postflop import PostflopEngine
        from range_narrowing import initial_range

        # Hero cards as treys card ints
        from treys import Card
        hero_cards = tuple(Card.new(c) for c in state.hero_cards)

        # Villain position - estimate from hero position + action
        vill_pos = self._estimate_villain_position(state)

        # Determine villain range based on preflop action
        vill_range = initial_range(vill_pos)

        # Build engine
        engine = PostflopEngine(
            hero_cards=hero_cards,
            villain_range=vill_range,
            position="IP" if state.hero_position in ("BTN", "CO") else "OOP",
            opponent_type=self._detect_opponent_type(),
            stack=state.hero_stack,
            pot=state.pot,
            hero_position=state.hero_position,
            villain_position=vill_pos,
            villain_preflop_action="call",
        )
        return engine

    def _estimate_villain_position(self, state: GameState) -> str:
        """Guess villain position from hero position + action context."""
        # Simple heuristic: villain is typically to the right of hero
        pos_order = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
        try:
            hero_idx = pos_order.index(state.hero_position)
            villain_idx = (hero_idx - 1) % 6
            return pos_order[villain_idx]
        except ValueError:
            return "CO"

    def _detect_opponent_type(self) -> str:
        """Detect opponent playing style from HUD/session data."""
        # Default: standard. Could be extended with HUD stats.
        return "standard"

    # ═══ Decision engine ═══

    def decide(self, state: GameState) -> Dict:
        """
        Make a GTO-based decision for the current game state.
        Returns: {'action': str, 'amount': float, 'freq': float, ...}
        """
        from treys import Card

        # Build hero and villain ranges
        from app import GTO_RANGES
        hero_position = state.hero_position

        # Hero range based on position
        hero_range = GTO_RANGES["RFI"].get(hero_position, {"AA", "KK", "QQ", "JJ", "AKs"})
        hero_range_list = list(hero_range)[:30]  # top 30 combos for speed

        # Villain range: estimate from preflop action
        vill_position = self._estimate_villain_position(state)
        vill_range = GTO_RANGES["VS_RFI"]["call"].get(
            f"vs_{vill_position}",
            GTO_RANGES["VS_RFI"]["3bet"].get(f"vs_{vill_position}", {"JJ", "TT", "99", "88"}))
        vill_range_list = list(vill_range)[:25]

        # Convert hero cards to treys format
        board_cards = [Card.new(c) for c in state.board_cards]

        # Use solver for flop+turn+river
        if len(board_cards) >= 3:
            solver = self._get_solver()
            start_street = "river" if len(board_cards) >= 5 else \
                           "turn" if len(board_cards) >= 4 else "flop"

            try:
                result = solver.solve(
                    hero_range_list, vill_range_list, board_cards,
                    pot=state.pot, stack=state.hero_stack,
                    pos="IP", start=start_street, iters=200
                )

                if 'error' not in result and result.get('actions'):
                    # Extract primary action
                    actions = result['actions']
                    primary = max(actions, key=actions.get)
                    freq = actions[primary]

                    # Map to executor format
                    action_map = {
                        'CHECK': 'CHECK',
                        'FOLD': 'FOLD',
                        'CALL': 'CALL',
                    }
                    action = action_map.get(primary, 'BET')

                    # Extract bet size if it's a bet
                    amount = 0
                    if 'BET' in primary:
                        # Parse sizing from label like "BET 33%"
                        try:
                            pct_str = primary.split('%')[0].split()[-1]
                            pct = float(pct_str) / 100
                            amount = state.pot * pct
                        except (ValueError, IndexError):
                            amount = state.pot * 0.5

                    return {
                        'action': action,
                        'amount': round(amount, 1),
                        'freq': freq,
                        'ev': result.get('hero_ev', 0),
                        'solver_time': result.get('total_time', 0),
                    }

            except Exception as e:
                print(f"Solver error: {e}")

        # Fallback: heuristic decision via PostflopEngine
        try:
            engine = self._get_postflop_engine(state, vill_range_list)
            if len(board_cards) == 3:
                decision = engine.decide_flop(board_cards)
            elif len(board_cards) == 4:
                decision = engine.decide_turn(board_cards)
            elif len(board_cards) >= 5:
                decision = engine.decide_river(board_cards)
            else:
                # Preflop
                from app import preflop_decision, combo_to_hands
                from treys import Card as C

                hero_strs = [C.int_to_str(c) for c in board_cards] if board_cards else []
                combo = ""  # would need to convert hero cards to combo string
                return {'action': 'RAISE' if random.random() < 0.3 else 'FOLD', 'amount': 3, 'freq': 80}

            return {
                'action': decision.get('action', 'CHECK').upper(),
                'amount': decision.get('bet_size', 0),
                'freq': 80,
                'reason': decision.get('reason', ''),
            }
        except Exception as e:
            print(f"Engine error: {e}")
            return {'action': 'CHECK', 'amount': 0, 'freq': 50}

    # ═══ Main loop ═══

    def run(self):
        """Main bot loop. Reads table, decides, acts, repeats."""
        self._running = True
        print("[Bot] Starting...")
        print(f"[Bot] Auto-sitout: {self.auto_sitout_minutes}min | Max hands: {self.max_hands or '∞'}")
        print("[Bot] Press Ctrl+C to stop")

        last_action_time = time.time()
        idle_cycles = 0

        while self._running:
            try:
                # 1. Read table state
                state = self.reader.read_state()

                # 2. If it's our turn, decide and act
                if state.is_hero_turn and state.available_actions:
                    print(f"\n[Bot] Action required — {state.street.value} | "
                          f"Pot: {state.pot}BB | Stack: {state.hero_stack}BB")

                    # Make decision
                    decision = self.decide(state)
                    print(f"[Bot] Decision: {decision['action']}"
                          + (f" {decision['amount']}BB" if decision.get('amount') else "")
                          + f" (freq: {decision.get('freq', '?')}%)")

                    # Execute
                    result = self.executor.execute(decision, state)
                    print(f"[Bot] Executed: {result}")

                    self.hands_played += 1
                    last_action_time = time.time()
                    idle_cycles = 0

                    # Log
                    self._session_log.append({
                        'time': time.time(),
                        'street': state.street.value,
                        'hand': state.hero_cards,
                        'board': state.board_cards,
                        'pot': state.pot,
                        'decision': decision['action'],
                        'amount': decision.get('amount', 0),
                        'result': result,
                    })

                else:
                    # Not our turn — wait
                    idle_cycles += 1

                    # Irregular jitter to look human (idle hands)
                    if idle_cycles >= self._next_jitter:
                        self.mouse.jitter_mouse()
                        self._next_jitter = idle_cycles + random.randint(5, 18)

                    time.sleep(random.uniform(0.8, 1.5))

                # 3. Session management
                if self.auto_sitout_minutes and self.timer.session_age() > self.auto_sitout_minutes:
                    print(f"[Bot] Auto-sitout after {self.auto_sitout_minutes}min")
                    self.executor.sit_out_next_hand()
                    break

                if self.max_hands and self.hands_played >= self.max_hands:
                    print(f"[Bot] Reached max hands ({self.max_hands})")
                    break

                # 4. Occasional 'thinking break'
                self.timer.maybe_break()

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Bot] Error: {e}")
                traceback.print_exc()
                # Emergency: fold if error during action
                try:
                    self.executor.emergency_fold()
                except Exception:
                    pass
                time.sleep(1)

        self._shutdown()

    def _shutdown(self):
        """Clean shutdown."""
        self._running = False
        print(f"\n[Bot] Shutting down. {self.hands_played} hands played.")

        # Save session log
        if self._session_log:
            log_path = os.path.join(os.path.dirname(__file__), "..", "bot_session.json")
            with open(log_path, 'w') as f:
                json.dump(self._session_log, f, indent=2)
            print(f"[Bot] Session saved to {log_path}")

    def _handle_signal(self, signum, frame):
        """Handle Ctrl+C / SIGTERM gracefully."""
        print("\n[Bot] Signal received, shutting down...")
        self._running = False


# ═══ Entry point ═══

def main():
    """CLI entry point for the bot."""
    print("=" * 50)
    print("  Governor Poker Bot — Stealth Edition")
    print("  EDUCATIONAL USE ONLY")
    print("=" * 50)

    config = TableConfig()
    bot = PokerBot(
        config=config,
        auto_sitout_minutes=45,
        max_hands=0,  # unlimited
    )
    bot.run()


if __name__ == "__main__":
    main()
