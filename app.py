from dotenv import load_dotenv
load_dotenv() # Loading All Environment variables!

import streamlit as st
import os
import sqlite3

import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Function to load google gemin Model and Provide sql query as response
def get_gemini_response(question,prompt):
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content([prompt[0],question])
    return response.text

## Function to retrieve query from sql database
def read_sql_query(sql,db):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    print("DEBUG QUERY:", sql)
    cur.execute(sql)
    rows = cur.fetchall()
    conn.commit()
    conn.close()
    for row in rows:
        print(row)
    return rows 

prompt = [
    """
    You are an expenses-to-SQL assistant for a simple personal financial tracker.
    Your only job is to convert a single natural-language user input into one safe,
    parameterized SQL statement (or to ask for clarification).

    VERY IMPORTANT RULES:
    - Use this schema exactly:
      CREATE TABLE Finance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchased VARCHAR NOT NULL,
        categorization TEXT NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        payment_type TEXT
      );
    - The table name is Finance (NOT transactions, NOT Parameters).
    - The only valid columns are: purchased, categorization, amount, date, payment_type.
    - Do not invent new tables or columns.
    - Do not output ```sql or ``` fences.
    - Output ONLY the SQL statement.

    If the user describes an expense, generate an INSERT into Finance with:
    - categorization -> Always normalize categorization to one of these categories--->['Food', 'Transport', 'Utilities', 'Shopping', 'Entertainment', 'Healthcare', 'Other']. 
    - purchased -> Name of the item purchased
    - amount → numeric value
    - date → YYYY-MM-DD (default year 2025 if omitted)
    - payment_type → given or NULL 

    If the user asks for data retrieval, generate a SELECT statement on Finance.
    """
]

import streamlit as st

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="💰 AI-Powered Expense Tracker",
    page_icon="💸",
    layout="wide"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    /* Background Gradient */
    .stApp {
        background: linear-gradient(135deg, #1f1c2c, #928dab);
        color: white;
        font-family: 'Trebuchet MS', sans-serif;
    }

    /* Title Glow Effect */
    .title {
        font-size: 3rem;
        font-weight: bold;
        color: #fff;
        text-align: center;
        text-shadow: 0 0 10px #00ffe7, 0 0 20px #00ffe7, 0 0 30px #00ffe7;
        animation: glow 2s infinite alternate;
    }
    @keyframes glow {
        from { text-shadow: 0 0 5px #00ffe7; }
        to { text-shadow: 0 0 20px #00ffe7, 0 0 40px #00ffe7; }
    }

    /* Subheader Typewriter Animation */
    .typewriter {
        overflow: hidden;
        border-right: .15em solid orange;
        white-space: nowrap;
        margin: 0 auto;
        letter-spacing: .10em;
        animation:
          typing 3.5s steps(40, end),
          blink-caret .75s step-end infinite;
        font-size: 1.3rem;
        color: #FFD700;
        text-align: center;
    }
    @keyframes typing {
      from { width: 0 }
      to { width: 100% }
    }
    @keyframes blink-caret {
      from, to { border-color: transparent }
      50% { border-color: orange }
    }

    /* Fancy Cards */
    .result-card {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<div class='title'>💰 AI-Powered Expense Tracker</div>", unsafe_allow_html=True)
st.markdown("<div class='typewriter'>Talk to your expenses in plain English → Get instant SQL-powered insights</div>", unsafe_allow_html=True)

st.write("")

# --- INPUT ---
question = st.text_input("💬 Enter your query or expense:", placeholder="e.g. I spent 250 on groceries yesterday using UPI")
submit = st.button("🚀 Run")

# If Submit is clicked!
if submit:
    with st.container():
        st.markdown("<div class='result-card'>✅ Expense successfully added to database!</div>", unsafe_allow_html=True)
    response = get_gemini_response(question,prompt)
    print(response)
    data = read_sql_query(response, "student.db")
    for row in data:
        print(row)
        st.header(row)