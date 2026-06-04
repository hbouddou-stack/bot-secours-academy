import asyncio
import aiosqlite
import sys
import os

sys.path.append('C:\\Users\\Houssam\\Desktop\\Telegram-Bot-Assets\\telegram-bot-backup')
from config import DATABASE_PATH

async def run():
    print(f"Injecting into {DATABASE_PATH}")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO question_reports (user_id, username, first_name, report_type, notes, urgency, status, source, contact_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (0, "whatsapp_user", "Omar", "schooling", "Je ne comprends pas la lecon 3 de la Sira", "Moyen", "pending", "whatsapp", "+33600000000"))
        
        await db.execute("""
            INSERT INTO question_reports (user_id, username, first_name, report_type, notes, urgency, status, source, contact_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (0, "gmail_user", "Amina", "tech", "Mon mot de passe ne marche pas sur la plateforme", "Critique", "pending", "gmail", "amina@test.com"))
        await db.commit()
    print("Done!")

if __name__ == '__main__':
    asyncio.run(run())
