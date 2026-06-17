
import streamlit as st
from treys import Card, Evaluator, Deck
import random

def translate_card(user_card):
    c = user_card.replace(" ", "").lower()
    val = c[:-1]
    suit = c[-1]
    color_map = {'i': 'h', 'r': 'd', 'f': 's', 't': 'c'}
    if val == '10': val = 't'
    if val == 'as': val = 'a'
    return f"{val.upper()}{color_map.get(suit, 's')}"

def calculate_equity(hand, board, iterations=500):
    evaluator = Evaluator()
    wins = 0
    for _ in range(iterations):
        deck = Deck()
        # Scoatem cărțile deja folosite
        deck.cards = [c for c in deck.cards if c not in hand and c not in board]
        
        # Completăm board-ul până la 5 cărți
        needed = 5 - len(board)
        draw = deck.draw(needed)
        full_board = board + (draw if needed > 1 else [draw])
        
        # Mână adversar
        opp_hand = deck.draw(2)
        
        if evaluator.evaluate(full_board, hand) < evaluator.evaluate(full_board, opp_hand):
            wins += 1
    return (wins / iterations) * 100

def main():
    st.title("♠️ Poker Assistant Pro")
    p1 = st.text_input("Cartea 1", "Ai")
    p2 = st.text_input("Cartea 2", "Kr")
    board_input = st.text_input("Board", "10i Jf 2t")
    
    if st.button("Calcul Equity"):
        try:
            evaluator = Evaluator()
            hand = [Card.new(translate_card(p1)), Card.new(translate_card(p2))]
            board = [Card.new(translate_card(c)) for c in board_input.replace(',', ' ').split()]
            
            equity = calculate_equity(hand, board)
            st.success(f"Șanse de câștig (Equity): {equity:.1f}%")
        except Exception as e:
            st.error("Eroare la calcul. Verifică cărțile.")

if __name__ == "__main__":
    main()
