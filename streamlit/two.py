import streamlit as st
from datetime import date

st.title("Age Calculator")

name = st.text_input("Enter your name")
if name:
    st.write(f"Welcome, {name} ! Let's get your details")
today = date.today()
dob = st.date_input(
    "Select your date of birth",
    value=date(2000, 1, 1),
    min_value=date(1900, 1, 1),
    max_value=today
)
st.write(f"Your date of birth {dob}")

age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
if st.button("Calculate Age"):
    st.success("Calculated!,You are {age} years old!")

party_type = st.radio("Pick your party base: ", ["Party", "Dinner", "Movie"])
st.write(f"Selected base {party_type}")

flavour = st.selectbox("Choose cake flavour: ", ["Chocolate", "Vanilla", "Strawberry"])
st.write(f"Selected Flavour {flavour}")

excitement = st.slider("Excitement level", 0, 10, 8)
st.write(f"Selected excitement level {excitement}")

slices = st.number_input("How many slices", min_value=1, max_value=10, step=1)
st.write(f"Selected slices {slices}")


