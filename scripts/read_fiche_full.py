import asyncio
import aiosqlite
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def read():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT content FROM generated_fiches WHERE subject='sira' AND course_number=14") as cur:
            row = await cur.fetchone()
            if row:
                print(row[0])
            else:
                print("PAS DE FICHE")

if __name__ == '__main__':
    asyncio.run(read())
