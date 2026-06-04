import sqlite3
import os

db_path = r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db'
if not os.path.exists(db_path):
    print("Database not found:", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables_to_migrate = ['question_reports', 'question_proposals', 'support_tickets']

for table in tables_to_migrate:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN tags TEXT DEFAULT '[]'")
        print(f"Added tags column to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"Column tags already exists in {table}")
        else:
            print(f"Error altering {table}: {e}")

conn.commit()
conn.close()
