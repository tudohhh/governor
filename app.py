import streamlit as st
import random
import json
from treys import Card, Evaluator

evaluator = Evaluator()
RANKS = "AKQJT98765432"
SUITS = "shdc"
POSITIONS = ["UTG","HJ","CO","BTN","SB","BB"]

# ═══ NOTAȚIE ROMÂNĂ → TREYS ═══
SUIT_MAP = {"i":"h","r":"d","t":"c","f":"s"}  # inimă,romb,treflă,frunză
SUIT_MAP_REV = {v:k for k,v in SUIT_MAP.items()}
RANK_MAP = {"10":"T"}
SUIT_NAMES = {"i":"♥","r":"♦","t":"♣","f":"♠"}
SUIT_COLORS = {"i":"red","r":"red","t":"black","f":"black"}

def ro_to_treys(card_ro):
    """Convertește Ai→Ah, Kr→Kd, 10i→Th, Jf→Js"""
    card_ro = card_ro.strip()
    if card_ro.startswith("10"):
        rank = "T"
        suit = card_ro[2].lower()
    else:
        rank = card_ro[0].upper()
        suit = card_ro[1].lower()
    suit_treys = SUIT_MAP.get(suit, suit)
    return rank + suit_treys

def treys_to_ro(card_treys):
    """Convertește Ah→Ai, Kd→Kr, Th→10i"""
    rank = card_treys[0]
    suit = card_treys[1]
    suit_ro = SUIT_MAP_REV.get(suit, suit)
    if rank == "T":
        return "10" + suit_ro
    return rank + suit_ro

def parse_card(s):
    return Card.new(ro_to_treys(s))

def parse_board(board_str):
    """Parsează board: 10iJf2t → [Th, Js, 2c]"""
    cards = []
    i = 0
    while i < len(board_str):
        if board_str[i:i+2].isdigit() or (board_str[i] == "1" and i+1 < len(board_str) and board_str[i+1] == "0"):
            cards.append(board_str[i:i+3])
            i += 3
        else:
            cards.append(board_str[i:i+2])
            i += 2
    return cards

def card_display(card_ro):
    """Afișează cărți frumos: Ai → A♥"""
    if card_ro.startswith("10"):
        rank = "10"
        suit = card_ro[2].lower()
    else:
        rank = card_ro[0].upper()
        suit = card_ro[1].lower()
    symbol = SUIT_NAMES.get(suit, suit)
    return f"{rank}{symbol}"

def hand_to_combo(cards_ro):
    c1 = ro_to_treys(cards_ro[0])
    c2 = ro_to_treys(cards_ro[1])
    r1, r2 = c1[0], c2[0]
    s1, s2 = c1[1], c2[1]
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 > i2: r1,r2=r2,r1; s1,s2=s2,s1
    if r1==r2: return r1+r2
    return r1+r2+("s" if s1==s2 else "o")

# ═══ GTO RANGES ═══
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

# ═══ EQUITY ENGINE ═══
def combo_to_hands(combo):
    hands=[]
    if len(combo)==2:
        r=combo[0]
        for i,s1 in enumerate(SUITS):
            for s2 in SUITS[i+1:]: hands.append([Card.new(r+s1),Card.new(r+s2)])
    elif combo[2]==\'s\':
        for s in SUITS: hands.append([Card.new(combo[0]+s),Card.new(combo[1]+s)])
    else:
        for s1 in SUITS:
            for s2 in SUITS:
                if s1!=s2: hands.append([Card.new(combo[0]+s1),Card.new(combo[1]+s2)])
    return hands

def calc_equity_vs_random(hero_cards_ro, board_ro=None, n=3000):
    hero = [Card.new(ro_to_treys(c)) for c in hero_cards_ro]
    board = [Card.new(ro_to_treys(c)) for c in board_ro] if board_ro else []
    dead = set(hero + board)
    rem = [Card.new(r+s) for r in RANKS for s in SUITS if Card.new(r+s) not in dead]
    w=t=0
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
            if h[0] not in dead and h[1] not in dead: vh.append(h)
    if not vh: return 50.0
    rem_base = [Card.new(r+s) for r in RANKS for s in SUITS if Card.new(r+s) not in dead]
    w=t=0
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

# ═══ ADVERSAR PROFILES ═══
PROFILES = {
    "Standard": {"range_mult": 1.0, "desc": "Joacă normal, range-uri echilibrate"},
    "Tight-Rock": {"range_mult": 0.5, "desc": "Joacă doar mâini premium. Raise = pericol."},
    "LAG (Loose-Aggressive)": {"range_mult": 1.5, "desc": "Range larg, agresiv. Blufează des."},
    "Maniac": {"range_mult": 2.0, "desc": "Joacă orice, raise orice. Equity ta crește."},
    "Fish (Calling Station)": {"range_mult": 1.8, "desc": "Dă call la tot. Value bet mare, nu blufa."},
    "Nit": {"range_mult": 0.3, "desc": "Mai tight decât un rock. Fold la orice raise."},
}

