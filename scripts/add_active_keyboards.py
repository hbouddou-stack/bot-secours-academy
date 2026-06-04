with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'a', encoding='utf-8') as f:
    f.write('''

# --- Active Study Keyboards ---

def get_active_study_overview_keyboard(subject: str, lesson_num: int, current_chapter_index: int, total_chapters: int) -> InlineKeyboardMarkup:
    """Keyboard for the overview of Active Study path."""
    rows = []
    
    if current_chapter_index > 0 and current_chapter_index < total_chapters:
        start_btn_text = f"▶️ استئناف التعلم (من المحور {current_chapter_index + 1})"
    elif current_chapter_index >= total_chapters:
        start_btn_text = "🔁 إعادة المسار التفاعلي"
    else:
        start_btn_text = "▶️ بدء التعلم التفاعلي"
        
    rows.append([InlineKeyboardButton(text=start_btn_text, callback_data=f"active_study_go:{subject}:{lesson_num}")])
    
    # If they completed it, give them a shortcut to the end? Or let's just keep it simple.
    if current_chapter_index >= total_chapters:
        rows.append([InlineKeyboardButton(text="🗺️ عرض الخريطة الذهنية", callback_data=f"active_study_mindmap:{subject}:{lesson_num}")])
        rows.append([InlineKeyboardButton(text="📑 عرض الملخص الشامل", callback_data=f"guided_step:{subject}:{lesson_num}:summary")])
    
    rows.append([InlineKeyboardButton(text="◀️ العودة لصفحة الدرس", callback_data=f"rev_les:{subject}:{lesson_num}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_active_study_chapter_summary_keyboard(subject: str, lesson_num: int, chapter_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📝 الانتقال لسؤال المحور", callback_data=f"active_study_q:{subject}:{lesson_num}:{chapter_id}")],
        [InlineKeyboardButton(text="◀️ العودة للقائمة السابقة", callback_data=f"rev_study_path_start:{subject}:{lesson_num}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_active_study_question_keyboard(subject: str, lesson_num: int, chapter_id: int, choices: dict) -> InlineKeyboardMarkup:
    rows = []
    
    # Add choices
    for key, text in choices.items():
        if text and text.strip():
            rows.append([InlineKeyboardButton(text=f"{key.upper()}. {text}", callback_data=f"active_study_ans:{subject}:{lesson_num}:{chapter_id}:{key}")])
            
    # Add skip button
    rows.append([InlineKeyboardButton(text="⏭️ فهمت المحور (تجاوز)", callback_data=f"active_study_skip:{subject}:{lesson_num}:{chapter_id}")])
    
    # Add back button
    rows.append([InlineKeyboardButton(text="◀️ العودة للملخص", callback_data=f"active_study_resume:{subject}:{lesson_num}:{chapter_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_active_study_next_chapter_keyboard(subject: str, lesson_num: int, is_last: bool) -> InlineKeyboardMarkup:
    rows = []
    if is_last:
        rows.append([InlineKeyboardButton(text="✅ إنهاء وعرض الخريطة الذهنية", callback_data=f"active_study_mindmap:{subject}:{lesson_num}")])
    else:
        rows.append([InlineKeyboardButton(text="▶️ المحور التالي", callback_data=f"active_study_go:{subject}:{lesson_num}")])
        
    rows.append([InlineKeyboardButton(text="◀️ العودة لصفحة الدرس", callback_data=f"rev_les:{subject}:{lesson_num}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_active_study_end_keyboard(subject: str, lesson_num: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📑 عرض الملخص الشامل (Fiche Express)", callback_data=f"guided_step:{subject}:{lesson_num}:summary")],
        [InlineKeyboardButton(text="📝 الانتقال للاختبار الشامل", callback_data=f"guided_step:{subject}:{lesson_num}:quiz")],
        [InlineKeyboardButton(text="◀️ العودة لصفحة الدرس", callback_data=f"rev_les:{subject}:{lesson_num}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
''')
