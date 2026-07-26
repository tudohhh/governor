"""
Advanced training: frequency drill (same texture, different scenarios),
real leak finder (HH-based analysis), hand reviewer.
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
    Frequency drill: N different scenarios with similar board texture.
    Tests if you can maintain correct frequencies, not memorize answers.
    """

    def __init__(self, num_scenarios=10):
        self.num_scenarios = num_scenarios
        self.scenarios = []
        self.responses = []
        self.current_idx = 0

    def generate(self, hero_position="BTN", villain_position="BB",
                 opponent_type="standard"):
        """Generate N scenarios with similar texture but different cards."""
        deck = all_cards()
        random.shuffle(deck)

        # First scenario determines the texture class
        hero = (deck[0], deck[1])
        remaining = remove_cards(deck, list(hero))
        base_board = remaining[:3]
        base_texture = analyze_flop(base_board)
        target_class = base_texture["wetness"]

        pos_order = ["UTG","HJ","CO","BTN","SB","BB"]
        ip = pos_order.index(hero_position) > pos_order.index(villain_position)
        position = "IP" if ip else "OOP"

        vrange = initial_range(villain_position)
        engine = PostflopEngine(hero, vrange, position=position,
                                opponent_type=opponent_type,
                                hero_position=hero_position,
                                villain_position=villain_position)
        base_result = engine.decide_flop(base_board)

        # Record first scenario
        self.scenarios.append({
            "hero": hero, "board": base_board, "texture": base_result["texture"],
            "equity": base_result["equity"], "gto_action": base_result["action"],
            "gto_reasoning": base_result["reasoning"],
        })

        # Generate N-1 more with same texture class
        attempts = 0
        while len(self.scenarios) < self.num_scenarios and attempts < 100:
            attempts += 1
            deck2 = all_cards()
            random.shuffle(deck2)
            h2 = (deck2[0], deck2[1])
            rem2 = remove_cards(deck2, list(h2))
            b2 = rem2[:3]
            tex2 = analyze_flop(b2)

            if tex2["wetness"] != target_class or tex2["paired"] != base_texture["paired"]:
                continue

            try:
                eng2 = PostflopEngine(h2, vrange, position=position,
                                      opponent_type=opponent_type,
                                      hero_position=hero_position,
                                      villain_position=villain_position)
                res2 = eng2.decide_flop(b2)
                self.scenarios.append({
                    "hero": h2, "board": b2, "texture": res2["texture"],
                    "equity": res2["equity"], "gto_action": res2["action"],
                    "gto_reasoning": res2["reasoning"],
                })
            except:
                continue

        self.responses = []
        self.current_idx = 0
        return self.scenarios[0] if self.scenarios else None

    def record(self, action):
        self.responses.append(action)
        self.current_idx += 1

    def current_scenario(self):
        if self.current_idx < len(self.scenarios):
            return self.scenarios[self.current_idx]
        return None

    def is_done(self):
        return self.current_idx >= len(self.scenarios)

    def results(self):
        if not self.responses:
            return {"score": 0, "feedback": "Nicio decizie"}

        # Compare frequencies
        gto_actions = [s["gto_action"] for s in self.scenarios[:len(self.responses)]]
        bet_expected = sum(1 for a in gto_actions if a == "BET") / len(gto_actions)
        bet_actual = sum(1 for a in self.responses if a == "BET") / len(self.responses)

        check_expected = 1 - bet_expected
        check_actual = 1 - bet_actual

        bet_dev = abs(bet_actual - bet_expected)
        check_dev = abs(check_actual - check_expected)

        score = 1.0 - (bet_dev + check_dev)

        # Check alternation (consecutive same action is worse than alternating)
        runs = 0
        for i in range(1, len(self.responses)):
            if self.responses[i] != self.responses[i-1]:
                runs += 1
        alt_score = min(1.0, runs / max(1, len(self.responses) - 1))

        feedback = []
        if bet_dev > 0.12:
            direction = "des" if bet_actual > bet_expected else "rar"
            feedback.append(f"Bet-ezi prea {direction} ({bet_actual*100:.0f}% vs țintă {bet_expected*100:.0f}%)")
        if alt_score < 0.4:
            feedback.append("Alternează mai mult — nu da același răspuns consecutiv")

        return {
            "score": round(max(0, score), 3),
            "alternation_score": round(alt_score, 3),
            "bet_actual": round(bet_actual, 3),
            "bet_expected": round(bet_expected, 3),
            "total": len(self.responses),
            "feedback": " | ".join(feedback) if feedback else "Frecvențe excelente!",
        }