def get_adjusted_equity(equity_vs_range, equity_vs_random, profile):
    mult = PROFILES[profile]["range_mult"]
    if mult < 1.0:
        return equity_vs_range * (0.7 + 0.3 * mult) if equity_vs_range else equity_vs_random * 0.85
    elif mult > 1.0:
        blend = min(mult - 1.0, 1.0)
        base = equity_vs_range if equity_vs_range else equity_vs_random
        return base + (equity_vs_random - base) * blend * 0.5
    return equity_vs_range if equity_vs_range else equity_vs_random

# ═══ DECISION ENGINE ═══
def preflop_decision(combo, hero_pos, situation="RFI", villain_pos=None):
    if situation == "RFI":
        rr = GTO_RANGES["RFI"].get(hero_pos, set())
        if combo in rr: return "RAISE", f"{combo} în range open {hero_pos} ({len(rr)} combouri)"
        return "FOLD", f"{combo} NU e în range open {hero_pos}"
    elif situation == "VS_RFI" and villain_pos:
        k = f"vs_{villain_pos}"
        b3 = GTO_RANGES["VS_RFI"]["3bet"].get(k, set())
        ca = GTO_RANGES["VS_RFI"]["call"].get(k, set())
        if combo in b3: return "3-BET", f"{combo} în 3-bet range vs {villain_pos}"
        if combo in ca: return "CALL", f"{combo} în call range vs {villain_pos}"
        return "FOLD", f"{combo} nu e în range vs {villain_pos}"
    return "FOLD", "?"

def postflop_decision(eq, pot, bet):
    if bet == 0:
        if eq > 65: return "BET", f"Equity {eq}% > 65% — value bet"
        if eq > 45: return "CHECK", f"Equity {eq}% — marginal"
        return "CHECK", f"Equity {eq}% — slab"
    po = bet/(pot+bet)*100
    if eq > po+10: return "RAISE", f"Equity {eq}% >> pot odds {po:.0f}%"
    if eq > po: return "CALL", f"Equity {eq}% > pot odds {po:.0f}%"
    if eq > po-5: return "CALL (marginal)", f"Equity {eq}% ≈ pot odds {po:.0f}%"
    return "FOLD", f"Equity {eq}% < pot odds {po:.0f}%"

# ═══ RANGE GRID ═══
def render_range_grid(range_set):
    grid = []
    for i, r1 in enumerate(RANKS):
        row = []
        for j, r2 in enumerate(RANKS):
            if i == j: c = r1+r2
            elif i < j: c = r1+r2+"s"
            else: c = r2+r1+"o"
            row.append((c, c in range_set))
        grid.append(row)
    return grid

