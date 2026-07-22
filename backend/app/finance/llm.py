# ==========================================
# finance/llm.py — Groq LLM Integration
# ==========================================
# Responsible for:
#   1. Building a prompt that constrains the LLM to SELECT-only SQL
#   2. Injecting user_id into the WHERE clause (server-enforced, not LLM-trusted)
#   3. Calling the Groq API and returning raw SQL text
#
# The caller (service.py) is responsible for passing the result through
# sql_guard.validate_sql() before execution.
# ==========================================

import logging
from typing import Optional

from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy-initialised client (avoids import-time failure if key is missing during testing)
_client: Optional[Groq] = None


def _get_client() -> Optional[Groq]:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            logger.critical("GROQ_API_KEY is not set.")
            return None
        try:
            _client = Groq(api_key=settings.groq_api_key)
            logger.info("Groq client initialised.")
        except Exception as e:
            logger.critical("Failed to initialise Groq client: %s", e)
            return None
    return _client


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are an expenses-to-SQL assistant for a multi-user personal finance tracker.
Convert natural language into ONE safe SELECT SQL statement only.

STRICT RULES:
1. Output ONLY a single SELECT statement. No INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER.
2. No SQL comments (-- or /* */).
3. No semicolons.
4. Query ONLY the table: finance_entries
5. Always include the clause: WHERE user_id = {user_id}
   Combine with other conditions using AND.

DATABASE: PostgreSQL
  - Use DATE_TRUNC('month', CURRENT_DATE) for the start of the current month.
  - Use DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' for the start of last month.
  - Use DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' + INTERVAL '1 month - 1 day' for the end of last month.
  - Use CURRENT_DATE for today.
  - Use CURRENT_DATE - INTERVAL '7 days' for 7 days ago.
  - NEVER use SQLite-style date() function with modifier strings like date('now', 'start of month').
  - The `date` column is stored as TEXT in YYYY-MM-DD format; cast with ::date when comparing to date expressions.

SCHEMA (finance_entries):
  id          INTEGER  PRIMARY KEY
  user_id     INTEGER  (always filter by this — provided below)
  purchased   TEXT     (item name)
  categorization TEXT  ['Food & Dining','Transport','Shopping','Entertainment','Healthcare','Utilities','Housing','Business & Software','Income','Other']
  amount      NUMERIC  (decimal, e.g. 250.00; negative = expense, positive = income)
  date        TEXT     (YYYY-MM-DD format, stored as text)
  payment_type TEXT    (e.g. UPI, Cash, Card — may be NULL)
  created_at  TIMESTAMP

EXAMPLES (assume user_id = 42):

Input: "Show me all food expenses"
Output: SELECT * FROM finance_entries WHERE user_id = 42 AND categorization = 'Food & Dining'

Input: "What did I spend the most on this month?"
Output: SELECT categorization, SUM(amount) AS total FROM finance_entries WHERE user_id = 42 AND date::date >= DATE_TRUNC('month', CURRENT_DATE) GROUP BY categorization ORDER BY total DESC LIMIT 1

Input: "Show my expenses last month"
Output: SELECT * FROM finance_entries WHERE user_id = 42 AND date::date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' AND date::date < DATE_TRUNC('month', CURRENT_DATE) ORDER BY date DESC

Input: "What is my highest spend last month?"
Output: SELECT MAX(ABS(amount)) AS highest_spend FROM finance_entries WHERE user_id = 42 AND date::date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' AND date::date < DATE_TRUNC('month', CURRENT_DATE)

Input: "Show my last 10 transactions"
Output: SELECT id, purchased, amount, categorization, date FROM finance_entries WHERE user_id = 42 ORDER BY id DESC LIMIT 10

Input: "What did I spend today?"
Output: SELECT * FROM finance_entries WHERE user_id = 42 AND date::date = CURRENT_DATE

Input: "Show spending in the last 7 days"
Output: SELECT * FROM finance_entries WHERE user_id = 42 AND date::date >= CURRENT_DATE - INTERVAL '7 days' ORDER BY date DESC

Output ONLY the SQL text. No markdown. No explanations.
"""


def generate_sql(question: str, user_id: int) -> Optional[str]:
    """
    Asks Groq to convert a natural-language question into a SELECT SQL statement,
    scoped to the given user_id.

    Returns raw SQL string from the model, or None on failure.
    The caller MUST pass the result through sql_guard.validate_sql().
    """
    client = _get_client()
    if not client:
        return None

    # Inject the real user_id into the system prompt so the model knows it
    prompt = _SYSTEM_PROMPT.format(user_id=user_id)

    try:
        logger.info("Sending request to Groq (user_id=%s, question=%r)", user_id, question)
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,       # deterministic SQL output
            # gpt-oss is a reasoning model whose chain-of-thought counts against
            # max_tokens. Keep reasoning minimal (SQL generation is near-mechanical)
            # and leave ample room for the actual SQL, or the completion gets cut
            # off mid-reasoning and returns empty content (finish_reason=length).
            reasoning_effort="low",
            max_tokens=1200,
            top_p=1,
            stream=False,
        )
        raw_sql = completion.choices[0].message.content.strip()
        logger.info("Groq returned SQL: %s", raw_sql)
        return raw_sql
    except Exception as e:
        logger.error("Groq API error: %s", e)
        return None
