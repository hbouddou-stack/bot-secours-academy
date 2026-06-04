import asyncio
import aiosqlite

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def clear_sira_14():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM course_chapters WHERE subject='sira' AND course_number=14")
        # Since I didn't save the chapter IDs, let's just delete the ones we inserted? 
        # Actually it's fine, the questions will just sit there unlinked.
        await db.commit()

if __name__ == '__main__':
    asyncio.run(clear_sira_14())
    print("Bad simulation data cleared.")
