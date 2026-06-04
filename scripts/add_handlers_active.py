import re

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the start handler
old_start = r'@router\.callback_query\(F\.data\.startswith\("rev_study_path_start:"\)\)\nasync def handle_rev_study_path_start\(callback: CallbackQuery, state: FSMContext\):.*?await render_study_path_syllabus\(callback, state\)'

new_start = '''@router.callback_query(F.data.startswith("rev_study_path_start:"))
async def handle_rev_study_path_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    user_id = callback.from_user.id
    
    chapters = await db.get_course_chapters(subject, lesson)
    if not chapters:
        await callback.message.answer("⚠️ عذراً، لا يوجد مسار قراءة متوفر حالياً لهذا الدرس.")
        return
        
    prog = await db.get_student_course_progress(user_id, subject, lesson)
    # prog is a dict, we added current_chapter_index
    idx = prog.get("current_chapter_index", 0) if prog else 0
    
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    text = (
        f"📚 <b>خطة الدرس {lesson} - {sub_ar}</b>\\n"
        f"المسار التفاعلي مقسم إلى المحاور التالية:\\n\\n"
    )
    for i, ch in enumerate(chapters):
        status = "✅" if i < idx else "⏳"
        text += f"{status} {i+1}. {ch['title']}\\n"
        
    if idx > 0 and idx < len(chapters):
        text += f"\\n💡 <i>أنت حالياً عند المحور {idx + 1}. يمكنك استئناف التعلم من حيث توقفت.</i>"
    elif idx >= len(chapters):
        text += f"\\n🎉 <i>لقد أتممت جميع محاور هذا الدرس بنجاح!</i>"
        
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_active_study_overview_keyboard(subject, lesson, idx, len(chapters)),
        parse_mode="HTML"
    )

# --- Active Study Flow ---

@router.callback_query(F.data.startswith("active_study_go:"))
async def handle_active_study_go(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    user_id = callback.from_user.id
    
    chapters = await db.get_course_chapters(subject, lesson)
    prog = await db.get_student_course_progress(user_id, subject, lesson)
    idx = prog.get("current_chapter_index", 0) if prog else 0
    
    if idx >= len(chapters):
        idx = 0 # reset if restarting
        await db.update_student_course_progress(user_id, subject, lesson, current_chapter_index=0)
        
    chapter = chapters[idx]
    ch_id = chapter['id']
    
    # Clean and format the content
    content_html = format_gemini_markdown_to_html(chapter['content'])
    # Since format_gemini_markdown_to_html returns a list of chunks now:
    if isinstance(content_html, list):
        content_html = "\\n\\n".join(content_html)
        
    text = f"📖 <b>المحور {idx+1}: {chapter['title']}</b>\\n\\n{content_html}"
    
    # Safely edit or send new message if too long
    try:
        await callback.message.delete()
    except: pass
    
    # We might need to split it if it's too long, but let's assume it's small enough since it's just one chapter.
    if len(text) > 4000:
        text = text[:4000]
        
    await callback.message.answer(
        text,
        reply_markup=kb.get_active_study_chapter_summary_keyboard(subject, lesson, ch_id),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("active_study_resume:"))
async def handle_active_study_resume(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    ch_id = int(parts[3])
    
    chapters = await db.get_course_chapters(subject, lesson)
    chapter = next((c for c in chapters if c['id'] == ch_id), None)
    if not chapter: return
    idx = chapters.index(chapter)
    
    content_html = format_gemini_markdown_to_html(chapter['content'])
    if isinstance(content_html, list):
        content_html = "\\n\\n".join(content_html)
        
    text = f"📖 <b>المحور {idx+1}: {chapter['title']}</b>\\n\\n{content_html}"
    if len(text) > 4000: text = text[:4000]
    
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_active_study_chapter_summary_keyboard(subject, lesson, ch_id), parse_mode="HTML")
    except:
        try: await callback.message.delete()
        except: pass
        await callback.message.answer(text, reply_markup=kb.get_active_study_chapter_summary_keyboard(subject, lesson, ch_id), parse_mode="HTML")

@router.callback_query(F.data.startswith("active_study_q:"))
async def handle_active_study_q(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    ch_id = int(parts[3])
    
    import aiosqlite
    from config import DATABASE_PATH
    q_data = None
    async with aiosqlite.connect(DATABASE_PATH) as _db:
        async with _db.execute("SELECT question, choice_a, choice_b, choice_c, choice_d FROM course_chapter_questions WHERE chapter_id=?", (ch_id,)) as _cur:
            q_data = await _cur.fetchone()
            
    if not q_data:
        await callback.message.answer("⚠️ لم يتم العثور على سؤال لهذا المحور.")
        return
        
    choices = {
        'a': q_data[1],
        'b': q_data[2],
        'c': q_data[3],
        'd': q_data[4]
    }
    
    text = f"❓ <b>سؤال المحور:</b>\\n\\n{q_data[0]}"
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_active_study_question_keyboard(subject, lesson, ch_id, choices), parse_mode="HTML")
    except:
        pass

@router.callback_query(F.data.startswith("active_study_skip:"))
async def handle_active_study_skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer("تم تجاوز السؤال! لا تقلق، المهم هو الفهم العام. 👏")
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    ch_id = int(parts[3])
    
    await _advance_chapter(callback, subject, lesson, ch_id)

@router.callback_query(F.data.startswith("active_study_ans:"))
async def handle_active_study_ans(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    ch_id = int(parts[3])
    ans = parts[4]
    
    import aiosqlite
    from config import DATABASE_PATH
    q_data = None
    async with aiosqlite.connect(DATABASE_PATH) as _db:
        async with _db.execute("SELECT correct_answer, explanation FROM course_chapter_questions WHERE chapter_id=?", (ch_id,)) as _cur:
            q_data = await _cur.fetchone()
            
    if not q_data: return
    correct_ans = q_data[0]
    explanation = q_data[1]
    
    if ans == correct_ans:
        await callback.answer("إجابة صحيحة! أحسنت 🌟", show_alert=True)
        # Log correct answer? Actually these are chapter questions, not in `questions` table. So we don't track them in `question_progress`.
        await _advance_chapter(callback, subject, lesson, ch_id, explanation)
    else:
        await callback.answer("إجابة خاطئة! حاول مرة أخرى 🤔", show_alert=True)

async def _advance_chapter(callback: CallbackQuery, subject: str, lesson: int, ch_id: int, explanation: str = None):
    user_id = callback.from_user.id
    chapters = await db.get_course_chapters(subject, lesson)
    chapter = next((c for c in chapters if c['id'] == ch_id), None)
    idx = chapters.index(chapter)
    
    # Increment progress
    new_idx = idx + 1
    await db.update_student_course_progress(user_id, subject, lesson, current_chapter_index=new_idx)
    
    is_last = new_idx >= len(chapters)
    
    text = f"🎉 <b>ممتاز يا {callback.from_user.first_name}! لقد أتممت المحور بنجاح.</b>\\n"
    if explanation:
        text += f"\\n💡 <b>توضيح:</b> {explanation}\\n"
        
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_active_study_next_chapter_keyboard(subject, lesson, is_last), parse_mode="HTML")
    except:
        try: await callback.message.delete()
        except: pass
        await callback.message.answer(text, reply_markup=kb.get_active_study_next_chapter_keyboard(subject, lesson, is_last), parse_mode="HTML")

@router.callback_query(F.data.startswith("active_study_mindmap:"))
async def handle_active_study_mindmap(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    user_id = callback.from_user.id
    
    pages = await db.get_mind_map_pages(subject, lesson)
    if not pages:
        await callback.answer("⚠️ الخريطة الذهنية غير متوفرة لهذا الدرس.", show_alert=True)
        # Directly go to end
        await callback.message.edit_text("🎉 لقد أنهيت جميع المحاور! يمكنك الآن عرض الملخص الشامل أو الانتقال للاختبار.", reply_markup=kb.get_active_study_end_keyboard(subject, lesson))
        return
        
    await callback.answer("جاري تحميل الخريطة الذهنية... 🗺️")
    await db.update_student_course_progress(user_id, subject, lesson, mindmap_done=1)
    
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    caption = f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar})</b>\\n\\nأنت الآن جاهز للملخص الشامل والاختبار!"
    
    try: await callback.message.delete()
    except: pass
    
    # Assuming the first page is the mindmap
    file_id = pages[0]["file_id"]
    from handlers.revision import _send_map_photo
    await _send_map_photo(
        callback.message.bot,
        chat_id=user_id,
        file_id=file_id,
        caption=caption,
        reply_markup=kb.get_active_study_end_keyboard(subject, lesson)
    )
'''

content = re.sub(old_start, new_start, content, flags=re.DOTALL)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(content)
