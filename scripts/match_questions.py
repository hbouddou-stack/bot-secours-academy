import sqlite3
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    conn_main = sqlite3.connect('telegram-bot/persistent_storage/academy.db')
    cur_main = conn_main.cursor()

    cur_main.execute(
        "SELECT id, course_number, question, explanation FROM official_questions WHERE subject='sira' AND course_number >= 14 AND course_number <= 22"
    )
    rows = cur_main.fetchall()
    print(f"Total Sira questions (14-22) in Main DB: {len(rows)}")
    for r in rows:
        q_id, cn, text, exp = r
        exp_status = "Has explanation" if (exp and len(exp.strip()) > 15) else "No explanation"
        print(f"ID {q_id} (Course {cn}): {text[:60]} [{exp_status}]")

    conn_main.close()

if __name__ == "__main__":
    main()
