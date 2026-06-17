
import streamlit as st
from treys import Card, Evaluator, Deck

# Inițializare memorie adversari
if 'adversari' not in st.session_state:
    st.session_state.adversari = {}
if 'tilt_counter' not in st.session_state:
    st.session_state.tilt_counter = 0

def main():
    st.title("♠️ Poker Command Center")
    
    # 1. Modul Notițe Adversari
    with st.expander("📝 Notițe Adversari"):
        nick = st.text_input("Nickname adversar")
        nota = st.text_area("Stil/Observații")
        if st.button("Salvează Notă"):
            st.session_state.adversari[nick] = nota
        st.write("Notițe salvate:", st.session_state.adversari)

    # 2. Pot Odds Calculator (Rapid)
    st.subheader("🧮 Pot Odds Calculator")
    col1, col2 = st.columns(2)
    pot = col1.number_input("Potul Total ($)", value=100.0)
    bet = col2.number_input("Bet Adversar ($)", value=25.0)
    if pot > 0:
        odds = bet / (pot + bet)
        st.info(f"Ai nevoie de {odds*100:.1f}% equity pentru a face un Call profitabil.")

    # 3. Tilt Guard
    st.subheader("🛡️ Tilt Guard")
    ev_status = st.radio("Cum a fost ultima mână?", ("EV Pozitiv", "EV Negativ"))
    if ev_status == "EV Negativ":
        st.session_state.tilt_counter += 1
    else:
        st.session_state.tilt_counter = max(0, st.session_state.tilt_counter - 1)
    
    if st.session_state.tilt_counter >= 3:
        st.warning("⚠️ ALERTĂ TILT: Ai pierdut 3 mâini la rând. Ia o pauză de 5 minute!")
    st.write(f"Nivel stres: {st.session_state.tilt_counter}/3")

    st.markdown("---")
    # ... (Aici ar veni restul logicii de calcul Equity de mai devreme)
    st.success("Sistem gata de luptă!")

if __name__ == "__main__":
    main()
