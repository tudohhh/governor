import streamlit as st
import random
from treys import Card, Evaluator
from board_analyzer import analyze_flop, describe_board
from equity import equity_vs_range, eq_to_string, all_cards, remove_cards
from postflop import PostflopEngine

evaluator = Evaluator()
RANKS = "AKQJT98765432"
SUITS = "shdc"
POSITIONS = ["UTG","HJ","CO","BTN","SB","BB"]

SUIT_MAP = {"i":"h","r":"d","t":"c","f":"s"}
SUIT_MAP_REV = {v:k for k,v in SUIT_MAP.items()}
SUIT_NAMES = {"i":"♥","r":"♦","t":"♣","f":"♠"}

def ro_to_treys(card_ro):
    card_ro = card_ro.strip()
    if card_ro.startswith("10"):
        rank = "T"
        suit = card_ro[2].lower()
    else:
        rank = card_ro[0].upper()
        suit = card_ro[1].lower()
    return rank + SUIT_MAP.get(suit, suit)

def card_display(card_ro):
    if card_ro.startswith("10"):
        rank = "10"
        suit = card_ro[2].lower()
    else:
        rank = card_ro[0].upper()
        suit = card_ro[1].lower()
    return rank + SUIT_NAMES.get(suit, suit)

def parse_board(board_str):
    cards = []
    i = 0
    while i < len(board_str):
        if i+1 < len(board_str) and board_str[i] == "1" and board_str[i+1] == "0":
            cards.append(board_str[i:i+3])
            i += 3
        else:
            cards.append(board_str[i:i+2])
            i += 2
    return cards

def hand_to_combo(cards_ro):
    c1 = ro_to_treys(cards_ro[0])
    c2 = ro_to_treys(cards_ro[1])
    r1, r2 = c1[0], c2[0]
    s1, s2 = c1[1], c2[1]
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 > i2:
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1 == r2:
        return r1 + r2
    if s1 == s2:
        return r1 + r2 + "s"
    return r1 + r2 + "o"

GTO_RANGES = {
 "RFI":{
  "UTG":{"AA","KK","QQ","JJ","TT","99","88","77","AKs","AQs","AJs","ATs","A5s","A4s","KQs","KJs","KTs","QJs","QTs","JTs","T9s","98s","AKo","AQo","AJo","KQo"},
  "HJ":{"AA","KK","QQ","JJ","TT","99","88","77","66","AKs","AQs","AJs","ATs","A9s","A8s","A5s","A4s","A3s","KQs","KJs","KTs","K9s","QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","AKo","AQo","AJo","ATo","KQo","KJo"},
  "CO":{"AA","KK","QQ","JJ","TT","99","88","77","66","55","AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s","KQs","KJs","KTs","K9s","K8s","QJs","QTs","Q9s","Q8s","JTs","J9s","J8s","T9s","T8s","98s","87s","76s","65s","AKo","AQo","AJo","ATo","A9o","KQo","KJo","KTo","QJo","QTo","JTo"},
  "BTN":{"AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22","AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s","KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","QJs","QTs","Q9s","Q8s","Q7s","Q6s","JTs","J9s","J8s","J7s","T9s","T8s","T7s","98s","97s","87s","86s","76s","75s","65s","64s","54s","53s","43s","AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o","A4o","KQo","KJo","KTo","K9o","QJo","QTo","Q9o","JTo","J9o","T9o","98o"},
  "SB":{"AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22","AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s","KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s","JTs","J9s","J8s","J7s","T9s","T8s","T7s","98s","97s","87s","86s","76s","75s","65s","64s","54s","53s","43s","AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o","A4o","A3o","KQo","KJo","KTo","K9o","K8o","QJo","QTo","Q9o","JTo","J9o","T9o","98o","87o"}
 },
 "VS_RFI":{
  "3bet":{
   "vs_UTG":{"AA","KK","QQ","JJ","AKs","AQs","AKo"},
   "vs_HJ":{"AA","KK","QQ","JJ","TT","AKs","AQs","AJs","AKo","AQo"},
   "vs_CO":{"AA","KK","QQ","JJ","TT","99","AKs","AQs","AJs","ATs","A5s","KQs","AKo","AQo","AJo"},
   "vs_BTN":{"AA","KK","QQ","JJ","TT","99","88","AKs","AQs","AJs","ATs","A5s","A4s","KQs","KJs","QJs","AKo","AQo","AJo"},
  },
  "call":{
   "vs_UTG":{"TT","99","88","77","AJs","ATs","A5s","A4s","KQs","KJs","QJs","JTs","T9s","98s"},
   "vs_HJ":{"99","88","77","66","ATs","A9s","A5s","A4s","KQs","KJs","KTs","QJs","QTs","JTs","T9s","98s","87s"},
   "vs_CO":{"88","77","66","55","A9s","A8s","A7s","A6s","A4s","A3s","KJs","KTs","K9s","QTs","Q9s","JTs","J9s","T9s","T8s","98s","87s","76s","65s","ATo"},
   "vs_BTN":{"77","66","55","44","A9s","A8s","A7s","A6s","A3s","A2s","KTs","K9s","K8s","QTs","Q9s","Q8s","J9s","J8s","T9s","T8s","98s","97s","87s","86s","76s","75s","65s","54s","ATo","A9o","KQo","KJo","KTo","QJo","QTo","JTo"},
  }
 }
}

