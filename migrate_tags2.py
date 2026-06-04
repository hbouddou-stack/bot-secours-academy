import sqlite3
import os

db_path = r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE chapter_reports ADD COLUMN tags TEXT DEFAULT '[]'")
    print('Added tags column to chapter_reports')
except sqlite3.OperationalError as e:
    print('Error altering chapter_reports:', e)

try:
    cursor.execute("ALTER TABLE questions_proposees ADD COLUMN tags TEXT DEFAULT '[]'")
    print('Added tags column to questions_proposees')
except sqlite3.OperationalError as e:
    print('Error altering questions_proposees:', e)

conn.commit()
conn.close()
