import sqlite3
import os

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

    # 1. Fetch Sira questions for courses 14-22 from Backup DB
    cur_backup.execute(
        "SELECT id, subject, course_number, course_name, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, source, created_at, hijra_year, theme FROM questions WHERE subject='sira' AND course_number >= 14 AND course_number <= 22"
    )
    rows = cur_backup.fetchall()
    print(f"Fetched {len(rows)} Sira questions (14-22) from Backup DB.")

    # 2. Delete existing Sira questions for courses 14-22 from Main DB
    cur_main.execute(
        "DELETE FROM official_questions WHERE subject='sira' AND course_number >= 14 AND course_number <= 22"
    )
    deleted_count = cur_main.rowcount
    print(f"Deleted {deleted_count} Sira questions (14-22) from Main DB.")

    # 3. Insert the questions from Backup DB into Main DB
    insert_query = """
        INSERT INTO official_questions (
            id, subject, course_number, course_name, question,
            choice_a, choice_b, choice_c, choice_d, correct_answer,
            explanation, source, created_at, hijra_year, theme
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    inserted_count = 0
    for r in rows:
        cur_main.execute(insert_query, r)
        inserted_count += 1

    conn_main.commit()
    print(f"Successfully aligned and inserted {inserted_count} Sira questions into Main DB.")

    conn_backup.close()
    conn_main.close()

if __name__ == "__main__":
    main()
