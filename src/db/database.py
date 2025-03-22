# db/database.py

import sqlite3
import os

def create_connection(db_file="database.db"):
    """
    Create a database connection to the SQLite database specified by db_file.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def create_tables(conn):
    """
    Create the users and payments tables.
    """
    # SQL to create the users table
    create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT,
        paid_until TEXT,
        last_payment_date TEXT
    );
    """
    
    # SQL to create the payments table
    create_payments_table = """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        payment_date TEXT,
        paid_until TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """
    
    try:
        cur = conn.cursor()
        cur.execute(create_users_table)
        cur.execute(create_payments_table)
        conn.commit()
        print("Tables created successfully.")
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")

def init_db():
    """
    Initialize the database and create tables if they do not exist.
    """
    # Define the path to the database (you can adjust the path as needed)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "database.db")
    
    conn = create_connection(db_path)
    if conn is not None:
        create_tables(conn)
        conn.close()
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    init_db()