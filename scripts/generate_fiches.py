import asyncio
import sqlite3
import google.generativeai as genai
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GEMINI_API_KEYS

genai.configure(api_key=GEMINI_API_KEYS[0])

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backup_bot.db")

PROMPTS = {
    "aqeeda": """أنت أستاذ خبير في العقيدة الإسلامية. 
قم بتلخيص هذا النص في "ملخص شامل" يحتوي حصراً على هذه العناصر بنفس العناوين:
1. 🔹 الخلاصة المحورية للدرس (في أسطر):
2. 🔹 القواعد والمسائل العقدية بالتفصيل:
3. 🔹 الأسماء والمصطلحات الرئيسية التي وردت:
4. 🔹 العِبر والأحكام المستفادة:
5. 🔹 سؤال تدبر ومراجعة ذاتية:
استخدم تنسيق Markdown و <b> </b> للكلمات المهمة.""",

    "fiqh": """أنت فقيه خبير. 
قم بتلخيص هذا النص في "ملخص شامل" يحتوي حصراً على هذه العناصر بنفس العناوين:
1. 🔹 الخلاصة المحورية للدرس (في أسطر):
2. 🔹 الأحكام الشرعية والأدلة بالتفصيل:
3. 🔹 الشروط والمصطلحات الفقهية الرئيسية:
4. 🔹 العِبر والأحكام المستفادة:
5. 🔹 سؤال تدبر ومراجعة ذاتية:
استخدم تنسيق Markdown و <b> </b> للكلمات المهمة.""",

    "sira": """أنت مؤرخ خبير في السيرة النبوية. 
قم بتلخيص هذا النص في "ملخص شامل" يحتوي حصراً على هذه العناصر بنفس العناوين:
1. 🔹 الخلاصة المحورية للدرس (في أسطر):
2. 🔹 الأحداث والوقائع بالتفصيل:
3. 🔹 الأسماء والتواريخ والمصطلحات الرئيسية التي وردت:
4. 🔹 العِبر والأحكام المستفادة:
5. 🔹 سؤال تدبر ومراجعة ذاتية:
استخدم تنسيق Markdown و <b> </b> للكلمات المهمة.""",

    "nahw": """أنت نحوي خبير في اللغة العربية. 
قم بتلخيص هذا النص في "ملخص شامل" يحتوي حصراً على هذه العناصر بنفس العناوين:
1. 🔹 الخلاصة المحورية للدرس (في أسطر):
2. 🔹 القواعد النحوية والإعراب بالتفصيل (مع الأمثلة):
3. 🔹 المصطلحات النحوية الرئيسية:
4. 🔹 العِبر والأحكام المستفادة:
5. 🔹 سؤال تدبر ومراجعة ذاتية:
استخدم تنسيق Markdown و <b> </b> للكلمات المهمة."""
}

async def generate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Init table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_fiches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            course_number INTEGER,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    # Get distinct lessons
    cursor.execute("SELECT DISTINCT subject, course_number FROM course_chapters")
    lessons = cursor.fetchall()
    
    model = genai.GenerativeModel('gemini-2.5-flash')

    for subject, course_number in lessons:
        cursor.execute("SELECT id FROM generated_fiches WHERE subject=? AND course_number=?", (subject, course_number))
        if cursor.fetchone():
            continue # already generated
            
        print(f"Generating for {subject} {course_number}...")
        cursor.execute("SELECT content FROM course_chapters WHERE subject=? AND course_number=?", (subject, course_number))
        texts = [r[0] for r in cursor.fetchall() if r[0]]
        full_text = "\n\n".join(texts)
        if not full_text.strip():
            continue
            
        prompt = PROMPTS.get(subject, PROMPTS["sira"])
        full_prompt = f"{prompt}\n\nالنص المراد تلخيصه:\n{full_text}"
        
        try:
            response = await model.generate_content_async(full_prompt)
            content = response.text
            cursor.execute("INSERT INTO generated_fiches (subject, course_number, content) VALUES (?, ?, ?)", (subject, course_number, content))
            conn.commit()
            print(f"Success {subject} {course_number}")
        except Exception as e:
            print(f"Failed {subject} {course_number}: {e}")
            
    conn.close()

if __name__ == "__main__":
    asyncio.run(generate())