def combo_to_hands(combo):
    hands = []
    if len(combo) == 2:
        r = combo[0]
        for i, s1 in enumerate(SUITS):
            for s2 in SUITS[i+1:]:
                hands.append([Card.new(r+s1), Card.new(r+s2)])
    elif combo[2] == 's':
        for s in SUITS:
            hands.append([Card.new(combo[0]+s), Card.new(combo[1]+s)])
    else:
        for s1 in SUITS:
            for s2 in SUITS:
                if s1 != s2:
                    hands.append([Card.new(combo[0]+s1), Card.new(combo[1]+s2)])
    return hands

def calc_equity_vs_random(hero_cards_ro, board_ro=None, n=3000):
    hero = [Card.new(ro_to_treys(c)) for c in hero_cards_ro]
    board = [Card.new(ro_to_treys(c)) for c in board_ro] if board_ro else []
    dead = set(hero + board)
    rem = [Card.new(r+s) for r in RANKS for s in SUITS if Card.new(r+s) not in dead]
    w = t = 0
    for _ in range(n):
        random.shuffle(rem)
        sb = board + rem[2:2+5-len(board)]
        hs = evaluator.evaluate(sb, hero)
        vs = evaluator.evaluate(sb, rem[:2])
        if hs < vs: w += 1
        elif hs == vs: t += 1
    return round((w + t*0.5)/n*100, 1)

def calc_equity_vs_range(hero_cards_ro, vrange, board_ro=None, n=2000):
    hero = [Card.new(ro_to_treys(c)) for c in hero_cards_ro]
    board = [Card.new(ro_to_treys(c)) for c in board_ro] if board_ro else []
    dead = set(hero + board)
    vh = []
    for combo in vrange:
        for h in combo_to_hands(combo):
            if h[0] not in dead and h[1] not in dead:
                vh.append(h)
    if not vh:
        return 50.0
    rem_base = [Card.new(r+s) for r in RANKS for s in SUITS if Card.new(r+s) not in dead]
    w = t = 0
    for _ in range(n):
        v = random.choice(vh)
        rem = [c for c in rem_base if c not in v]
        random.shuffle(rem)
        sb = board + rem[:5-len(board)]
        hs = evaluator.evaluate(sb, hero)
        vs = evaluator.evaluate(sb, v)
        if hs < vs: w += 1
        elif hs == vs: t += 1
    return round((w + t*0.5)/n*100, 1)

PROFILES = {
    "Standard": {"range_mult": 1.0, "desc": "Joacă normal, range-uri echilibrate"},
    "Tight-Rock": {"range_mult": 0.5, "desc": "Joacă doar mâini premium. Raise = pericol."},
    "LAG": {"range_mult": 1.5, "desc": "Range larg, agresiv. Blufează des."},
    "Maniac": {"range_mult": 2.0, "desc": "Joacă orice, raise orice. Equity ta crește."},
    "Fish": {"range_mult": 1.8, "desc": "Dă call la tot. Value bet mare, nu blufa."},
    "Nit": {"range_mult": 0.3, "desc": "Mai tight decât un rock. Fold la orice raise."},
}

def get_adjusted_equity(eq_range, eq_rand, profile):
    mult = PROFILES[profile]["range_mult"]
    if mult < 1.0:
        base = eq_range if eq_range else eq_rand
        return base * (0.7 + 0.3 * mult)
    elif mult > 1.0:
        blend = min(mult - 1.0, 1.0)
        base = eq_range if eq_range else eq_rand
        return base + (eq_rand - base) * blend * 0.5
    return eq_range if eq_range else eq_rand

