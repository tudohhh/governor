
import streamlit as st
from treys import Card, Evaluator

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
    p1 = st.text_input("Cartea 1 (ex: Ai)", "Ai")
    p2 = st.text_input("Cartea 2 (ex: Kr)", "Kr")
    board_input = st.text_input("Board (ex: 4i 5i 9r 10i Jf)", "4i 5i 9r 10i Jf")
    
    if st.button("Analizează"):
        try:
            evaluator = Evaluator()
            hand = [Card.new(translate_card(p1)), Card.new(translate_card(p2))]
            cards_raw = board_input.replace(',', ' ').split()
            board_cards = [Card.new(translate_card(c)) for c in cards_raw]
            
            rank = evaluator.evaluate(board_cards, hand)
            rank_class = evaluator.get_rank_class(rank)
            st.success(f"Rezultat: {evaluator.class_to_string(rank_class)}")
        except Exception as e:
            st.error("Format invalid. Folosește: 10i, Ar, Jf, 7t")

if __name__ == "__main__":
    main()
