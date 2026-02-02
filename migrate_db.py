import sqlite3
import os

# Copy logic from app.py to find DB
base_dir = '/data' if os.path.exists('/data') else os.path.join(os.getcwd(), 'data')
DB_PATH = os.path.join(base_dir, 'snippets.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at {DB_PATH}. Skipping migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if column exists
    c.execute("PRAGMA table_info(snippet)")
    columns = [info[1] for info in c.fetchall()]

    if 'parsing_mode' not in columns:
        print("Adding 'parsing_mode' column to snippet table...")
        try:
            c.execute("ALTER TABLE snippet ADD COLUMN parsing_mode TEXT DEFAULT 'weblint'")
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("'parsing_mode' column already exists.")

    conn.close()

if __name__ == '__main__':
    migrate()
