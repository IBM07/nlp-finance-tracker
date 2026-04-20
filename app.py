# ==========================================
# AI FINANCE TRACKER - UNIFIED STREAMLIT APP
# ==========================================
import streamlit as st
import sqlite3
import pandas as pd
import logging
from groq import Groq
from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional, Tuple

# --- CONFIG ---
DB_PATH = "student.db"
GROQ_MODEL = "llama-3.3-70b-versatile"
SAFE_SQL_STARTS = ("SELECT", "INSERT", "UPDATE", "DELETE")
BLOCKED_SQL_KEYWORDS = ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
CATEGORY_VALUES = ["Food", "Transport", "Utilities", "Shopping", "Entertainment", "Healthcare", "Other"]
SPAM_KEYWORDS = ["rob", "hack", "steal", "terrorist", "attack", "kill", "murder", "drugs", "bomb", "scam", "fraud"]
FINANCE_KEYWORDS = [
    "spent", "paid", "bought", "purchased", "cost", "expense", "bill", "salary", "income", "received",
    "transfer", "show", "list", "total", "how much", "delete", "remove", "update", "change", "edit",
    "modify", "all my", "transactions", "spending"
]
NON_FINANCE_MESSAGE = "Please enter a finance-related query (e.g. 'I spent 200 on groceries')."
INVALID_AI_SQL_MESSAGE = "AI returned an unexpected response. Please rephrase your query."
SPAM_MESSAGE = "Security Alert: Please don't spam or misuse the app."
AI_UNAVAILABLE_MESSAGE = "AI service unavailable. Please try again."
GENERIC_ERROR_MESSAGE = "An unexpected error occurred while processing your request."

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="💰 AI Finance Tracker",
    page_icon="💸",
    layout="wide"
)


