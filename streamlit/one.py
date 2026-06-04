import streamlit as st

st.title("Hello")
st.subheader("Brewed with streamlit")
st.text("Welcome")
st.write("Chooose your fav. programmming language")

box  =st.selectbox("Choose", ["Python", "Java", "C++", "JavaScript", "Rust"])

st.write(f"You chose {box}")

st.success("Thank you for your feedback")

