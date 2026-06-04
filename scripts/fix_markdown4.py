import html
import re

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace format_gemini_markdown_to_html and handle_guided_step_summary
start_idx = content.find("def format_gemini_markdown_to_html(text):")
end_idx = content.find("@router.callback_query(F.data.startswith(\"guided_step:\") & F.data.endswith(\":flashcards\"))")

old_code = content[start_idx:end_idx]

new_code = '''def format_gemini_markdown_to_html(text):
    if not text:
        return []
    
    # 1. Clean HTML escaping but preserve Gemini's <b> tags
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
    
    # 2. Bold: **text**
    text = re.sub(r'\\*\\*(.+?)\\*\\*', r'<b>\\1</b>', text)
    
    # 3. Headers: ## text
    text = re.sub(r'^#+\\s+(.+)$', r'<b>\\1</b>', text, flags=re.MULTILINE)
    
    # 4. Bullets: * text
    text = re.sub(r'^\\s*[\\*\\-]\\s+(.+)$', r'• \\1', text, flags=re.MULTILINE)
    
    # 5. Split by sections and wrap in blockquotes
    parts = re.split(r'\\n(?=\\d+\\.\\s+🔹)', text)
    
    messages = []
    current_msg = ""
    
    for p in parts:
        p = p.strip()
        if not p:
            continue
            
        # Wrap section in blockquote
        if re.match(r'^\\d+\\.\\s+🔹', p):
            p = f"<blockquote>{p}</blockquote>"
            
        # Check length
        if len(current_msg) + len(p) > 3800:
            messages.append(current_msg)
            current_msg = p + "\\n\\n"
        else:
            current_msg += p + "\\n\\n"
            
    if current_msg:
        messages.append(current_msg)
        
    return messages

@router.callback_query(F.data.startswith("guided_step:") & F.data.endswith(":summary"))
async def handle_guided_step_summary(callback: CallbackQuery):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    user_id = callback.from_user.id
    
    # Try fetching from generated_fiches first
    import aiosqlite
    from config import DATABASE_PATH
    fiche_content = None
    async with aiosqlite.connect(DATABASE_PATH) as _db:
        async with _db.execute("SELECT content FROM generated_fiches WHERE subject=? AND course_number=?", (subject, lesson)) as _cursor:
            row = await _cursor.fetchone()
            if row:
                fiche_content = row[0]
                
    if fiche_content:
        await callback.answer("⏳ جاري تحميل الملخص...")
        await db.update_student_course_progress(user_id, subject, lesson, resume_done=1)
        sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
        
        # Get formatted messages chunks
        messages_chunks = format_gemini_markdown_to_html(fiche_content)
        
        for i, chunk in enumerate(messages_chunks):
            if i == 0:
                await callback.message.answer(f"📑 <b>الملخص الشامل - {sub_ar} (درس {lesson})</b>\\n\\n{chunk}", parse_mode="HTML")
            else:
                await callback.message.answer(chunk, parse_mode="HTML")
                
        text_done = (
            f"🎉 <b>أحسنت يا {callback.from_user.first_name}! لقد أتممت قراءة الملخص للدرس {lesson}!</b>\\n\\n"
            f"تم تحديث تقدمك بنجاح. يمكنك الآن الانتقال إلى الخطوة التالية (بطاقات الاستذكار)."
        )
        kb_next = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎴 الانتقال لبطاقات الاستذكار", callback_data=f"guided_step:{subject}:{lesson}:flashcards")],
            [InlineKeyboardButton(text="↩️ العودة لصفحة الدرس", callback_data=f"guided_path_les:{subject}:{lesson}")]
        ])
        await callback.message.answer(text_done, reply_markup=kb_next, parse_mode="HTML")
        
    else:
        # Fallback to document
        resources = await db.get_lesson_resources(subject, lesson)
        file_id = resources.get("summary_file_id") if resources else None
        
        if not file_id:
            await callback.answer("⚠️ الملخص الشامل قيد التحضير بواسطة الذكاء الاصطناعي ولن يتوفر حالياً.", show_alert=True)
            return
            
        await callback.answer("⏳ جاري إرسال الملف...")
        await db.update_student_course_progress(user_id, subject, lesson, resume_done=1)
        sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
        await callback.message.bot.send_document(
            chat_id=callback.from_user.id,
            document=file_id,
            caption=f"📄 <b>ملف تفريغ الدرس {lesson} ({sub_ar})</b>",
            parse_mode="HTML"
        )
        
        text_done = (
            f"🎉 <b>أحسنت يا {callback.from_user.first_name}! لقد أتممت قراءة الملخص للدرس {lesson}!</b>\\n\\n"
            f"تم تحديث تقدمك بنجاح. يمكنك الآن الانتقال إلى الخطوة التالية (بطاقات الاستذكار)."
        )
        kb_next = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎴 الانتقال لبطاقات الاستذكار", callback_data=f"guided_step:{subject}:{lesson}:flashcards")],
            [InlineKeyboardButton(text="↩️ العودة لصفحة الدرس", callback_data=f"guided_path_les:{subject}:{lesson}")]
        ])
        await callback.message.answer(text_done, reply_markup=kb_next, parse_mode="HTML")

'''

content = content.replace(old_code, new_code)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(content)