def preflop_decision(combo, hero_pos, sit="RFI", vpos=None):
    if sit == "RFI":
        rr = GTO_RANGES["RFI"].get(hero_pos, set())
        if combo in rr:
            return "RAISE", combo + " in range open " + hero_pos + " (" + str(len(rr)) + " combouri)"
        return "FOLD", combo + " NU e in range open " + hero_pos
    elif sit == "VS_RFI" and vpos:
        k = "vs_" + vpos
        b3 = GTO_RANGES["VS_RFI"]["3bet"].get(k, set())
        ca = GTO_RANGES["VS_RFI"]["call"].get(k, set())
        if combo in b3:
            return "3-BET", combo + " in 3-bet range vs " + vpos
        if combo in ca:
            return "CALL", combo + " in call range vs " + vpos
        return "FOLD", combo + " nu e in range vs " + vpos
    return "FOLD", "?"

def postflop_decision(eq, pot, bet):
    if bet == 0:
        if eq > 65:
            return "BET", "Equity " + str(eq) + "% > 65% — value bet"
        if eq > 45:
            return "CHECK", "Equity " + str(eq) + "% — marginal"
        return "CHECK", "Equity " + str(eq) + "% — slab"
    po = bet / (pot + bet) * 100
    if eq > po + 10:
        return "RAISE", "Equity " + str(eq) + "% >> pot odds " + str(round(po)) + "%"
    if eq > po:
        return "CALL", "Equity " + str(eq) + "% > pot odds " + str(round(po)) + "%"
    if eq > po - 5:
        return "CALL (marginal)", "Equity " + str(eq) + "% ~ pot odds " + str(round(po)) + "%"
    return "FOLD", "Equity " + str(eq) + "% < pot odds " + str(round(po)) + "%"

def render_range_grid(rs):
    rows = []
    for i, r1 in enumerate(RANKS):
        row = []
        for j, r2 in enumerate(RANKS):
            if i == j:
                c = r1 + r2
            elif i < j:
                c = r1 + r2 + "s"
            else:
                c = r2 + r1 + "o"
            row.append((c, c in rs))
        rows.append(row)
    return rows

