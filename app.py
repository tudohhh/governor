
import streamlit as st
from treys import Card, Evaluator, Deck

def translate_card(c_str):
    if c_str.startswith('10'): val, suit = '10', c_str[2]
    else: val, suit = c_str[0], c_str[1]
    color_map = {'i': 'h', 'r': 'd', 'f': 's', 't': 'c'}
    val = 't' if val == '10' else val.lower()
    return f"{val.upper()}{color_map.get(suit, 's')}"

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
    st.title("♠️ Poker Assistant Pro - EV Mode")
    
    p1 = st.text_input("Cartea 1", "Ai")
    p2 = st.text_input("Cartea 2", "Kr")
    board_input = st.text_input("Board", "10iJf2t")
    pot_size = st.number_input("Potul actual ($)", min_value=0.0, value=100.0)
    call_amount = st.number_input("Cât trebuie să plătești ($)", min_value=0.0, value=20.0)
    
    if st.button("Calculează EV"):
        try:
            hand = [Card.new(translate_card(p1)), Card.new(translate_card(p2))]
            b_cards = []
            temp = board_input
            while len(temp) > 0:
                if temp.startswith('10'): b_cards.append(temp[:3]); temp = temp[3:]
                else: b_cards.append(temp[:2]); temp = temp[2:]
            board = [Card.new(translate_card(c)) for c in b_cards]
            
            equity = calculate_equity(hand, board) / 100
            ev = (equity * (pot_size + call_amount)) - call_amount
            
            st.markdown(f"### Șanse: {equity*100:.1f}%")
            if ev > 0:
                st.success(f"EV Pozitiv: +${ev:.2f} (Profitabil pe termen lung)")
            else:
                st.error(f"EV Negativ: -${abs(ev):.2f} (Pierdere pe termen lung)")
        except Exception:
            st.error("Format eronat. Folosește: 10i, Ai, Jf (fără spații)")

if __name__ == "__main__":
    main()
