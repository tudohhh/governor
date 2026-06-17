
import streamlit as st
from treys import Card, Evaluator, Deck

def translate_card(c_str):
    if c_str.startswith('10'): val, suit = '10', c_str[2]
    else: val, suit = c_str[0], c_str[1]
    color_map = {'i': 'h', 'r': 'd', 'f': 's', 't': 'c'}
    val = 't' if val == '10' else val.lower()
    return f"{val.upper()}{color_map.get(suit, 's')}"

def get_decision(equity):
    if equity >= 70: return "VERDE: Agresiv (Valoare Maximă)", "green"
    elif equity >= 50: return "GALBEN: Calculează (Pot Odds favorabile)", "orange"
    elif equity >= 30: return "PORTOCALIU: Prudent (Așteaptă un preț bun)", "orange"
    else: return "ROȘU: FOLD (Nu merită riscul)", "red"

def calculate_equity(hand, board, iterations=500):
    evaluator = Evaluator()
    wins = 0
    for _ in range(iterations):
        deck = Deck()
        deck.cards = [c for c in deck.cards if c not in hand and c not in board]
        needed = 5 - len(board)
        draw = deck.draw(needed)
        full_board = board + (draw if needed > 1 else [draw])
        if evaluator.evaluate(full_board, hand) < evaluator.evaluate(full_board, deck.draw(2)):
            wins += 1
    return (wins / iterations) * 100

def main():
    st.title("♠️ Poker Assistant Pro")
    p1 = st.text_input("Cartea 1", "Ai")
    p2 = st.text_input("Cartea 2", "Kr")
    board_input = st.text_input("Board (ex: 10iJf2t)", "10iJf2t")
    
    if st.button("Analizează"):
        try:
            # Parsare compactă
            raw_hand = [p1, p2]
            hand = [Card.new(translate_card(c)) for c in raw_hand]
            
            # Parsare board compact
            b_str = board_input
            b_cards = []
            while len(b_str) > 0:
                if b_str.startswith('10'): b_cards.append(b_str[:3]); b_str = b_str[3:]
                else: b_cards.append(b_str[:2]); b_str = b_str[2:]
            board = [Card.new(translate_card(c)) for c in b_cards]
            
            equity = calculate_equity(hand, board)
            msg, color = get_decision(equity)
            
            st.markdown(f"### Șanse: {equity:.1f}%")
            st.markdown(f"### <span style='color:{color}'>{msg}</span>", unsafe_allow_html=True)
            
        except Exception:
            st.error("Format invalid. Folosește: 10i, Ai, Jf (fără spații)")

if __name__ == "__main__":
    main()