def main():
    st.set_page_config(page_title="Poker GTO Coach", layout="wide", page_icon="♠")
    st.title("♠ Poker GTO Coach")
    st.caption("Equity reala | Range-uri GTO | Profil adversar | Drill")

    if "drill_correct" not in st.session_state:
        st.session_state.drill_correct = 0
    if "drill_total" not in st.session_state:
        st.session_state.drill_total = 0
    if "drill_combo" not in st.session_state:
        st.session_state.drill_combo = None
    if "postflop_scenario" not in st.session_state:
        st.session_state.postflop_scenario = None
    if "postflop_correct" not in st.session_state:
        st.session_state.postflop_correct = 0
    if "postflop_total" not in st.session_state:
        st.session_state.postflop_total = 0
    if "sparring_hand" not in st.session_state:
        st.session_state.sparring_hand = None
    if "sparring_street" not in st.session_state:
        st.session_state.sparring_street = "FLOP"
    if "sparring_score" not in st.session_state:
        st.session_state.sparring_score = {"correct": 0, "total": 0}

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Analiza Mana", "Range Viewer", "Drill Preflop", "Drill Postflop",
        "Sparring NL100", "Freq Drill", "ICM/Leaks", "Referinta"
    ])

    with tab1:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Input")
            st.caption("Notatie: A K Q J 10 9...2 + i(inima) r(romb) t(trefla) f(frunza)")
            c1 = st.text_input("Cartea 1", "Ai", key="c1")
            c2 = st.text_input("Cartea 2", "Kr", key="c2")
            pozitie = st.selectbox("Pozitia ta", POSITIONS, index=3)
            situatie = st.radio("Situatie", ["RFI (primul care actioneaza)", "Facing open raise", "Postflop"])

            villain_pos = None
            board_input = ""
            pot_size = 0
            bet_size = 0

            if situatie == "Facing open raise":
                villain_pos = st.selectbox("Villain position", ["UTG","HJ","CO","BTN","SB"])
            if situatie == "Postflop":
                board_input = st.text_input("Board (ex: 10iJf2t)", "")
                pot_size = st.number_input("Pot", min_value=0, value=100)
                bet_size = st.number_input("Bet de platit", min_value=0, value=0)

            profil = st.selectbox("Profil adversar", list(PROFILES.keys()))
            st.caption(PROFILES[profil]["desc"])
            analizeaza = st.button("Analizeaza", type="primary", use_container_width=True)

        with col2:
            if analizeaza:
                try:
                    hero_cards = [c1.strip(), c2.strip()]
                    combo = hand_to_combo(hero_cards)
                    disp = card_display(c1) + " " + card_display(c2)
                    st.subheader("Mana: " + disp + " (" + combo + ")")

                    with st.spinner("Calculez equity..."):
                        eq_rand = calc_equity_vs_random(hero_cards)

                    eq_range = None
                    action = ""
                    info = ""

                    if situatie == "RFI (primul care actioneaza)":
                        action, info = preflop_decision(combo, pozitie, "RFI")
                        st.metric("Equity vs random", str(eq_rand) + "%")

                    elif situatie == "Facing open raise" and villain_pos:
                        action, info = preflop_decision(combo, pozitie, "VS_RFI", villain_pos)
                        v_range = GTO_RANGES["RFI"].get(villain_pos, set())
                        if v_range:
                            with st.spinner("Equity vs range " + villain_pos + "..."):
                                eq_range = calc_equity_vs_range(hero_cards, v_range)
                        mc1, mc2 = st.columns(2)
                        mc1.metric("Equity vs random", str(eq_rand) + "%")
                        if eq_range:
                            mc2.metric("Equity vs range " + villain_pos, str(eq_range) + "%")

                    elif situatie == "Postflop" and board_input:
                        board_cards = parse_board(board_input.strip())
                        bd = " ".join(card_display(c) for c in board_cards)
                        st.write("Board: " + bd)
                        with st.spinner("Equity pe board..."):
                            eq_rand = calc_equity_vs_random(hero_cards, board_cards)
                        action, info = postflop_decision(eq_rand, pot_size, bet_size)
                        st.metric("Equity vs random", str(eq_rand) + "%")

                    if profil != "Standard":
                        eq_adj = get_adjusted_equity(eq_range, eq_rand, profil)
                        delta = round(eq_adj - eq_rand, 1)
                        st.metric("Equity ajustata (profil)", str(round(eq_adj, 1)) + "%",
                                  delta=str(delta) + "% vs raw")

                    if action:
                        if "FOLD" in action:
                            st.error("❌ " + action)
                        elif "RAISE" in action or "3-BET" in action:
                            st.success("🔺 " + action)
                        elif "CALL" in action:
                            st.info("📞 " + action)
                        elif "BET" in action:
                            st.warning("💰 " + action)
                        else:
                            st.info("✋ " + action)
                        st.write("💡 " + info)

                    st.progress(min(eq_rand / 100, 1.0))

                except Exception as e:
                    st.error("Eroare: " + str(e))
                    st.caption("Verifica notatia: Ai=A♥, Kr=K♦, 10t=10♣, Jf=J♠")

    with tab2:
        st.subheader("Range-uri GTO Preflop")
        range_pos = st.selectbox("Pozitie", ["UTG","HJ","CO","BTN","SB"], key="rp")
        rng = GTO_RANGES["RFI"].get(range_pos, set())
        st.write(str(len(rng)) + " combouri in range-ul de open raise din " + range_pos)

        grid = render_range_grid(rng)
        header = "| |" + "|".join(r for r in RANKS) + "|"
        sep = "|---|" + "|".join("---" for _ in RANKS) + "|"
        lines = [header, sep]
        for i, r1 in enumerate(RANKS):
            cells = [r1]
            for j, (combo, in_range) in enumerate(grid[i]):
                cells.append("🟩" if in_range else "⬛")
            lines.append("|" + "|".join(cells) + "|")
        st.markdown("\n".join(lines))
        st.caption("🟩 = in range | ⬛ = fold")

    with tab3:
        st.subheader("Drill — Antrenament Preflop")

        if st.session_state.drill_total > 0:
            pct = st.session_state.drill_correct / st.session_state.drill_total * 100
            st.metric("Scor", str(st.session_state.drill_correct) + "/" + str(st.session_state.drill_total) + " (" + str(round(pct)) + "%)")

        if st.button("Situatie noua", use_container_width=True):
            r1 = random.choice(list(RANKS))
            r2 = random.choice(list(RANKS))
            if r1 == r2:
                combo = r1 + r2
            elif random.random() > 0.5:
                if RANKS.index(r1) > RANKS.index(r2):
                    r1, r2 = r2, r1
                combo = r1 + r2 + "s"
            else:
                if RANKS.index(r1) > RANKS.index(r2):
                    r1, r2 = r2, r1
                combo = r1 + r2 + "o"
            hp = random.choice(["UTG","HJ","CO","BTN","SB"])

            if random.random() > 0.4:
                rr = GTO_RANGES["RFI"].get(hp, set())
                correct = "RAISE" if combo in rr else "FOLD"
                st.session_state.drill_combo = {
                    "combo": combo, "pos": hp, "sit": "RFI",
                    "correct": correct, "desc": "Foldeaza pana la tine"
                }
            else:
                vp = random.choice(["UTG","HJ","CO","BTN"])
                vi = POSITIONS.index(vp)
                vh = [p for p in POSITIONS[vi+1:] if p != "BB"]
                hp = random.choice(vh) if vh else "BB"
                k = "vs_" + vp
                b3 = GTO_RANGES["VS_RFI"]["3bet"].get(k, set())
                ca = GTO_RANGES["VS_RFI"]["call"].get(k, set())
                if combo in b3:
                    correct = "3-BET"
                elif combo in ca:
                    correct = "CALL"
                else:
                    correct = "FOLD"
                st.session_state.drill_combo = {
                    "combo": combo, "pos": hp, "sit": "VS_RFI",
                    "correct": correct, "desc": vp + " deschide 3x"
                }

        d = st.session_state.drill_combo
        if d:
            st.markdown("### " + d["combo"] + " din " + d["pos"])
            st.write("Situatie: " + d["desc"])

            if d["sit"] == "RFI":
                options = ["RAISE", "FOLD"]
            else:
                options = ["3-BET", "CALL", "FOLD"]

            cols = st.columns(len(options))
            for i, opt in enumerate(options):
                if cols[i].button(opt, key="drill_" + opt, use_container_width=True):
                    st.session_state.drill_total += 1
                    if opt == d["correct"]:
                        st.session_state.drill_correct += 1
                        st.success("CORECT! " + d["combo"] + " -> " + d["correct"])
                    else:
                        st.error("GRESIT. Corect: " + d["correct"])
                    st.session_state.drill_combo = None
                    st.rerun()

        if st.button("Reseteaza scor"):
            st.session_state.drill_correct = 0
            st.session_state.drill_total = 0
            st.rerun()

    with tab4:
        st.subheader("♣ Drill Postflop — NL100")
        st.caption("Antreneaza decizii pe flop, turn, river. GTO-based.")

        col_pf1, col_pf2 = st.columns([1, 2])

        with col_pf1:
            opp_type = st.selectbox("Profil adversar", ["standard", "nit", "lag", "fish", "maniac"],
                                     key="pf_opp")
            if st.button("Genereaza Scenariu", type="primary", use_container_width=True, key="gen_pf"):
                # Generate random scenario
                deck = all_cards()
                random.shuffle(deck)
                hero = (deck[0], deck[1])
                dead = list(hero)
                remaining = remove_cards(deck, dead)
                board = remaining[:3]

                # Villain range based on position
                vpos = random.choice(["UTG", "HJ", "CO", "BTN"])
                vrange = list(GTO_RANGES["RFI"].get(vpos, set()))
                pos = "IP" if random.random() > 0.5 else "OOP"

                st.session_state.postflop_scenario = {
                    "hero": hero,
                    "board": board,
                    "vrange": vrange[:20],
                    "position": pos,
                    "opponent": opp_type,
                }

        with col_pf2:
            sc = st.session_state.postflop_scenario
            if sc:
                hero_str = " ".join(Card.int_to_pretty_str(c) for c in sc["hero"])
                board_str = " ".join(Card.int_to_pretty_str(c) for c in sc["board"])
                st.markdown(f"### 🤚 {hero_str}")
                st.markdown(f"### 📋 Flop: {board_str}")
                st.caption(f"Poziție: **{sc['position']}** | Adversar: **{sc['opponent']}** | Stack: 100BB | Pot: 7.5BB")

                # Board analysis
                flop = analyze_flop(sc["board"])
                tex = describe_board(flop)
                st.info(f"Board: **{tex}** | High: {flop['high_card']} | Wetness: {flop['wetness']}")

                engine = PostflopEngine(
                    sc["hero"], sc["vrange"],
                    position=sc["position"],
                    opponent_type=sc["opponent"],
                    pot=7.5, stack=100
                )
                gto = engine.decide_flop(sc["board"])
                eq_str = eq_to_string(gto["equity"])

                st.progress(gto["equity"], text=f"Equity: {eq_str}")

                # Decision buttons
                st.markdown("### Acțiunea ta:")
                acts = ["BET 1/3 pot", "BET 2/3 pot", "BET pot", "CHECK", "CHECK-FOLD"]
                cols = st.columns(len(acts))
                for i, act in enumerate(acts):
                    if cols[i].button(act, key=f"pf_{act}", use_container_width=True):
                        user_action = act.split(" ")[0]
                        correct_action = gto["action"]
                        is_correct = (user_action == correct_action or
                                      (user_action == "BET" and correct_action == "BET") or
                                      (user_action == "CHECK" and correct_action == "CHECK") or
                                      (user_action == "CHECK-FOLD" and correct_action == "FOLD"))

                        st.session_state.postflop_total += 1
                        if is_correct:
                            st.session_state.postflop_correct += 1
                            st.success(f"✅ CORECT! GTO: {gto['action']} ({gto.get('sizing_bb', 0)}BB)")
                        else:
                            st.error(f"❌ GRESIT. GTO: {gto['action']} ({gto.get('sizing_bb', 0)}BB)")
                        st.info(f"**Raționament:** {gto['reasoning']}")
                        st.caption(f"Sizing recomandat: {gto.get('sizing', 0)*100:.0f}% pot")

                # Score
                if st.session_state.postflop_total > 0:
                    pct = st.session_state.postflop_correct / st.session_state.postflop_total * 100
                    st.metric("Scor Postflop", f"{st.session_state.postflop_correct}/{st.session_state.postflop_total}", f"{pct:.0f}%")

        if st.button("Reseteaza scor postflop", key="reset_pf"):
            st.session_state.postflop_correct = 0
            st.session_state.postflop_total = 0
            st.rerun()

    with tab5:
        st.subheader("♠ Sparring NL100 — Mână completă")
        st.caption("Simulează o mână întreagă: preflop → flop → turn → river. Engine-ul decide GTO.")

        col_s1, col_s2 = st.columns([1, 2])

        with col_s1:
            hero_pos = st.selectbox("Poziția ta", ["UTG","HJ","CO","BTN","SB","BB"], index=3, key="sp_pos")
            vill_pos = st.selectbox("Poziția villain", ["UTG","HJ","CO","BTN","SB","BB"], index=5, key="sp_vpos")
            opp_type = st.selectbox("Profil adversar", ["standard","nit","lag","fish","maniac"], key="sp_opp")
            stack_size = st.slider("Stack (BB)", 50, 200, 100, key="sp_stack")

            if st.button("🔄 Mână nouă", type="primary", use_container_width=True, key="sp_new"):
                random.seed()
                deck = all_cards()
                random.shuffle(deck)
                hero = (deck[0], deck[1])
                dead = list(hero)
                remaining = remove_cards(deck, dead)
                board = remaining[:3]

                # Determine position
                pos_order = ["UTG","HJ","CO","BTN","SB","BB"]
                hero_ip = pos_order.index(hero_pos) > pos_order.index(vill_pos)
                position = "IP" if hero_ip else "OOP"

                from range_narrowing import initial_range
                vrange = initial_range(vill_pos)

                engine = PostflopEngine(
                    hero, vrange, position=position,
                    opponent_type=opp_type, stack=stack_size, pot=7.5,
                    hero_position=hero_pos, villain_position=vill_pos,
                )

                flop_result = engine.decide_flop(board)

                st.session_state.sparring_hand = {
                    "hero": hero,
                    "board_flop": board,
                    "vrange": vrange,
                    "position": position,
                    "opponent": opp_type,
                    "engine": engine,
                    "flop_result": flop_result,
                    "turn_board": None,
                    "river_board": None,
                    "turn_result": None,
                    "river_result": None,
                }
                st.session_state.sparring_street = "FLOP"
                st.rerun()

        with col_s2:
            sh = st.session_state.sparring_hand
            if sh:
                hero_str = " ".join(Card.int_to_pretty_str(c) for c in sh["hero"])
                board_str = " ".join(Card.int_to_pretty_str(c) for c in sh["board_flop"])
                st.markdown(f"### 🤚 {hero_str}")
                st.markdown(f"### 📋 Flop: {board_str}")
                st.caption(f"Poziție: **{sh['position']}** ({sh.get('hero_position','BTN')} vs {sh.get('villain_position','BB')}) | "
                          f"Adversar: **{sh['opponent']}** | Stack: {stack_size}BB")

                fr = sh["flop_result"]
                st.info(f"Board: **{fr['texture']}** | Equity: **{fr['equity_str']}** | "
                       f"Range adv: **{fr.get('range_advantage','?')}** | "
                       f"Blocanți: **{fr.get('blockers','?')}**")

                st.progress(fr["equity"], text=f"Equity vs range: {fr['equity_str']}")

                st.markdown("#### Acțiune GTO recomandată:")
                action_color = {"BET": "green", "CHECK": "orange", "RAISE": "red", "CALL": "blue", "FOLD": "gray"}
                color = action_color.get(fr["action"], "black")
                st.markdown(f"**:{color}[{fr['action']}]** {fr.get('sizing_bb', '')}BB — *{fr['reasoning']}*")

                if sh["flop_result"]["action"] in ("BET", "CHECK"):
                    if st.button("▶️ Continuă pe Turn", key="sp_turn"):
                        engine = sh["engine"]
                        board_4 = list(sh["board_flop"])
                        remaining2 = remove_cards(all_cards(), list(sh["hero"]) + board_4)
                        turn_card = random.choice(remaining2)
                        board_4.append(turn_card)
                        turn_result = engine.decide_turn(board_4, flop_action=fr["action"])
                        sh["turn_board"] = board_4
                        sh["turn_result"] = turn_result
                        st.session_state.sparring_street = "TURN"
                        st.rerun()

                # Show turn results
                if sh.get("turn_result"):
                    tr = sh["turn_result"]
                    turn_card_str = Card.int_to_pretty_str(sh["turn_board"][-1])
                    st.markdown("---")
                    st.markdown(f"### 🂭 Turn: {turn_card_str}")
                    st.progress(tr["equity"], text=f"Equity: {tr['equity_str']}")
                    scare = "⚠️ Scare card! " if tr.get("scare_card") else ""
                    st.markdown(f"**:{color}[{tr['action']}]** — {scare}{tr.get('reasoning','')}")

                    if tr["action"] in ("BET", "CHECK"):
                        if st.button("▶️ Continuă pe River", key="sp_river"):
                            engine = sh["engine"]
                            board_5 = list(sh["turn_board"])
                            remaining3 = remove_cards(all_cards(), list(sh["hero"]) + board_5)
                            river_card = random.choice(remaining3)
                            board_5.append(river_card)
                            river_result = engine.decide_river(board_5, action_history=[
                                sh["flop_result"]["action"], tr.get("action","CHECK")
                            ])
                            sh["river_board"] = board_5
                            sh["river_result"] = river_result
                            st.session_state.sparring_street = "RIVER"
                            st.rerun()

                # Show river
                if sh.get("river_result"):
                    rr = sh["river_result"]
                    river_card_str = Card.int_to_pretty_str(sh["river_board"][-1])
                    st.markdown("---")
                    st.markdown(f"### 🂭 River: {river_card_str}")
                    st.progress(rr["equity"], text=f"Equity: {rr['equity_str']}")
                    st.markdown(f"**:{color}[{rr['action']}]** — {rr.get('reasoning','')}")
                    if "villain_distribution" in rr:
                        vd = rr["villain_distribution"]
                        st.caption(f"Range villain: strong={vd['strong']}% medium={vd['medium']}% weak={vd['weak']}% | "
                                  f"Range rămas: {rr.get('range_narrowed','?')} combos")

    with tab6:
        st.subheader("🎯 Frequency Drill")
        st.caption("Antrenează frecvențele GTO, nu doar deciziile individuale.")

        from trainer_advanced import FrequencyDrill
        if "freq_drill" not in st.session_state:
            st.session_state.freq_drill = None
        if "freq_responses" not in st.session_state:
            st.session_state.freq_responses = []

        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            if st.button("Generează Scenariu", type="primary", key="gen_freq"):
                drill = FrequencyDrill()
                drill.generate_scenario()
                st.session_state.freq_drill = drill
                st.session_state.freq_responses = []
                st.rerun()

            if st.session_state.freq_drill:
                fd = st.session_state.freq_drill
                st.info(f"Decizii: **{len(fd.responses)}/{fd.num_repetitions}**")
                if len(fd.responses) >= fd.num_repetitions:
                    score = fd.get_score()
                    st.metric("Scor Frecvență", f"{score['score']*100:.0f}%")
                    st.caption(score['feedback'])

        with col_f2:
            if st.session_state.freq_drill:
                fd = st.session_state.freq_drill
                sc = fd.scenario
                hero_s = " ".join(Card.int_to_pretty_str(c) for c in sc["hero"])
                board_s = " ".join(Card.int_to_pretty_str(c) for c in sc["board"])
                st.markdown(f"### {hero_s} pe {board_s}")
                st.caption(f"{sc['texture']} | Equity: {sc['equity']*100:.0f}% | GTO: {sc['gto_action']}")

                if len(fd.responses) < fd.num_repetitions:
                    c1, c2 = st.columns(2)
                    if c1.button("BET", key="freq_bet", use_container_width=True):
                        fd.record_response("BET")
                        st.session_state.freq_responses = fd.responses
                        st.rerun()
                    if c2.button("CHECK", key="freq_chk", use_container_width=True):
                        fd.record_response("CHECK")
                        st.session_state.freq_responses = fd.responses
                        st.rerun()
                else:
                    freqs = fd.get_score()
                    st.progress(freqs["frequencies"]["BET"], text=f"BET: {freqs['frequencies']['BET']*100:.0f}% (țintă: {freqs['targets']['BET']*100:.0f}%)")
                    st.progress(freqs["frequencies"]["CHECK"], text=f"CHECK: {freqs['frequencies']['CHECK']*100:.0f}% (țintă: {freqs['targets']['CHECK']*100:.0f}%)")

    with tab7:
        st.subheader("💰 ICM & Leak Finder")
        st.caption("Calcule ICM pentru turnee + analiză leak-uri.")

        col_i1, col_i2 = st.columns(2)
        with col_i1:
            st.markdown("#### Calculator ICM")
            stack_input = st.text_input("Stack-uri (separate prin virgulă)", "1000,800,600,400", key="icm_stacks")
            payout_input = st.text_input("Payouts (separate prin virgulă)", "0.5,0.3,0.2", key="icm_payouts")

            if st.button("Calculează ICM", key="calc_icm"):
                try:
                    from icm import icm_equity, tournament_stage_adjustment
                    stacks = [float(s.strip()) for s in stack_input.split(",")]
                    payouts = [float(p.strip()) for p in payout_input.split(",")]
                    while len(payouts) < len(stacks):
                        payouts.append(0.0)
                    eqs = icm_equity(stacks, payouts[:len(stacks)])
                    st.success("ICM Equity:")
                    for i, (s, eq) in enumerate(zip(stacks, eqs)):
                        st.write(f"Jucător {i+1} ({s:.0f} chips): **{eq*100:.1f}%** din prize pool")

                    stage = tournament_stage_adjustment(stacks, [50, 100], payouts)
                    st.info(f"Stage: **{stage['stage']}** | Deschidere: {stage['open_size']} | "
                           f"Hero: {stage['hero_bb']:.0f}BB")
                except Exception as e:
                    st.error(f"Eroare: {e}")

        with col_i2:
            st.markdown("#### Leak Finder")
            st.caption("Analizează deciziile tale și găsește pattern-uri.")

            if "leak_finder" not in st.session_state:
                st.session_state.leak_finder = None

            if st.button("Simulează Sesiune (20 mâini)", key="sim_session"):
                from trainer_advanced import LeakFinder
                lf = LeakFinder()
                actions = ["BET", "CHECK", "FOLD", "CALL"]
                for _ in range(20):
                    lf.add_decision({
                        "street": "FLOP",
                        "user_action": "BET" if random.random() < 0.75 else random.choice(actions),
                        "bet_faced": 0 if random.random() < 0.7 else random.randint(3, 8),
                        "sizing": random.choice([0.33, 0.50, 0.66]),
                    })
                st.session_state.leak_finder = lf
                st.rerun()

            if st.session_state.leak_finder:
                result = st.session_state.leak_finder.analyze()
                st.metric("Decizii analizate", result["total_decisions"])
                st.metric("Leak-uri găsite", result["leaks_found"])
                for leak in result.get("leaks", []):
                    sev_color = {"high": "red", "medium": "orange", "low": "blue"}
                    st.markdown(f"**:{sev_color.get(leak['severity'],'gray')}[{leak['severity'].upper()}]** "
                               f"{leak['detail']}")
                    st.caption(f"💡 Fix: {leak['fix']}")

    with tab8:
        st.subheader("Referinta Rapida")
        st.markdown("""
**Notatie carti:**
- Ranks: A K Q J 10 9 8 7 6 5 4 3 2
- Culori: **i**=inima, **r**=romb, **t**=trefla, **f**=frunza/pica
- Exemple: Ai=A inima, Kr=K romb, 10t=10 trefla, Jf=J frunza

**Pozitii (6-max):** UTG, HJ, CO, BTN, SB, BB

**Actiuni GTO:**
- **RFI** = First in (deschizi tu)
- **3-BET** = Re-raise vs open
- **Call** = Echitezi
- **Fold** = Nu joci mana

**Profiluri adversar:**
- **Standard** — Range normal
- **Tight-Rock** — Doar premium, respecta raise-ul lui
- **LAG** — Range larg + agresiv
- **Maniac** — Raise orice, equity ta creste
- **Fish** — Call la tot, value bet mare
- **Nit** — Ultra-tight, fold la presiune
        """)

if __name__ == "__main__":
    main()
