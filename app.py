
import streamlit as st
from treys import Card, Evaluator

def translate_card(user_card):
    # Eliminăm orice spațiu introdus din greșeală și transformăm în litere mici
    c = user_card.replace(" ", "").lower()
    
    # Valoarea este tot ce e înainte de ultimul caracter (semnul)
    val = c[:-1]
    suit = c[-1]
    
    # Mapare culori
    color_map = {'i': 'h', 'r': 'd', 'f': 's', 't': 'c'}
    
    # Corecții pentru formatul treys
    if val == '10': val = 't'
    if val == 'as': val = 'a'
    
    # Rezultat: ex. 'Th', 'Ad', 'Js', '7c'
    return f"{val.upper()}{color_map.get(suit, 's')}"

def main():
    st.set_page_config(page_title="Poker Assistant", page_icon="♠️")
    st.title("♠️ Poker Assistant Pro")
    
    c1, c2 = st.columns(2)
    p1 = c1.text_input("Cartea 1 (ex: Ai)", "Ai")
    p2 = c2.text_input("Cartea 2 (ex: Kr)", "Kr")
    board_input = st.text_input("Board (ex: 10i,Jf,2t)", "10i,Jf,2t")
    
    if st.button("Analizează"):
        try:
            evaluator = Evaluator()
            hand = [Card.new(translate_card(p1)), Card.new(translate_card(p2))]
            # Separăm prin virgulă sau spațiu
            cards_raw = board_input.replace(',', ' ').split()
            board_cards = [Card.new(translate_card(c)) for c in cards_raw]
            
            rank = evaluator.evaluate(board_cards, hand)
            st.success(f"Rezultat: {evaluator.get_rank_string(rank)}")
        except Exception:
            st.error("Format invalid! Folosește: 10i, Ar, Jf, 7t (fără spațiu între cifră și semn)")

if __name__ == "__main__":
    main()