class LeakFinder:
    """
    Analyzes poker decisions and finds systematic leaks.
    Works with real hand histories, not simulated data.
    """

    def __init__(self):
        self.decisions = []

    def add_decision(self, d):
        self.decisions.append(d)

    def add_from_hand_history(self, hands):
        """Import decisions from parsed hand histories."""
        for hand in hands:
            analysis = hand if isinstance(hand, dict) else {}
            actions = analysis.get("actions", [])
            for act in actions:
                self.decisions.append(act)

    def analyze(self):
        if len(self.decisions) < 5:
            return {"insufficient": True, "message": "Minim 5 decizii necesare"}

        leaks = []

        # 1. C-bet frequency
        cbet_opps = [d for d in self.decisions
                    if d.get("street") == "flop" and d.get("aggressor") == "hero"]
        if cbet_opps:
            freq = sum(1 for d in cbet_opps if d.get("action") == "bet") / len(cbet_opps)
            if freq > 0.75:
                leaks.append({"type": "C-bet prea frecvent", "severity": "high",
                              "detail": f"{freq*100:.0f}% — scoate din range air-ul complet",
                              "fix": "Check-ează 25-35% din range pe flop"})
            elif freq < 0.40:
                leaks.append({"type": "C-bet prea rar", "severity": "medium",
                              "detail": f"{freq*100:.0f}% — pierzi value",
                              "fix": "Bet-ează orice board uscat când ai range advantage"})

        # 2. Fold to c-bet
        faced = [d for d in self.decisions
                if d.get("street") == "flop" and d.get("aggressor") == "villain"]
        if faced:
            fold_freq = sum(1 for d in faced if d.get("action") == "fold") / len(faced)
            if fold_freq > 0.70:
                leaks.append({"type": "Fold-ezi prea mult la c-bet", "severity": "high",
                              "detail": f"{fold_freq*100:.0f}% — te exploatează ușor",
                              "fix": "Apără MDF: cheamă cu backdoor draws + overcards"})
            elif fold_freq < 0.35:
                leaks.append({"type": "Chemi prea mult la c-bet", "severity": "medium",
                              "detail": f"Doar {fold_freq*100:.0f}% fold — plătești prea des",
                              "fix": "Fold-ează bottom of range pe board-uri wet"})

        # 3. Turn aggression
        turn_opps = [d for d in self.decisions
                    if d.get("street") == "turn" and d.get("aggressor") == "hero"]
        if turn_opps:
            bet_freq = sum(1 for d in turn_opps if d.get("action") == "bet") / len(turn_opps)
            if bet_freq < 0.25:
                leaks.append({"type": "Pasiv pe turn", "severity": "medium",
                              "detail": f"{bet_freq*100:.0f}% barrel — prea pasiv",
                              "fix": "Double barrel când ai equity și range advantage"})
            elif bet_freq > 0.65:
                leaks.append({"type": "Prea agresiv pe turn", "severity": "low",
                              "detail": f"{bet_freq*100:.0f}% — verifică mai mult",
                              "fix": "Pot control cu equity marginală"})

        # 4. River calling frequency
        river_facing = [d for d in self.decisions
                       if d.get("street") == "river" and d.get("aggressor") == "villain"]
        if river_facing:
            call_freq = sum(1 for d in river_facing if d.get("action") == "call") / len(river_facing)
            if call_freq > 0.70:
                leaks.append({"type": "Call-ezi prea mult pe river", "severity": "high",
                              "detail": f"{call_freq*100:.0f}% call — hero call prea des",
                              "fix": "River-ul e value-heavy. Fold fără bluff catcher solid"})
            elif call_freq < 0.15:
                leaks.append({"type": "Fold-ezi prea mult pe river", "severity": "low",
                              "detail": f"Doar {call_freq*100:.0f}% call — exploitabil",
                              "fix": "Bluff catch vs LAG cu bluff catcher"})

        # 5. Sizing variability
        sizes = [d.get("sizing", 0) for d in self.decisions
                if d.get("action") == "bet" and d.get("sizing", 0) > 0]
        if len(sizes) > 5:
            unique_sizes = len(set(round(s, 1) for s in sizes))
            if unique_sizes <= 1:
                leaks.append({"type": "Sizing predictibil", "severity": "low",
                              "detail": f"Doar {unique_sizes} mărime de bet — prea previzibil",
                              "fix": "Variează: 33% pe dry, 66% pe wet, overbet la river"})

        # 6. Check-raise frequency
        cbet_faced_flop = [d for d in self.decisions
                          if d.get("street") == "flop" and d.get("aggressor") == "villain"]
        if cbet_faced_flop:
            raises = sum(1 for d in cbet_faced_flop if d.get("action") in ("raise", "check-raise"))
            raise_freq = raises / len(cbet_faced_flop)
            if raise_freq < 0.03 and len(cbet_faced_flop) > 15:
                leaks.append({"type": "Zero check-raise-uri", "severity": "medium",
                              "detail": "Nu faci niciodată check-raise — range-ul tău e transparent",
                              "fix": "Check-raise 5-8% din range: combo draws + set-uri"})

        return {
            "total": len(self.decisions),
            "leaks_count": len(leaks),
            "leaks": leaks,
            "summary": f"{len(leaks)} leak-uri în {len(self.decisions)} decizii",
        }


class HandReviewer:
    """Review a complete hand street-by-street."""

    def review(self, hero_cards, board_progression, actions_taken,
               villain_range, position="IP", opponent_type="standard"):
        feedback = []
        engine = PostflopEngine(hero_cards, villain_range, position=position,
                                opponent_type=opponent_type)

        for board, act_info in zip(board_progression, actions_taken):
            street = act_info.get("street", "FLOP")
            user_action = act_info.get("action", "?")
            bet_faced = act_info.get("bet_faced", 0)

            if street == "FLOP":
                gto = engine.decide_flop(board, bet_faced)
            elif street == "TURN":
                gto = engine.decide_turn(board, bet_faced=bet_faced)
            elif street == "RIVER":
                gto = engine.decide_river(board, bet_faced=bet_faced)
            else:
                continue

            correct = user_action == gto["action"]
            feedback.append({
                "street": street,
                "board": [Card.int_to_pretty_str(c) for c in board],
                "your_action": user_action,
                "gto_action": gto["action"],
                "correct": correct,
                "equity": gto.get("equity", 0),
                "reasoning": gto.get("reasoning", ""),
            })

        correct = sum(1 for f in feedback if f["correct"])
        return {
            "street_feedback": feedback,
            "correct": correct,
            "total": len(feedback),
            "score": round(correct / max(1, len(feedback)), 3),
        }