def init_db() -> None:
    """Initialize the SQLite database and Finance table if absent.

    Parameters:
        None.
    Returns:
        None.
    Edge cases:
        Logs and safely exits on SQLite failures without crashing the app.
    """
    logger.info("Entering init_db")
    try:
        with sqlite3.connect(DB_PATH) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Finance(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchased VARCHAR NOT NULL,
                    categorization TEXT NOT NULL,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL,
                    payment_type TEXT
                );
                """
            )
            connection.commit()
        logger.info("init_db success: Finance table is ready")
    except sqlite3.Error as exc:
        logger.error("init_db failed: %s", exc)
        st.error("Database initialization failed. Please check logs.")


def build_system_prompt() -> str:
    """Build the system prompt with a dynamic default date for inserts.

    Parameters:
        None.
    Returns:
        str: Prompt content for the Groq model.
    Edge cases:
        Uses today's date to avoid stale hardcoded dates.
    """
    logger.info("Entering build_system_prompt")
    try:
        today_str = date.today().isoformat()
        prompt = f"""
    You are an expenses-to-SQL assistant for a simple personal financial tracker.
    Your job is to convert natural language into ONE safe, parameterized SQL statement.
    You can INSERT, SELECT, UPDATE, or DELETE data.

    Today's date is {today_str}. Use this as the default date for any INSERT when the user does not specify a date.

    SAFETY & SECURITY RULES (Industry Standard):
    1. **NO DESTRUCTIVE DDL**: Never generate DROP, TRUNCATE, ALTER, or GRANT.
    2. **SAFE UPDATES/DELETES**:
       - If the user asks to "update/delete the last purchase", you MUST use a subquery for the ID, because SQLite does not support ORDER BY in UPDATE/DELETE.
       - Pattern: `UPDATE Finance SET amount=300 WHERE id = (SELECT id FROM Finance ORDER BY id DESC LIMIT 1);`
       - Never update/delete without a WHERE clause unless explicitly asked to "delete all".

    STRICT SCHEMA:
    - Table: `Finance`
    - Columns: `id` (INT), `purchased` (STR), `categorization` (STR), `amount` (REAL), `date` (STR), `payment_type` (STR).
    - Categorization: Normalize to {CATEGORY_VALUES}.

    EXAMPLES:

    Input: "I spent 250 on pizza"
    Output: `INSERT INTO Finance (purchased, categorization, amount, date, payment_type) VALUES ('pizza', 'Food', 250, '{today_str}', NULL);`

    Input: "Show me all food from yesterday"
    Output: `SELECT * FROM Finance WHERE categorization='Food' AND date = date('now', '-1 day');`

    Input: "Change the last expense to 300 instead of 250"
    Output: `UPDATE Finance SET amount = 300 WHERE id = (SELECT id FROM Finance ORDER BY id DESC LIMIT 1);`

    Input: "Delete the last transaction"
    Output: `DELETE FROM Finance WHERE id = (SELECT id FROM Finance ORDER BY id DESC LIMIT 1);`

    Output ONLY text of the SQL. No markdown fences.
    """
        logger.info("build_system_prompt success")
        return prompt
    except Exception as exc:
        logger.error("build_system_prompt failed: %s", exc)
        return ""


def is_spam_input(user_input: str) -> bool:
    """Check whether user text appears malicious or abusive.

    Parameters:
        user_input (str): Raw user query text.
    Returns:
        bool: True when spam indicators are detected, else False.
    Edge cases:
        Returns True on internal errors to fail safely.
    """
    logger.info("Entering is_spam_input")
    try:
        user_input_lower = user_input.lower()
        is_spam = any(word in user_input_lower for word in SPAM_KEYWORDS)
        if is_spam:
            logger.warning("Spam detected in input: %s", user_input)
        logger.info("is_spam_input success")
        return is_spam
    except Exception as exc:
        logger.error("is_spam_input failed: %s", exc)
        return True


def is_finance_related(text: str) -> bool:
    """Decide whether input is finance-related using local heuristics only.

    Parameters:
        text (str): User query text.
    Returns:
        bool: True if query contains a number or known finance keyword.
    Edge cases:
        Empty or unrelated text returns False and is logged as warning.
    """
    logger.info("Entering is_finance_related")
    try:
        lowered = text.lower().strip()
        has_number = bool(re.search(r"\d+", lowered))
        has_keyword = any(keyword in lowered for keyword in FINANCE_KEYWORDS)
        result = has_number or has_keyword
        if not result:
            logger.warning("Non-finance input rejected: %s", text)
        logger.info("is_finance_related success")
        return result
    except Exception as exc:
        logger.error("is_finance_related failed: %s", exc)
        return False


def is_valid_sql(text: str) -> bool:
    """Validate model output before any SQL execution.

    Parameters:
        text (str): Candidate SQL output from AI.
    Returns:
        bool: True for allowed DML statements without blocked DDL keywords.
    Edge cases:
        Empty strings and malformed statements are rejected.
    """
    logger.info("Entering is_valid_sql")
    try:
        stripped = text.strip().upper()
        is_allowed_start = any(stripped.startswith(prefix) for prefix in SAFE_SQL_STARTS)
        has_blocked_keyword = any(keyword in stripped for keyword in BLOCKED_SQL_KEYWORDS)
        result = is_allowed_start and not has_blocked_keyword
        if not result:
            logger.warning("Invalid SQL blocked: %s", text)
        logger.info("is_valid_sql success")
        return result
    except Exception as exc:
        logger.error("is_valid_sql failed: %s", exc)
        return False


def get_ai_response(question: str) -> Optional[str]:
    """Send user query to Groq and return generated SQL text.

    Parameters:
        question (str): User query.
    Returns:
        Optional[str]: SQL text on success, else None.
    Edge cases:
        Returns None if client is unavailable or API call fails.
    """
    logger.info("Entering get_ai_response")
    if "groq_client" not in st.session_state:
        logger.error("get_ai_response failed: Groq client not initialized")
        return None

    try:
        prompt = build_system_prompt()
        completion = st.session_state.groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question}
            ],
            temperature=0,
            max_tokens=200,
            top_p=1,
            stop=None,
            stream=False
        )
        if not completion.choices or not completion.choices[0].message or not completion.choices[0].message.content:
            logger.warning("get_ai_response warning: Empty choices/content returned from Groq")
            return None
        response_text = completion.choices[0].message.content.strip()
        logger.info("get_ai_response success")
        return response_text
    except Exception as exc:
        logger.error("get_ai_response failed: %s", exc)
        return None


def read_sql_query(sql: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[int]]:
    """Execute SQL against SQLite and return rows or affected row count.

    Parameters:
        sql (str): SQL statement to run.
    Returns:
        Tuple[Optional[List[Dict[str, Any]]], Optional[int]]:
            SELECT => (list of row dicts, None), DML => (None, affected row count), failures => (None, None).
    Edge cases:
        Any SQLite error is logged and converted to a safe `(None, None)` response.
    """
    logger.info("Entering read_sql_query")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            logger.info("Executing SQL: %s", sql)
            cursor.execute(sql)

            if sql.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                data = [dict(zip(columns, row)) for row in rows]
                logger.info("read_sql_query success: SELECT returned %s rows", len(data))
                return data, None

            conn.commit()
            logger.info("read_sql_query success: DML affected %s rows", cursor.rowcount)
            return None, cursor.rowcount
    except sqlite3.Error as exc:
        logger.error("read_sql_query failed: %s", exc)
        return None, None


def process_user_query(query_text: str) -> Dict[str, Any]:
    """Run full guarded query pipeline from user text to optional DB execution.

    Parameters:
        query_text (str): Raw natural-language input.
    Returns:
        Dict[str, Any]: Standard response with `message`, `sql`, `data`, and `row_count` keys.
    Edge cases:
        Spam, non-finance, AI failures, invalid SQL, and DB failures all return safe messages.
    """
    logger.info("Entering process_user_query")
    try:
        if is_spam_input(query_text):
            logger.warning("process_user_query blocked by spam filter")
            return {"message": SPAM_MESSAGE, "sql": None, "data": None, "row_count": 0}

        if not is_finance_related(query_text):
            logger.warning("process_user_query blocked by finance intent filter")
            return {"message": NON_FINANCE_MESSAGE, "sql": None, "data": None, "row_count": 0}

        sql = get_ai_response(query_text)
        if not sql:
            logger.warning("process_user_query failed: AI returned no SQL")
            return {"message": AI_UNAVAILABLE_MESSAGE, "sql": None, "data": None, "row_count": 0}

        if not is_valid_sql(sql):
            logger.warning("AI returned unexpected non-executable SQL/text")
            return {"message": INVALID_AI_SQL_MESSAGE, "sql": None, "data": None, "row_count": 0}

        rows, row_count = read_sql_query(sql)
        sql_upper = sql.strip().upper()

        if sql_upper.startswith("INSERT"):
            message = "Expense successfully added!"
        elif sql_upper.startswith(("UPDATE", "DELETE")):
            message = f"Operation successful. Affected {row_count if row_count is not None else 0} records."
        elif rows is not None:
            message = f"Found {len(rows)} records."
        else:
            message = "Error executing query."

        logger.info("process_user_query success: %s", message)
        return {
            "message": message,
            "sql": sql,
            "data": rows,
            "row_count": row_count if row_count is not None else (len(rows) if rows is not None else 0)
        }
    except Exception as exc:
        logger.error("process_user_query failed: %s", exc)
        return {"message": GENERIC_ERROR_MESSAGE, "sql": None, "data": None, "row_count": 0}


def fetch_analytics() -> List[Dict[str, Any]]:
    """Fetch category-level spend totals for dashboard analytics.

    Parameters:
        None.
    Returns:
        List[Dict[str, Any]]: Records as `{category, total}`.
    Edge cases:
        Returns empty list on DB errors or no data.
    """
    logger.info("Entering fetch_analytics")
    query = "SELECT categorization, SUM(amount) as total FROM Finance GROUP BY categorization ORDER BY total DESC"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            data = [{"category": row[0], "total": row[1]} for row in rows]
            logger.info("fetch_analytics success: %s rows", len(data))
            return data
    except sqlite3.Error as exc:
        logger.error("fetch_analytics failed: %s", exc)
        return []


def fetch_recent() -> List[Dict[str, Any]]:
    """Fetch the latest five transactions for recent activity.

    Parameters:
        None.
    Returns:
        List[Dict[str, Any]]: Records as `{id, item, amount, category, date}`.
    Edge cases:
        Returns empty list on DB errors or no records.
    """
    logger.info("Entering fetch_recent")
    query = "SELECT id, purchased, amount, categorization, date FROM Finance ORDER BY id DESC LIMIT 5"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            data = [
                {"id": row[0], "item": row[1], "amount": row[2], "category": row[3], "date": row[4]}
                for row in rows
            ]
            logger.info("fetch_recent success: %s rows", len(data))
            return data
    except sqlite3.Error as exc:
        logger.error("fetch_recent failed: %s", exc)
        return []


def handle_query() -> None:
    """Handle action-center query submission and store the latest response.

    Parameters:
        None. Reads text from `st.session_state.user_query`.
    Returns:
        None.
    Edge cases:
        Empty queries are ignored; failures surface as safe user-facing errors.
    """
    logger.info("Entering handle_query")
    try:
        query_text = st.session_state.user_query
        if not query_text:
            logger.warning("handle_query called with empty input")
            return

        with st.spinner("Processing with Groq LPU™..."):
            response_data = process_user_query(query_text)
            st.session_state.last_response = response_data

        if response_data.get("sql"):
            st.success("Processed Successfully!")
        else:
            st.warning(response_data.get("message", "Request was not processed."))
        logger.info("handle_query success")
    except Exception as exc:
        logger.error("handle_query failed: %s", exc)
        st.error("Failed to process query. Please try again.")


# --- APP STARTUP ---
logger.info("App startup at %s", datetime.now().isoformat())
init_db()

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    if not isinstance(GROQ_API_KEY, str) or not GROQ_API_KEY.strip():
        logger.error("GROQ_API_KEY is present but empty")
        st.error("GROQ_API_KEY is empty. Provide a valid key in Streamlit secrets.")
        st.stop()
    st.session_state.groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq client initialized successfully")
except KeyError:
    logger.error("GROQ_API_KEY missing in Streamlit secrets")
    st.error("GROQ_API_KEY not found. Add it to Streamlit Cloud Secrets or a local .secrets.toml file.")
    st.stop()
except Exception as exc:
    logger.error("Failed to initialize Groq client: %s", exc)
    st.error("Failed to initialize Groq client. Check your key and retry.")
    st.stop()

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #1f1c2c, #928dab);
        color: white;
        font-family: 'Trebuchet MS', sans-serif;
    }

    /* Hero Header */
    .hero-title {
        font-size: 3.5rem;
        font-weight: bold;
        color: #fff;
        text-align: center;
        text-shadow: 0 0 10px #00ffe7, 0 0 20px #00ffe7;
        margin-bottom: 0px;
    }
    .hero-subtitle {
        font-size: 1.2rem;
        color: #FFD700;
        text-align: center;
        margin-top: -10px;
        margin-bottom: 30px;
        font-style: italic;
    }

    /* Cards & Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem;
        color: #00ffe7;
    }

    /* Input Field */
    .stTextInput > div > div > input {
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid #00ffe7;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
if "last_response" not in st.session_state:
    st.session_state.last_response = None

recent_data = fetch_recent()
analytics_data = fetch_analytics()

# --- SECTION A: HERO HEADER ---
st.markdown("<div class='hero-title'>💰 AI Finance Tracker</div>", unsafe_allow_html=True)
st.markdown("<div class='hero-subtitle'>Powered by Groq LPU™</div>", unsafe_allow_html=True)

# --- SECTION B: THE DASHBOARD (Top Row) ---
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 📊 Metrics")
    total_spend = 0.0
    if analytics_data:
        total_spend = sum(item["total"] for item in analytics_data)
    st.metric(label="Total Expenses (All Time)", value=f"${total_spend:,.2f}")

with col2:
    st.markdown("### 🍩 Spending Breakdown")
    if analytics_data:
        df_analytics = pd.DataFrame(analytics_data)
        st.bar_chart(df_analytics, x="category", y="total", color="#00ffe7")
    else:
        st.info("No analytics data available yet.")

st.markdown("---")

# --- SECTION C: RECENT ACTIVITY (Middle Row) ---
st.markdown("### 🕒 Recent Activity")
if recent_data:
    df_recent = pd.DataFrame(recent_data)
    st.dataframe(df_recent, use_container_width=True, hide_index=True)
else:
    st.info("No recent transactions found.")

if st.button("🔄 Refresh Dashboard"):
    logger.info("Manual dashboard refresh requested")
    st.rerun()

st.markdown("---")

# --- SECTION D: ACTION CENTER (Bottom Row) ---
st.markdown("### 💬 Action Center")

col_input, col_history = st.columns([2, 1])

with col_input:
    st.text_input(
        "Talk to your finance tracker...",
        placeholder="e.g. 'I spent $20 on Coffee' or 'Show all food expenses'",
        key="user_query",
        on_change=handle_query
    )
    st.caption("Press Enter to send.")

with col_history:
    st.markdown("**Last AI Response:**")
    if st.session_state.last_response:
        response = st.session_state.last_response
        msg = response.get("message", "")
        row_count = response.get("row_count", 0)

        if "success" in msg.lower() or "added" in msg.lower():
            st.success(msg)
        elif row_count > 0 and "found" in msg.lower():
            st.info(msg)
        else:
            st.warning(msg)

        result_data = response.get("data")
        if result_data:
            st.markdown("**Query Results**")
            st.dataframe(pd.DataFrame(result_data), use_container_width=True, hide_index=True)
    else:
        st.write("waiting for input...")
