import asyncio
import aiosqlite

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def explore():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. List all tables
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") as cur:
            tables = [r[0] for r in await cur.fetchall()]
        print("=== TABLES ===")
        for t in tables:
            print(t)
        
        print("\n=== Search for Sira lesson 14 content ===")
        
        # Check 'chapters' or transcription type tables
        for table in tables:
            async with db.execute(f"SELECT COUNT(*) FROM {table}") as cur:
                count = (await cur.fetchone())[0]
            if count > 0:
                print(f"Table '{table}': {count} rows")
        
        print("\n=== Looking for lesson content in 'lessons' or similar ===")
        for table in tables:
            if any(keyword in table.lower() for keyword in ['lesson', 'chapter', 'cours', 'transcript', 'content', 'fiche', 'sira', 'resume', 'summary']):
                async with db.execute(f"PRAGMA table_info({table})") as cur:
                    cols = [r[1] for r in await cur.fetchall()]
                print(f"Table '{table}' columns: {cols}")
                
                # Look for sira 14 specifically
                for col in ['subject', 'matiere', 'course', 'lesson']:
                    if col in cols:
                        try:
                            async with db.execute(f"SELECT * FROM {table} WHERE {col} LIKE '%sira%' LIMIT 2") as cur:
                                rows = await cur.fetchall()
                                if rows:
                                    print(f"  Found {len(rows)} sira rows in '{table}.{col}'")
                                    for r in rows[:1]:
                                        print(f"  Sample: {dict(r)}")
                        except Exception as e:
                            pass

if __name__ == '__main__':
    asyncio.run(explore())
