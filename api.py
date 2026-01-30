# ==========================================
# FASTAPI BACKEND SERVICE
# ==========================================
# This file serves as the core backend API for the AI Finance Tracker.
# It decouples the UI (Streamlit) from the Business Logic (AI + DB).
# 
# Usage:
#   uvicorn api:app --reload
# ==========================================

import os
import sqlite3
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List, Optional, Any
from groq import Groq

# --- CONFIGURATION & LOGGING ---
# Load environment variables
load_dotenv()

# Configure Logging (Production Requirement)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backend.log"), # Log to file
        logging.StreamHandler()             # Log to console
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="AI Finance Tracker API (Groq Edition)", version="2.0.0")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq Client
API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY:
    logger.critical("GROQ_API_KEY not found in environment variables. API will fail.")
    client = None
else:
    try:
        client = Groq(api_key=API_KEY)
        logger.info("Groq Client initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize Groq Client: {e}")
        client = None

# --- MODELS ---
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    sql: Optional[str] = None
    data: Optional[List[Any]] = None
    row_count: Optional[int] = None
    message: str

# --- PROMPT TEMPLATE ---
PROMPT = [
    """
    You are an expenses-to-SQL assistant for a simple personal financial tracker.
    Your job is to convert natural language into ONE safe, parameterized SQL statement.
    You can INSERT, SELECT, UPDATE, or DELETE data.

    SAFETY & SECURITY RULES (Industry Standard):
    1. **NO DESTRUCTIVE DDL**: Never generate DROP, TRUNCATE, ALTER, or GRANT.
    2. **SAFE UPDATES/DELETES**: 
       - If the user asks to "update/delete the last purchase", you MUST use a subquery for the ID, because SQLite does not support ORDER BY in UPDATE/DELETE.
       - Pattern: `UPDATE Finance SET amount=300 WHERE id = (SELECT id FROM Finance ORDER BY id DESC LIMIT 1);`
       - Never update/delete without a WHERE clause unless explicitly asked to "delete all".

    STRICT SCHEMA:
    - Table: `Finance`
    - Columns: `id` (INT), `purchased` (STR), `categorization` (STR), `amount` (REAL), `date` (STR), `payment_type` (STR).
    - Categorization: Normalize to ['Food', 'Transport', 'Utilities', 'Shopping', 'Entertainment', 'Healthcare', 'Other'].

    EXAMPLES:

    Input: "I spent 250 on pizza"
    Output: `INSERT INTO Finance (purchased, categorization, amount, date, payment_type) VALUES ('pizza', 'Food', 250, '2025-01-30', NULL);`

    Input: "Show me all food from yesterday"
    Output: `SELECT * FROM Finance WHERE categorization='Food' AND date = date('now', '-1 day');`

    Input: "Change the last expense to 300 instead of 250"
    Output: `UPDATE Finance SET amount = 300 WHERE id = (SELECT id FROM Finance ORDER BY id DESC LIMIT 1);`

    Input: "Delete the last transaction"
    Output: `DELETE FROM Finance WHERE id = (SELECT id FROM Finance ORDER BY id DESC LIMIT 1);`
    
    Output ONLY text of the SQL. No markdown fences.
    """
]

# --- HELPER FUNCTIONS ---

def is_spam_input(user_input: str) -> bool:
    """Checks for harmful or spammy content locally."""
    try:
        spam_keywords = [
            "rob", "hack", "steal", "terrorist", "attack",
            "kill", "murder", "drugs", "bomb", "scam", "fraud"
        ]
        user_input_lower = user_input.lower()
        is_spam = any(word in user_input_lower for word in spam_keywords)
        if is_spam:
            logger.warning(f"Spam detected in input: {user_input}")
        return is_spam
    except Exception as e:
        logger.error(f"Error in spam filter: {e}")
        return True # Fail safe

def get_ai_response(question, prompt) -> Optional[str]:
    """
    Calls Groq API to convert text to SQL.
    Uses 'llama3-70b-8192' for high precision.
    """
    if not client:
        logger.error("Groq Client is not initialized.")
        return None

    try:
        logger.info("Sending request to Groq API...")
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt[0]},
                {"role": "user", "content": question}
            ],
            temperature=0, # Deterministic output ensures valid SQL
            max_tokens=200,
            top_p=1,
            stop=None,
            stream=False
        )
        response_text = completion.choices[0].message.content.strip()
        logger.info("Received response from Groq.")
        return response_text
    except Exception as e:
        logger.error(f"Groq API Error: {e}")
        return None

