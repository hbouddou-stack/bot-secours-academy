import asyncio
import aiosqlite
import os
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"
TRANSCRIPT_PATH = r"C:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot\lessons\transcripts\sira\sira_14.txt"

def read_transcript():
    with open(TRANSCRIPT_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def generate_axes(transcript_text):
    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""أنت مساعد تعليمي متخصص في السيرة النبوية. مهمتك هي تحليل هذه التفريغ من دروس الشيخ ياسين العمري وتقسيمها إلى محاور تعليمية متسلسلة.

**التعليمات الصارمة:**
1. قسّم التفريغ إلى 6-9 محاور موضوعية منطقية
2. كل محور يجب أن يحتوي على:
   - **عنوان** واضح ومختصر
   - **شرح وافٍ** مأخوذ مباشرة من كلام الشيخ (بالأسلوب التفسيري، لا مجرد نقاط مبعثرة)
   - الشرح يكون بصيغة تعليمية مستمرة تُحافظ على روح الشيخ وتفسيراته
   - استخدم **تنسيق Telegram HTML** فقط: <b>نص</b> للغامق، لا تستخدم Markdown
   - استخدم نقاط البولت • للقوائم إذا لزم
3. لكل محور، اكتب **سؤالاً واحداً** اختيارياً من 4 خيارات، مبنياً على أهم فكرة في المحور
4. **المصدر هو التفريغ فقط** - لا تضف معلومات من خارجه

**أرجع النتيجة في JSON بهذا الشكل الدقيق:**
```json
{{
  "axes": [
    {{
      "index": 1,
      "title": "عنوان المحور",
      "content": "شرح وافٍ مأخوذ من كلام الشيخ...",
      "question": "نص السؤال؟",
      "choice_a": "الخيار الأول",
      "choice_b": "الخيار الثاني",
      "choice_c": "الخيار الثالث",
      "choice_d": "الخيار الرابع",
      "correct_answer": "a",
      "explanation": "شرح سبب الإجابة الصحيحة"
    }}
  ]
}}
```

**التفريغ:**
{transcript_text}

**مهم:** أرجع JSON نظيفاً فقط بدون أي نص إضافي قبله أو بعده."""

    response = client.models.generate_content(
        model='gemini-2.0-flash-lite',
        contents=prompt
    )
    return response.text

async def inject_axes(axes_data):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Clear old data for sira 14
        await db.execute("DELETE FROM course_chapters WHERE subject='sira' AND course_number=14")
        await db.commit()
        
        for axe in axes_data['axes']:
            cursor = await db.execute(
                """INSERT INTO course_chapters 
                   (subject, course_number, chapter_index, title, content) 
                   VALUES (?, ?, ?, ?, ?)""",
                ('sira', 14, axe['index'], axe['title'], axe['content'])
            )
            ch_id = cursor.lastrowid
            
            await db.execute(
                """INSERT INTO course_chapter_questions 
                   (chapter_id, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ch_id,
                    axe['question'],
                    axe['choice_a'],
                    axe['choice_b'],
                    axe['choice_c'],
                    axe['choice_d'],
                    axe['correct_answer'],
                    axe['explanation']
                )
            )
        
        await db.commit()
        print(f"✅ Injected {len(axes_data['axes'])} axes for Sira 14")

async def main():
    print("📖 Reading transcript...")
    transcript = read_transcript()
    print(f"  Transcript: {len(transcript)} chars")
    
    print("🤖 Calling Gemini to generate axes...")
    raw_response = generate_axes(transcript)
    
    # Clean JSON
    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    if not json_match:
        print("❌ Could not find JSON in response")
        print(raw_response[:500])
        return
    
    json_str = json_match.group(0)
    axes_data = json.loads(json_str)
    
    print(f"✅ Gemini generated {len(axes_data['axes'])} axes:")
    for a in axes_data['axes']:
        print(f"  Axe {a['index']}: {a['title']}")
    
    print("\n💾 Injecting into database...")
    await inject_axes(axes_data)

if __name__ == '__main__':
    asyncio.run(main())
