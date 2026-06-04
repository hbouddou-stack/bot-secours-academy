import asyncio
import aiosqlite
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def check():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        print("=== ALL lesson_transcription_pages for sira ===")
        async with db.execute(
            "SELECT subject, course_number, page_number, file_id FROM lesson_transcription_pages WHERE subject='sira' ORDER BY course_number, page_number"
        ) as cur:
            rows = await cur.fetchall()
            for r in rows:
                print(f"  Sira {r['course_number']} - Page {r['page_number']}: {r['file_id'][:60]}...")
        
        if not rows:
            print("  Aucune transcription trouvée pour Sira")
        
        print("\n=== ALL lesson_resources for sira ===")
        async with db.execute(
            "SELECT subject, course_number, mind_map_file_id, summary_file_id FROM lesson_resources WHERE subject='sira'"
        ) as cur:
            rows = await cur.fetchall()
            for r in rows:
                print(f"  Sira {r['course_number']}: mind_map={bool(r['mind_map_file_id'])}, summary={bool(r['summary_file_id'])}")

if __name__ == '__main__':
    asyncio.run(check())
