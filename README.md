AI-Powered Expense Tracker

One-line: A small Streamlit app that converts plain-English expense sentences into SQL (INSERT/SELECT) using Google Gemini and stores/results in a local SQLite database.

Project overview:-
This project is a prototype that demonstrates how an LLM can be used as an *interface* between natural language and a relational database. The app accepts a single-line user query such as ---> `I spent 250 on groceries yesterday using UPI` and uses Google Gemini to generate a single SQL statement which is executed against a local SQLite database and displayed back to the user.
This is a prototype intended to show the UX and prompt-engineering ideas — not a production-ready system.

Motivation:-
Logging expenses is tedious. The goal was to let users speak or type like a human, and let an LLM translate that into DB operations. This taught practical tradeoffs of convenience vs safety when an LLM is allowed to generate code that gets executed.

Features:-
1. Conversational input for logging or querying expenses
2. Google Gemini integration to convert English → SQL
3. Local SQLite (`student.db`) to persist data
4. Streamlit-based UI with custom CSS for a polished look
5. Basic safety: restricted prompt, blocked-word filter, rate limiting

Architecture & flow
1. User types a natural-language expense or query in the Streamlit UI.
2. The app sends a strongly-constrained prompt + user message to Google Gemini.
3. Gemini returns a single SQL statement (INSERT or SELECT) following the enforced schema.
4. The app executes that SQL against `student.db` and returns results to the UI.

Tech stack
1. Python 3.11+ (recommended)
2. Streamlit
3. sqlite3 (standard library)
4. `google.generativeai` (Gemini client)
5. `rateguard` (rate limiting)

Quick start (run locally)
1. Clone your repo and ensure `app.py` contains the project code.
2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install streamlit google-generativeai rateguard
```

3. Create the SQLite database with the required table (one-time):

```bash
python - <<PY
import sqlite3
conn = sqlite3.connect('student.db')
cur = conn.cursor()
cur.execute('''
CREATE TABLE IF NOT EXISTS Finance(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  purchased VARCHAR NOT NULL,
  categorization TEXT NOT NULL,
  amount REAL NOT NULL,
  date TEXT NOT NULL,
  payment_type TEXT
);
'''
conn.commit()
conn.close()
print('student.db created with table Finance')
```

4. Add your Gemini API key to Streamlit secrets. Create `~/.streamlit/secrets.toml` or use `streamlit` CLI. Example `secrets.toml`:
```toml
GEMINI_API_KEY = "your_api_key_here"
```

5. Run the app:
```bash
streamlit run app.py
```
Open `http://localhost:8501`

Database schema
Use this exact schema (the app and prompt rely on it):

```sql
CREATE TABLE Finance(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  purchased VARCHAR NOT NULL,
  categorization TEXT NOT NULL,
  amount REAL NOT NULL,
  date TEXT NOT NULL,
  payment_type TEXT
);
```
Allowed categories (normalization): `['Food', 'Transport', 'Utilities', 'Shopping', 'Entertainment', 'Healthcare', 'Other']`

Examples
Input: `I spent 250 on groceries yesterday using UPI`

Expected Gemini output (SQL):
```sql
INSERT INTO Finance (purchased, categorization, amount, date, payment_type) VALUES ('groceries', 'Food', 250.0, '2025-10-21', 'UPI');
```

Input: `Show me all entertainment expenses this month`
Expected SQL:

```sql
SELECT * FROM Finance WHERE categorization = 'Entertainment' AND date BETWEEN '2025-10-01' AND '2025-10-31';
```  

> Note: These are examples — the Gemini model may vary. The app relies on a strict prompt to keep outputs consistent.
---

License
MIT — feel free to reuse the code. Add an appropriate `LICENSE` file if you publish this publicly.

Contact
If you share this on GitHub and want help hardening the code for production (parameterized queries, JSON output, auth), open an issue or DM me — I can provide the exact code changes and tests.