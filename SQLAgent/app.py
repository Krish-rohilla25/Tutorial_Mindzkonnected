import os
from dotenv import load_dotenv
load_dotenv() 

os.environ["GOOGLE_API_KEY"]=os.getenv("GOOGLE_API_KEY")

import streamlit as st
import os
import sqlite3

from langchain.chat_models import init_chat_model






prompt=[
    """
    You are an expert in converting English questions to SQL query!
    The SQL database has the name STUDENT and has the following columns - NAME, CLASS, 
    SECTION, MARKS \n\nFor example,\nExample 1 - How many entries of records are present?, 
    the SQL command will be something like this SELECT COUNT(*) FROM STUDENT ;
    \nExample 2 - Tell me all the students studying in Data Science class?, 
    the SQL command will be something like this SELECT * FROM STUDENT 
    where CLASS="Data Science"; 
    also the sql code should not have ``` in beginning or end and sql word in output

    """
]
def get_gemini_response(question,prompt):
    llm=init_chat_model(model="google_genai:gemini-2.5-flash")
    response=llm.invoke([prompt[0],question])
    return response.content


def read_sql_query(sql,db):
    conn=sqlite3.connect(db)
    cur=conn.cursor()
    cur.execute(sql)
    rows=cur.fetchall()
    conn.commit()
    conn.close()
    return rows


# streamlit app
st.set_page_config(page_title="I can Retrieve Any SQL query")
st.header("Gemini App To Retrieve SQL Data")

question=st.text_input("Input: ",key="input")

submit=st.button("Ask the question")


if submit:
    response=get_gemini_response(question,prompt)
    print(response)
    response=read_sql_query(response,"SQLAgent/student.db")
    st.subheader("The Response is")
    for row in response:
        print(row)
        st.header(row)