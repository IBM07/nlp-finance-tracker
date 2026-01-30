import sqlite3
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# DATABASE INITIALIZATION SCRIPT
# ==========================================
# Current DB: SQLite (Local file 'student.db')
# Future DB: MySQL (Industry Ready)
# 
# TODO FOR MIGRATION TO MYSQL:
# 1. Replace `import sqlite3` with `import mysql.connector` (or `pymysql`).
# 2. Change connection string: sqlite3.connect(...) -> mysql.connector.connect(host=..., user=..., password=...).
# 3. Update data types: `TEXT` -> `VARCHAR(255)`, `REAL` -> `DECIMAL(10,2)` for financial precision.
# ==========================================

def init_db():
    """
    Initializes the local SQLite database.
    Uses 'IF NOT EXISTS' to ensure modifying this script doesn't destroy existing data.
    """
    try:
        # Use context manager to ensure the connection is closed automatically (avoids file locks)
        with sqlite3.connect("student.db") as connection:
            cursor = connection.cursor()
            
            # Define the schema. 
            # Note: We use standard SQL types compatible with most relational DBs.
            table_info = """
            CREATE TABLE IF NOT EXISTS Finance(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchased VARCHAR NOT NULL,     -- Item name
                categorization TEXT NOT NULL,   -- Category (Food, Transport, etc.)
                amount REAL NOT NULL,           -- Cost of item
                date TEXT NOT NULL,             -- Date in YYYY-MM-DD format
                payment_type TEXT               -- Method (UPI, Cash, etc.)
            );
            """
            
            cursor.execute(table_info)
            connection.commit()
            logger.info("Database 'student.db' and table 'Finance' checked/created successfully.")
            
    except sqlite3.Error as e:
        logger.critical(f"CRITICAL ERROR: Could not create database. Reason: {e}")

if __name__ == "__main__":
    init_db()