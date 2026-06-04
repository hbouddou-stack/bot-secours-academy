import asyncio
import aiosqlite
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def read_sira14():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. Generated fiche (résumé IA)
        print("=== GENERATED FICHE (Résumé IA) ===")
        async with db.execute("SELECT content FROM generated_fiches WHERE subject='sira' AND course_number=14") as cur:
            row = await cur.fetchone()
            if row:
                print(row[0][:2000])
            else:
                print("Pas de fiche générée pour Sira 14")
        
        # 2. Questions officielles
        print("\n\n=== QUESTIONS OFFICIELLES (5 premières) ===")
        async with db.execute("SELECT question, choice_a, choice_b, choice_c, choice_d, correct_answer FROM questions WHERE subject='sira' AND lesson_num=14 LIMIT 5") as cur:
            rows = await cur.fetchall()
            for r in rows:
                print(f"Q: {r[0]}")
                print(f"  A: {r[1]}")
                print(f"  B: {r[2]}")
                print(f"  C: {r[3]}")
                print(f"  D: {r[4]}")
                print(f"  Correct: {r[5]}\n")
        
        # 3. Transcription
        print("\n=== TRANSCRIPTION PAGES ===")
        async with db.execute("SELECT page_number, file_id FROM lesson_transcription_pages WHERE subject='sira' AND course_number=14") as cur:
            rows = await cur.fetchall()
            for r in rows:
                print(f"Page {r[0]}: {r[1][:50]}...")
        
        # 4. Existing course_chapters for sira 14
        print("\n=== EXISTING course_chapters for sira 14 ===")
        async with db.execute("SELECT chapter_index, title, content FROM course_chapters WHERE subject='sira' AND course_number=14 ORDER BY chapter_index") as cur:
            rows = await cur.fetchall()
            if rows:
                for r in rows:
                    print(f"Axe {r[0]}: {r[1]}")
                    print(r[2][:300])
            else:
                print("Aucun axe pour Sira 14 actuellement.")

if __name__ == '__main__':
    asyncio.run(read_sira14())
