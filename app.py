
import streamlit as st
from treys import Card, Evaluator

st.title("Poker Assistant Pro")
st.write("Introdu cărțile (ex: Ah, Ks)")

c1 = st.text_input("Cartea 1", "Ah")
c2 = st.text_input("Cartea 2", "Ks")

if st.button("Analizează"):
    st.write(f"Ai selectat: {c1} și {c2}")
    st.success("Logica Treys este pregătită pentru integrare!")
