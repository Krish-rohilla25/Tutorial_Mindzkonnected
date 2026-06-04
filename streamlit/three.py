import streamlit as st

st.title("Chai Taste Poll")

col1, col2 = st.columns(2)

with col1:
    st.header("Masala Chai")

    vote1 = st.button("Vote Masala Chai")

with col2:
    st.header("Adrak Chai")
    vote2 = st.button("Vote Adrak Chai")

if vote1:
    st.success("Thanks for voting masala Chai")
elif vote2:
    st.success("Thanks for voting Adrak Chai")

name = st.sidebar.text_input("Enter your name")
tea = st.sidebar.selectbox("Choose your chai", ["Masala", "kesar", "Adrak"])

st.write(f"Welcome {name} and your {tea} chai is getting ready")


with st.expander("Show Chai Making INstructions"):
    st.write("""
    1. Boil water with tea leaves
    2. Add milk and spices
    3. Serve hot
 """)
    
st.markdown('# Welcome to Chai App')
st.markdown('> Blockquote ')