# ═══ STREAMLIT APP ═══
def main():
    st.set_page_config(page_title="Poker GTO Coach", layout="wide", page_icon="♠")

    st.markdown("""
    <style>
    .big-action { font-size: 2em; font-weight: bold; padding: 10px; border-radius: 10px; text-align: center; margin: 10px 0; }
    .raise-box { background: #1a472a; color: #4ade80; }
    .fold-box { background: #4a1a1a; color: #f87171; }
    .call-box { background: #1a3a4a; color: #60a5fa; }
    .bet-box { background: #4a3a1a; color: #fbbf24; }
    .check-box { background: #2a2a2a; color: #9ca3af; }
    .in-range { background: #166534; color: white; padding: 2px 4px; font-size: 0.7em; text-align: center; }
    .out-range { background: #1f1f1f; color: #444; padding: 2px 4px; font-size: 0.7em; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    st.title("♠ Poker GTO Coach")
    st.caption("Equity reală • Range-uri GTO • Profil adversar")

    # ── Init session state ──
    if "drill_correct" not in st.session_state: st.session_state.drill_correct = 0
    if "drill_total" not in st.session_state: st.session_state.drill_total = 0
    if "drill_combo" not in st.session_state: st.session_state.drill_combo = None

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Analiză Mână", "📊 Range Viewer", "🏋️ Drill", "📖 Referință"])

    # ════════════════════════════════════════════
    # TAB 1: ANALIZĂ
    # ════════════════════════════════════════════
    with tab1:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Input")
            st.caption("Notație: A K Q J 10 9...2 + i(♥) r(♦) t(♣) f(♠)")

            c1 = st.text_input("Cartea 1", "Ai", key="c1")
            c2 = st.text_input("Cartea 2", "Kr", key="c2")

            pozitie = st.selectbox("Poziția ta", POSITIONS, index=3)

            situatie = st.radio("Situație", ["RFI (primul care acționează)", "Facing open raise", "Postflop"])

            villain_pos = None
            board_cards = None
            pot_size = 0
            bet_size = 0

            if situatie == "Facing open raise":
                villain_pos = st.selectbox("Villain position", ["UTG","HJ","CO","BTN","SB"])

            if situatie == "Postflop":
                board_input = st.text_input("Board (ex: 10iJf2t)", "")
                pot_size = st.number_input("Pot", min_value=0, value=100)
                bet_size = st.number_input("Bet de plătit", min_value=0, value=0)

            profil = st.selectbox("Profil adversar", list(PROFILES.keys()))
            st.caption(PROFILES[profil]["desc"])

            analizeaza = st.button("🔍 Analizează", type="primary", use_container_width=True)

        with col2:
            if analizeaza:
                try:
                    hero_cards = [c1.strip(), c2.strip()]
                    combo = hand_to_combo(hero_cards)

                    st.subheader(f"Mâna: {card_display(c1)} {card_display(c2)} ({combo})")

                    with st.spinner("Calculez equity..."):
                        eq_rand = calc_equity_vs_random(hero_cards)

                    eq_range = None
                    action = ""
                    info = ""

                    if situatie == "RFI (primul care acționează)":
                        action, info = preflop_decision(combo, pozitie, "RFI")
                        v_range = GTO_RANGES["RFI"].get(pozitie, set())
                        st.metric("Equity vs random", f"{eq_rand}%")

                    elif situatie == "Facing open raise" and villain_pos:
                        action, info = preflop_decision(combo, pozitie, "VS_RFI", villain_pos)
                        v_range = GTO_RANGES["RFI"].get(villain_pos, set())
                        if v_range:
                            with st.spinner(f"Equity vs range {villain_pos}..."):
                                eq_range = calc_equity_vs_range(hero_cards, v_range)
                        c_eq, c_rng = st.columns(2)
                        c_eq.metric("Equity vs random", f"{eq_rand}%")
                        if eq_range: c_rng.metric(f"Equity vs range {villain_pos}", f"{eq_range}%")

                    elif situatie == "Postflop" and board_input:
                        board_cards = parse_board(board_input.strip())
                        board_display = " ".join(card_display(c) for c in board_cards)
                        st.write(f"**Board:** {board_display}")
                        with st.spinner("Equity pe board..."):
                            eq_rand = calc_equity_vs_random(hero_cards, board_cards)
                        action, info = postflop_decision(eq_rand, pot_size, bet_size)
                        st.metric("Equity vs random", f"{eq_rand}%")

                    # Ajustare profil
                    eq_adjusted = get_adjusted_equity(eq_range, eq_rand, profil)
                    if profil != "Standard":
                        st.metric("Equity ajustată (profil)", f"{eq_adjusted:.1f}%",
                                  delta=f"{eq_adjusted - eq_rand:+.1f}% vs raw")

                    # Afișare acțiune
                    action_class = "fold" if "FOLD" in action else "raise" if "RAISE" in action or "3-BET" in action else "call" if "CALL" in action else "bet" if "BET" in action else "check"
                    st.markdown(f\'<div class="big-action {action_class}-box">{action}</div>\', unsafe_allow_html=True)
                    st.info(f"💡 {info}")

                    # Progress bar equity
                    st.progress(min(eq_rand/100, 1.0))

                except Exception as e:
                    st.error(f"Eroare: {e}")
                    st.caption("Verifică notația: Ai=A♥, Kr=K♦, 10t=10♣, Jf=J♠")

    # ════════════════════════════════════════════
    # TAB 2: RANGE VIEWER
    # ════════════════════════════════════════════
    with tab2:
        st.subheader("Range-uri GTO Preflop")
        range_pos = st.selectbox("Poziție", ["UTG","HJ","CO","BTN","SB"], key="range_pos")
        rng = GTO_RANGES["RFI"].get(range_pos, set())
        st.write(f"**{len(rng)} combouri** în range-ul de open raise din {range_pos}")

        grid = render_range_grid(rng)
        header = "| |" + "|".join(f"**{r}**" for r in RANKS) + "|"
        sep = "|---|" + "|".join("---" for _ in RANKS) + "|"
        rows = [header, sep]
        for i, r1 in enumerate(RANKS):
            row_cells = [f"**{r1}**"]
            for j, (combo, in_range) in enumerate(grid[i]):
                if in_range:
                    row_cells.append(f"🟩")
                else:
                    row_cells.append(f"⬛")
            rows.append("|" + "|".join(row_cells) + "|")
        st.markdown("\n".join(rows))
        st.caption("🟩 = în range | ⬛ = fold")

    # ════════════════════════════════════════════
    # TAB 3: DRILL
    # ════════════════════════════════════════════
    with tab3:
        st.subheader("🏋️ Drill — Antrenament Preflop")

        if st.session_state.drill_total > 0:
            pct = st.session_state.drill_correct / st.session_state.drill_total * 100
            st.metric("Scor", f"{st.session_state.drill_correct}/{st.session_state.drill_total} ({pct:.0f}%)")

        if st.button("🎲 Situație nouă", use_container_width=True):
            r1 = random.choice(list(RANKS)); r2 = random.choice(list(RANKS))
            if r1==r2: combo=r1+r2
            elif random.random()>.5:
                if RANKS.index(r1)>RANKS.index(r2): r1,r2=r2,r1
                combo=r1+r2+"s"
            else:
                if RANKS.index(r1)>RANKS.index(r2): r1,r2=r2,r1
                combo=r1+r2+"o"
            hp = random.choice(["UTG","HJ","CO","BTN","SB"])

            if random.random() > 0.4:
                rr = GTO_RANGES["RFI"].get(hp, set())
                correct = "RAISE" if combo in rr else "FOLD"
                st.session_state.drill_combo = {"combo":combo,"pos":hp,"sit":"RFI","correct":correct,"desc":"Foldează până la tine"}
            else:
                vp = random.choice(["UTG","HJ","CO","BTN"])
                vi = POSITIONS.index(vp)
                vh = [p for p in POSITIONS[vi+1:] if p!="BB"]
                hp = random.choice(vh) if vh else "BB"
                k = f"vs_{vp}"
                b3 = GTO_RANGES["VS_RFI"]["3bet"].get(k,set())
                ca = GTO_RANGES["VS_RFI"]["call"].get(k,set())
                if combo in b3: correct="3-BET"
                elif combo in ca: correct="CALL"
                else: correct="FOLD"
                st.session_state.drill_combo = {"combo":combo,"pos":hp,"sit":"VS_RFI","correct":correct,"desc":f"{vp} deschide 3x"}

        d = st.session_state.drill_combo
        if d:
            st.markdown(f"### {d[\'combo\']} din {d[\'pos\']}")
            st.write(f"Situație: {d[\'desc\']}")

            if d["sit"] == "RFI":
                options = ["RAISE","FOLD"]
            else:
                options = ["3-BET","CALL","FOLD"]

            cols = st.columns(len(options))
            for i, opt in enumerate(options):
                if cols[i].button(opt, key=f"drill_{opt}", use_container_width=True):
                    st.session_state.drill_total += 1
                    if opt == d["correct"]:
                        st.session_state.drill_correct += 1
                        st.success(f"✅ CORECT! {d[\'combo\']} → {d[\'correct\']}")
                    else:
                        st.error(f"❌ GREȘIT. Corect: {d[\'correct\']}")
                    st.session_state.drill_combo = None
                    st.rerun()

        if st.button("🔄 Resetează scor"):
            st.session_state.drill_correct = 0
            st.session_state.drill_total = 0
            st.rerun()

    # ════════════════════════════════════════════
    # TAB 4: REFERINȚĂ
    # ════════════════════════════════════════════
    with tab4:
        st.subheader("📖 Referință Rapidă")

        st.markdown("""
        **Notație cărți:**
        - Ranks: A K Q J 10 9 8 7 6 5 4 3 2
        - Culori: **i**=♥ inimă, **r**=♦ romb, **t**=♣ treflă, **f**=♠ frunză
        - Exemple: `Ai`=A♥, `Kr`=K♦, `10t`=10♣, `Jf`=J♠

        **Poziții (6-max):**
        - UTG → HJ → CO → BTN → SB → BB
        - Cu cât mai târziu, cu atât range-ul e mai larg

        **Acțiuni GTO:**
        - **RFI** = First in (deschizi tu)
        - **3-BET** = Re-raise vs open
        - **Call** = Echitezi
        - **Fold** = Nu joci mâna

        **Profiluri adversar:**
        - **Standard** — Range normal, fără ajustare
        - **Tight-Rock** — Joacă doar premium, respectă raise-ul lui
        - **LAG** — Range larg + agresiv, equity ta e mai bună decât pare
        - **Maniac** — Raise orice, equity ta crește semnificativ
        - **Fish** — Call la tot, value bet mare, nu blufa
        - **Nit** — Ultra-tight, fold la orice presiune

        **Equity:**
        - vs random = contra orice 2 cărți
        - vs range = contra range-ul GTO al poziției villain
        - ajustată = modificată pe baza profilului adversar
        """)

if __name__ == "__main__":
    main()