def read_sql_query(sql, db_path="student.db"):
    """Executes SQL against SQLite."""
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            logger.info(f"Executing SQL: {sql}")
            cur.execute(sql)
            
            if sql.strip().upper().startswith("SELECT"):
                rows = cur.fetchall()
                logger.info(f"Query returned {len(rows)} rows.")
                return rows, None
            else:
                conn.commit()
                logger.info(f"Modification affected {cur.rowcount} rows.")
                return None, cur.rowcount
    except sqlite3.Error as e:
        logger.error(f"Database Execution Error: {e}")
        return None, None

# --- API ENDPOINTS ---

@app.get("/")
def health_check():
    logger.info("Health check requested.")
    return {"status": "ok", "service": "Finance Tracker API (Groq)"}

@app.post("/query", response_model=QueryResponse)
def process_query(req: QueryRequest):
    """
    Main pipeline:
    1. Check Spam
    2. Get SQL from AI (Groq)
    3. Execute SQL
    4. Return formatted response
    """
    logger.info(f"Received query: {req.question}")

    # 1. Spam Check
    if is_spam_input(req.question):
        logger.warning(f"Query blocked by spam filter: {req.question}")
        return QueryResponse(message="Security Alert: Please don't spam or misuse the app.", sql=None)

    # 2. AI Generation
    sql = get_ai_response(req.question, PROMPT)
    if not sql:
        raise HTTPException(status_code=503, detail="AI Service unavailable")
    
    # 2.5 Safety Check on AI Output
    if "misuse" in sql.lower() or "spam" in sql.lower():
         logger.warning(f"AI refused request: {sql}")
         return QueryResponse(message=sql, sql=None)

    # 3. Database Execution
    rows, row_count = read_sql_query(sql)
    
    # 4. Formulate Response
    sql_upper = sql.strip().upper()
    
    if sql_upper.startswith("INSERT"):
        msg = "Expense successfully added!"
    elif sql_upper.startswith("UPDATE") or sql_upper.startswith("DELETE"):
        msg = f"Operation successful. Affected {row_count} records."
    elif rows is not None:
        msg = f"Found {len(rows)} records."
    else:
        msg = "Error executing query."

    logger.info(f"Request processed. Status: {msg}")
    return QueryResponse(
        sql=sql,
        data=rows,
        row_count=row_count,
        message=msg
    )

@app.get("/analytics")
def get_analytics():
    """
    Returns spending broken down by category.
    Useful for Pie Charts / Bar Charts.
    """
    logger.info("Analytics data requested.")
    sql = "SELECT categorization, SUM(amount) as total FROM Finance GROUP BY categorization ORDER BY total DESC"
    
    try:
        # Re-using read_sql_query helper (safely ignores row_count logic for SELECTs)
        rows, _ = read_sql_query(sql)
        if rows:
            # Format as list of dicts for easier frontend consumption
            data = [{"category": row[0], "total": row[1]} for row in rows]
            return {"status": "success", "data": data}
        else:
            return {"status": "success", "data": []}
    except Exception as e:
        logger.error(f"Analytics Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch analytics")

@app.get("/recent")
def get_recent_transactions():
    """
    Returns the 5 most recent transactions.
    Useful for the Dashboard 'Recent Activity' widget.
    """
    logger.info("Recent transactions requested.")
    sql = "SELECT id, purchased, amount, categorization, date FROM Finance ORDER BY id DESC LIMIT 5"
    
    try:
        rows, _ = read_sql_query(sql)
        if rows:
            # Format: ID, Item, Amount, Category, Date
            data = [
                {
                    "id": row[0],
                    "item": row[1],
                    "amount": row[2],
                    "category": row[3],
                    "date": row[4]
                }
                for row in rows
            ]
            return {"status": "success", "data": data}
        else:
            return {"status": "success", "data": []}
    except Exception as e:
        logger.error(f"Recent Data Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent data")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
