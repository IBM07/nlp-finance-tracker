# Is in python by default, No Library Neede!
import sqlite3

connection = sqlite3.connect("student.db")

# Create a cursor object to insert record, create table, retrieve
cursor = connection.cursor()

table_info = """
Create table Finance(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchased VARCHAR NOT NULL,
    categorization TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    payment_type TEXT)
"""

cursor.execute(table_info)

connection.commit()
connection.close()