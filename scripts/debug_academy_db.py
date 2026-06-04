import sqlite3
import sys

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')

db_path = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot\persistent_storage\academy.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT * FROM course_videos WHERE course_number BETWEEN 14 AND 24;")
rows = cursor.fetchall()
print("Course Videos:")
for r in rows:
    print(r)

conn.close()
