
import streamlit as st
from treys import Card, Evaluator
from treys import Deck

def translate_card(user_card):
    c = user_card.replace(" ", "").lower()
    val = c[:-1]
    suit = c[-1]
    color_map = {'i': 'h', 'r': 'd', 'f': 's', 't': 'c'}
    if val == '10': val = 't'
    if val == 'as': val = 'a'
    return f"{val.upper()}{color_map.get(suit, 's')}"

def main():
    st.title("♠️ Poker Assistant Pro")
    p1 = st.text_input("Carte 1", "Ai")
    p2 = st.text_input("Carte 2", "Kr")
    board_input = st.text_input("Board", "10i Jf 2t")
    
    if st.button("Calculează Șanse"):
        try:
            evaluator = Evaluator()
            hand = [Card.new(translate_card(p1)), Card.new(translate_card(p2))]
            board = [Card.new(translate_card(c)) for c in board_input.replace(',', ' ').split()]
            
            # Placeholder pentru simulare simplificată (vom dezvolta motorul de Monte Carlo)
            st.info("Analiză în curs: Comparăm mâna ta cu spectrul adversarului...")
            
            rank = evaluator.evaluate(board, hand)
            st.success(f"Puterea mâinii: {evaluator.class_to_string(evaluator.get_rank_class(rank))}")
            st.warning("Urmează implementarea algoritmului de Equity pentru decizii bazate pe procente.")
        except Exception:
            st.error("Format invalid. Folosește: 10i, Ar, Jf")

if __name__ == "__main__":
    main()
