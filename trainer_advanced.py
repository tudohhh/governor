"""
Advanced training modes: frequency drill, leak finder, hand review.
"""
import random
from collections import defaultdict, Counter
from treys import Card
from board_analyzer import analyze_flop, describe_board
from postflop import PostflopEngine
from range_narrowing import initial_range
from equity import all_cards, remove_cards


class FrequencyDrill:
    """
    Frequency-based training: instead of single decisions,
    present the same scenario multiple times and track bet/check ratio.
    """

    def __init__(self, hero_position="BTN", villain_position="BB",
                 opponent_type="standard", num_repetitions=10):
        self.hero_position = hero_position
        self.villain_position = villain_position
        self.opponent_type = opponent_type
        self.num_repetitions = num_repetitions
        self.scenario = None
        self.responses = []
        self.target_frequency = {}

    def generate_scenario(self):
        """Generate a fixed scenario for frequency drill."""
        deck = all_cards()
        random.shuffle(deck)
        hero = (deck[0], deck[1])
        dead = list(hero)
        remaining = remove_cards(deck, dead)
        board = remaining[:3]
        vrange = initial_range(self.villain_position)

        pos_order = ["UTG","HJ","CO","BTN","SB","BB"]
        ip = pos_order.index(self.hero_position) > pos_order.index(self.villain_position)
        position = "IP" if ip else "OOP"

        engine = PostflopEngine(hero, vrange, position=position,
                                opponent_type=self.opponent_type,
                                hero_position=self.hero_position,
                                villain_position=self.villain_position)

        result = engine.decide_flop(board)

        # Target frequency from GTO (simplified)
        self.target_frequency = {
            "BET": 0.65 if result["action"] == "BET" else 0.35,
            "CHECK": 0.35 if result["action"] == "BET" else 0.65,
        }

        self.scenario = {
            "hero": hero,
            "board": board,
            "hero_position": self.hero_position,
            "villain_position": self.villain_position,
            "texture": result["texture"],
            "equity": result["equity"],
            "gto_action": result["action"],
            "gto_reasoning": result["reasoning"],
        }
        self.responses = []
        return self.scenario

    def record_response(self, action):
        """Record a single response (BET or CHECK)."""
        self.responses.append(action)

    def get_score(self):
        """Calculate how well frequencies match GTO target."""
        if not self.responses:
            return {"score": 0, "feedback": "Nicio decizie înregistrată"}

        counts = Counter(self.responses)
        total = len(self.responses)
        freqs = {action: counts.get(action, 0) / total
                 for action in ["BET", "CHECK"]}

        # Score: 1.0 = perfect match, 0.0 = completely wrong
        bet_score = 1.0 - min(1.0, abs(freqs["BET"] - self.target_frequency["BET"]) * 3)
        check_score = 1.0 - min(1.0, abs(freqs["CHECK"] - self.target_frequency["CHECK"]) * 3)
        overall = (bet_score + check_score) / 2

        feedback = []
        if abs(freqs["BET"] - self.target_frequency["BET"]) > 0.15:
            direction = "mult" if freqs["BET"] > self.target_frequency["BET"] else "puțin"
            feedback.append(f"Bet-ezi prea {direction} ({freqs['BET']*100:.0f}% vs target {self.target_frequency['BET']*100:.0f}%)")

        return {
            "score": round(overall, 3),
            "frequencies": {k: round(v, 3) for k, v in freqs.items()},
            "targets": self.target_frequency,
            "total_responses": total,
            "feedback": " | ".join(feedback) if feedback else "Frecvențe bune!"
        }


