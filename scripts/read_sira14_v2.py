import asyncio
import aiosqlite
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def read_sira14():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. Generated fiche (résumé IA) - FULL content
        print("=== GENERATED FICHE (FULL) ===")
        async with db.execute("SELECT content FROM generated_fiches WHERE subject='sira' AND course_number=14") as cur:
            row = await cur.fetchone()
            if row:
                print(row[0])
            else:
                print("PAS DE FICHE")
        
        # 2. Questions officielles (course_number)
        print("\n\n=== QUESTIONS OFFICIELLES (10 premières) ===")
        async with db.execute("SELECT question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation FROM questions WHERE subject='sira' AND course_number=14 LIMIT 10") as cur:
            rows = await cur.fetchall()
            if rows:
                for i, r in enumerate(rows, 1):
                    print(f"Q{i}: {r[0]}")
                    print(f"  A: {r[1]}")
                    print(f"  B: {r[2]}")
                    print(f"  C: {r[3]}")
                    print(f"  D: {r[4]}")
                    print(f"  Correct: {r[5]}")
                    print(f"  Expl: {r[6]}\n")
            else:
                print("Aucune question pour sira/14")

if __name__ == '__main__':
    asyncio.run(read_sira14())
