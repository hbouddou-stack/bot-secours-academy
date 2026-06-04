import asyncio
import aiosqlite
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def inspect():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # What lessons have chapters?
        async with db.execute("""
            SELECT subject, course_number, COUNT(*) as nb 
            FROM course_chapters 
            GROUP BY subject, course_number
            ORDER BY subject, course_number
        """) as cur:
            rows = await cur.fetchall()
            print("=== LESSONS WITH course_chapters ===")
            for r in rows:
                print(f"  {r['subject']} / leçon {r['course_number']}: {r['nb']} axes")
        
        # Show a full example of one lesson's chapters
        if rows:
            subj = rows[0]['subject']
            num = rows[0]['course_number']
            print(f"\n=== FULL EXAMPLE: {subj} / leçon {num} ===")
            async with db.execute("""
                SELECT chapter_index, title, content 
                FROM course_chapters 
                WHERE subject=? AND course_number=?
                ORDER BY chapter_index
            """, (subj, num)) as cur:
                chapters = await cur.fetchall()
                for ch in chapters:
                    print(f"\n--- Axe {ch['chapter_index']}: {ch['title']} ---")
                    print(ch['content'])
                    print()

if __name__ == '__main__':
    asyncio.run(inspect())