class LeakFinder:
    """
    Analyze a batch of decisions and identify systematic leaks.
    """

    def __init__(self):
        self.decisions = []

    def add_decision(self, decision: dict):
        """Add a decision to the analysis pool."""
        self.decisions.append(decision)

    def analyze(self):
        """Find patterns in mistakes."""
        if len(self.decisions) < 5:
            return {"status": "insufficient_data", "message": "Minim 5 decizii necesare"}

        leaks = []

        # C-bet frequency analysis
        cbet_situations = [d for d in self.decisions if d.get("street") == "FLOP"
                          and d.get("bet_faced", 0) == 0]
        if cbet_situations:
            cbet_count = sum(1 for d in cbet_situations if d.get("user_action") == "BET")
            cbet_freq = cbet_count / len(cbet_situations)
            if cbet_freq > 0.80:
                leaks.append({
                    "type": "cbet_too_high",
                    "severity": "high",
                    "detail": f"C-bet {cbet_freq*100:.0f}% — prea mult. Ținta: 55-70%",
                    "fix": "Verifică mai mult pe flop cu equity marginală",
                })
            elif cbet_freq < 0.40:
                leaks.append({
                    "type": "cbet_too_low",
                    "severity": "medium",
                    "detail": f"C-bet {cbet_freq*100:.0f}% — prea puțin. Ținta: 55-70%",
                    "fix": "C-bet-ează mai mult pe board-uri uscate, chiar și fără equity",
                })

        # Fold-to-cbet analysis
        faced_cbet = [d for d in self.decisions if d.get("bet_faced", 0) > 0
                     and d.get("street") == "FLOP"]
        if faced_cbet:
            folds = sum(1 for d in faced_cbet if d.get("user_action") == "FOLD")
            fold_freq = folds / len(faced_cbet)
            if fold_freq > 0.75:
                leaks.append({
                    "type": "fold_too_much",
                    "severity": "high",
                    "detail": f"Fold la c-bet {fold_freq*100:.0f}% — prea mult. Ținta: 45-60%",
                    "fix": "Apără mai mult: chemi cu overcards, backdoor draws, și pocket pairs",
                })

        # Turn aggression
        turn_decisions = [d for d in self.decisions if d.get("street") == "TURN"
                         and d.get("bet_faced", 0) == 0]
        if turn_decisions:
            turn_bets = sum(1 for d in turn_decisions if d.get("user_action") == "BET")
            turn_agg = turn_bets / len(turn_decisions)
            if turn_agg < 0.25:
                leaks.append({
                    "type": "passive_on_turn",
                    "severity": "medium",
                    "detail": f"Turn aggression {turn_agg*100:.0f}% — pasiv. Ținta: 35-50%",
                    "fix": "Double barrel pe turn când ai range advantage",
                })

        # Sizing consistency
        bet_sizes = [d.get("sizing", 0) for d in self.decisions
                    if d.get("user_action") == "BET"]
        if bet_sizes:
            avg_size = sum(bet_sizes) / len(bet_sizes)
            if avg_size < 0.30:
                leaks.append({
                    "type": "bet_too_small",
                    "severity": "low",
                    "detail": f"Sizing mediu {avg_size*100:.0f}% — mic. Ținta: 40-80%",
                    "fix": "Mărește sizing-ul pe board-uri wet și când ai value",
                })

        return {
            "total_decisions": len(self.decisions),
            "leaks_found": len(leaks),
            "leaks": leaks,
            "summary": f"Analizate {len(self.decisions)} decizii, găsite {len(leaks)} leak-uri",
        }


class HandReviewer:
    """
    Review a complete hand and provide street-by-street feedback.
    """

    def review(self, hero_cards, board_progression, actions_taken,
               villain_range, position="IP", opponent_type="standard"):
        """
        board_progression: list of [flop_3, turn_4?, river_5?]
        actions_taken: list of {street: ..., action: ..., sizing: ...}
        """
        feedback = []
        engine = PostflopEngine(hero_cards, villain_range, position=position,
                                opponent_type=opponent_type)

        for i, (board, action_info) in enumerate(zip(board_progression, actions_taken)):
            street = action_info.get("street", f"STREET_{i}")
            user_action = action_info.get("action", "?")
            bet_faced = action_info.get("bet_faced", 0)

            if street == "FLOP":
                gto = engine.decide_flop(board, bet_faced)
            elif street == "TURN":
                gto = engine.decide_turn(board, bet_faced=bet_faced)
            elif street == "RIVER":
                gto = engine.decide_river(board, bet_faced=bet_faced)
            else:
                continue

            correct = (user_action == gto["action"] or
                      (user_action == "BET" and gto["action"] == "BET"))

            fb = {
                "street": street,
                "board": [Card.int_to_pretty_str(c) for c in board],
                "your_action": user_action,
                "gto_action": gto["action"],
                "correct": correct,
                "equity": gto.get("equity", 0),
                "gto_reasoning": gto.get("reasoning", ""),
            }
            feedback.append(fb)

        # Overall score
        correct_count = sum(1 for f in feedback if f["correct"])
        overall = correct_count / len(feedback) if feedback else 0

        return {
            "street_feedback": feedback,
            "correct": correct_count,
            "total": len(feedback),
            "score": round(overall, 3),
        }
