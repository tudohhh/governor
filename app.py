
import streamlit as st
from treys import Card, Evaluator

def parse_cards(card_str):
    return [Card.new(c.strip()) for c in card_str.split() if c.strip()]

def main():
    st.set_page_config(page_title="Poker Assistant Pro", page_icon="♠️")
    st.title("♠️ Poker Assistant Pro")
    
    col1, col2 = st.columns(2)
    p_card1 = col1.text_input("Jucător C1", "Ah").strip()
    p_card2 = col2.text_input("Jucător C2", "Ks").strip()
    
    board_input = st.text_input("Board (ex: Qh Jd 2c)", "Qh Jd 2c").strip()
    
    if st.button("Analizează Mâna"):
        try:
            evaluator = Evaluator()
            hand = [Card.new(p_card1), Card.new(p_card2)]
            board = parse_cards(board_input)
            
            # Calculăm rangul (scorul)
            rank = evaluator.evaluate(board, hand)
            class_name = evaluator.get_rank_string(rank)
            
            st.success(f"Rezultat: {class_name}")
            st.write(f"Scor numeric: {rank} (mai mic e mai bine!)")
        except Exception as e:
            st.error(f"Eroare: Verifică formatul cărților (ex: Ah, Ks, Qc). Eroare: {e}")

if __name__ == "__main__":
    main()
