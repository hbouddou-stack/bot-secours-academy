import sqlite3
import os
import sys

# Force stdout to use UTF-8 to prevent UnicodeEncodeError on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_BACKUP_PATH = "telegram-bot-backup/backup_bot.db"
DB_MAIN_PATH = "telegram-bot/persistent_storage/academy.db"

def main():
    if not os.path.exists(DB_BACKUP_PATH):
        print(f"Backup DB not found at: {DB_BACKUP_PATH}")
        return
    if not os.path.exists(DB_MAIN_PATH):
        print(f"Main DB not found at: {DB_MAIN_PATH}")
        return

    conn_backup = sqlite3.connect(DB_BACKUP_PATH)
    cur_backup = conn_backup.cursor()

    conn_main = sqlite3.connect(DB_MAIN_PATH)
    cur_main = conn_main.cursor()

    # 1. Sync explanations from Main DB to Backup DB where they exist
    print("Syncing explanations from Main DB to Backup DB...")
    cur_main.execute(
        "SELECT id, explanation FROM official_questions WHERE subject='sira' AND course_number >= 14 AND course_number <= 22"
    )
    main_rows = cur_main.fetchall()
    
    synced_count = 0
    for q_id, main_exp in main_rows:
        if main_exp and len(main_exp.strip()) > 15:
            # Check if backup DB needs it
            cur_backup.execute("SELECT explanation FROM questions WHERE id = ?", (q_id,))
            backup_row = cur_backup.fetchone()
            if backup_row:
                backup_exp = backup_row[0]
                if not backup_exp or len(backup_exp.strip()) <= 15:
                    cur_backup.execute("UPDATE questions SET explanation = ? WHERE id = ?", (main_exp, q_id))
                    synced_count += 1
    
    conn_backup.commit()
    print(f"Synced {synced_count} explanations to Backup DB.")

    # 2. Count missing in both databases
    cur_backup.execute(
        "SELECT id, course_number, question, correct_answer FROM questions WHERE subject='sira' AND course_number >= 14 AND course_number <= 22"
    )
    backup_questions = cur_backup.fetchall()
    
    missing_backup = []
    for q in backup_questions:
        q_id, cn, question_text, correct_ans = q
        cur_backup.execute("SELECT explanation FROM questions WHERE id = ?", (q_id,))
        exp = cur_backup.fetchone()[0]
        if not exp or len(exp.strip()) <= 15:
            missing_backup.append((q_id, cn, question_text, correct_ans))

    print(f"\nStatus after sync:")
    print(f"- Total Sira questions (14-22) in Backup DB: {len(backup_questions)}")
    print(f"- Missing explanations in Backup DB: {len(missing_backup)}")
    for q_id, cn, text, ans in missing_backup:
        snippet = text.strip()[:50] + "..." if len(text.strip()) > 50 else text.strip()
        print(f"  * [Course {cn}] Q {q_id}: {snippet} (Ans: {ans})")

    conn_backup.close()
    conn_main.close()

if __name__ == "__main__":
    main()
