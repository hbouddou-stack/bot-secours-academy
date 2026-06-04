import sqlite3

conn = sqlite3.connect(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db')
c = conn.cursor()
c.execute("SELECT chapter_index, title, content FROM course_chapters WHERE subject='sira' AND course_number=14 ORDER BY chapter_index")
rows = c.fetchall()
if rows:
    for r in rows:
        print(f"--- Chapter {r[0]}: {r[1]} ---")
        print(r[2][:200])
else:
    print("No chapters found for Sira 14")
