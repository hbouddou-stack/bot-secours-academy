import time
import random
import logging
import re
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
import keyboards as kb

logger = logging.getLogger(__name__)
router = Router(name="quiz")


def clean_islamic_salutations(text: str) -> str:
    if not text:
        return text
    # Replace common variations of the Prophet's blessing with the ligature symbol ﷺ
    pattern = r"صلى\s+الله\s+عليه\s+(?:وآله\s+)?و?\s?سلم"
    text = re.sub(pattern, "ﷺ", text)
    text = text.replace("صلى الله عليه وسلم", "ﷺ")
    text = text.replace("صلى الله عليه و سلم", "ﷺ")
    # Render Markdown bold (**) as HTML bold (<b>)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    # Strip any remaining loose double asterisks
    text = text.replace("**", "")
    return text


SUBJECT_MAP = {
    "fiqh": "الفقه",
    "sira": "السيرة النبوية",
    "nahw": "النحو",
    "aqeeda": "العقيدة",
    "tajweed": "علم التجويد"
}

SUBJECT_TEACHERS = {
    "sira": "الشيخ ياسين العمري",
    "fiqh": "الشيخ",
    "nahw": "الشيخ",
    "aqeeda": "الشيخ",
    "tajweed": "الشيخ"
}

ARABIC_CHARS = {"a": "أ", "b": "ب", "c": "ج", "d": "د"}

DEFAULT_SETTINGS = {
    "timer": "unlimited",
    "correction": "immediate",
    "order": "sequential",
    "source": "smart",
    "origin": "official"
}

def get_default_settings(subject: str) -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if subject == "tajweed":
        settings["origin"] = "practice"
    return settings

class QuizStates(StatesGroup):
    selecting_subject = State()
    selecting_mode = State()
    selecting_lessons = State()
    selecting_themes = State()
    selecting_sub_themes = State()
    selecting_years = State()
    customizing_settings = State()
    answering = State()
    showing_results = State()
    waiting_for_report_comment = State()
    waiting_for_expl_comment = State()
    waiting_for_expl_timestamp = State()

def split_text(text: str, limit: int = 3500) -> list[str]:
    """Helper to partition a long text into chunks to avoid Telegram message length limits."""
    chunks = []
    while len(text) > limit:
        split_idx = text.rfind('\n', 0, limit)
        if split_idx == -1:
            split_idx = limit
        chunks.append(text[:split_idx])
        text = text[split_idx:]
    if text:
        chunks.append(text)
    return chunks

async def render_subject_selection(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizStates.selecting_subject)
    data = await state.get_data()
    is_continue = data.get("continue_mode", False)
    
    if is_continue:
        remaining_counts = await db.get_remaining_questions_count_per_subject(callback.from_user.id)
        text = (
            "📚 <b>مواصلة التمرين (المسار المتبقي):</b>\n"
            "يرجى تحديد المادة الدراسية لمتابعة تمرينك.\n\n"
            "⚠️ <i>الأرقام الظاهرة بين قوسين بجانب أسماء المواد تمثل <b>عدد الأسئلة المتبقية فقط</b> (الأسئلة التي لم تقم بحلها بعد أو التي أخطأت فيها سابقاً، وليس العدد الإجمالي).</i>"
        )
    else:
        remaining_counts = None
        text = "📚 <b>يرجى تحديد المادة الدراسية لبدء التمرين الجديد:</b>"
        
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_subject_list_keyboard(remaining_counts),
        parse_mode="HTML"
    )

async def render_mode_selection(callback: CallbackQuery, state: FSMContext, subject: str):
    await state.set_state(QuizStates.selecting_mode)
    subject_ar = SUBJECT_MAP.get(subject, subject)
    if subject == "sira":
        text = (
            f"🎯 <b>مادة {subject_ar}</b>\n\n"
            "يرجى اختيار طريقة تصنيف الأسئلة:\n"
            "• حسب أرقام الدروس في المنهج الدراسي\n"
            "• حسب السنوات الهجرية للأحداث\n"
            "• حسب المحاور والمواضيع الرئيسية للمادة"
        )
    else:
        text = (
            f"🎯 <b>مادة {subject_ar}</b>\n\n"
            "يرجى اختيار طريقة تصنيف الأسئلة:\n"
            "• حسب أرقام الدروس في المنهج الدراسي\n"
            "• حسب المحاور والمواضيع الرئيسية للمادة"
        )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_quiz_mode_selection_keyboard(subject),
        parse_mode="HTML"
    )

async def render_lessons_grid(callback: CallbackQuery, state: FSMContext, subject: str, selected_lessons: list[int]):
    await state.set_state(QuizStates.selecting_lessons)
    subject_ar = SUBJECT_MAP.get(subject, subject)
    user_id = callback.from_user.id
    
    # Get available lessons from DB
    available = await db.get_available_lessons(subject)
            
    if not available:
        available = list(range(14, 25))
        
    # Get user progress stats for each lesson
    dashboard = await db.get_progress_dashboard(user_id, subject)
    subject_courses = dashboard.get(subject, {})
    progress_stats = {}
    for cn, stats in subject_courses.items():
        if stats['correct'] == stats['total'] and stats['total'] > 0:
            progress_stats[cn] = "🟢"
        elif stats['correct'] > 0 or stats['wrong'] > 0:
            progress_stats[cn] = "🟡"
            
    # Check if continue mode is active
    data = await state.get_data()
    continue_mode = data.get("continue_mode", False)
    
    remaining_counts = None
    if continue_mode:
        remaining_counts = {}
        for cn, stats in subject_courses.items():
            remaining_counts[cn] = stats.get('not_done', 0) + stats.get('wrong', 0)
        
        prompt_text = "<i>حدد الدروس التي تريد مواصلة تمرينها:\n⚠️ (الرقم الظاهر بين قوسين بجانب كل درس يمثل <b>عدد الأسئلة المتبقية</b> التي لم تُتقنها بعد وليس إجمالي الأسئلة).</i>"
    else:
        prompt_text = "<i>حدد الدروس التي تريد التمرّن عليها (يمكنك اختيار درس أو أكثر):</i>"
        
    # Get newly added lessons in last 7 days
    new_added = await db.get_newly_added_lessons()
    new_lessons = [item['course_number'] for item in new_added if item['subject'] == subject]
    
    legend = (
        "<blockquote>"
        "🟢 = تم الإتقان بنسبة 100%\n"
        "🟡 = قيد المذاكرة والمراجعة\n"
        "⬜ = لم يبدأ بعد"
        "</blockquote>\n\n"
    )
    
    await callback.message.edit_text(
        f"📖 <b>مادة {subject_ar} - اختيار الدروس:</b>\n\n"
        f"{legend}"
        f"{prompt_text}",
        reply_markup=kb.get_lessons_grid_keyboard(subject, available, selected_lessons, progress_stats, remaining_counts, new_lessons),
        parse_mode="HTML"
    )

async def render_themes_grid(callback: CallbackQuery, state: FSMContext, subject: str, selected_themes: list[str]):
    await state.set_state(QuizStates.selecting_themes)
    subject_ar = SUBJECT_MAP.get(subject, subject)
    
    available_themes = None
    if subject == "sira":
        available_themes = await db.get_available_sira_themes()
    elif subject == "fiqh":
        available_themes = await db.get_available_fiqh_themes()
    elif subject == "tajweed":
        available_themes = await db.get_available_tajweed_themes()
    elif subject in ("aqeeda", "aqida"):
        available_themes = await db.get_available_aqeeda_themes()
    elif subject == "nahw":
        available_themes = await db.get_available_nahw_themes()
        
    if available_themes is not None:
        await state.update_data(available_themes=available_themes)
        
    await callback.message.edit_text(
        f"🎯 <b>مادة {subject_ar} - اختيار المحاور:</b>\n\n"
        "<i>حدد المحاور الدراسية التي تريد التمرّن عليها:</i>",
        reply_markup=kb.get_themes_grid_keyboard(subject, selected_themes, available_themes),
        parse_mode="HTML"
    )

async def render_exam_settings(callback: CallbackQuery, state: FSMContext, subject: str, mode: str, selection_text: str, settings: dict):
    await state.set_state(QuizStates.customizing_settings)
    subject_ar = SUBJECT_MAP.get(subject, subject)
    mode_ar = "حسب الدروس" if mode == "lessons" else "حسب المحاور"
    
    # Query layout settings for the current user
    user_id = callback.from_user.id
    layout = await db.get_user_settings_layout(user_id)
    ai_disabled = await db.get_setting("disable_ai_for_students", "False") == "True"
    
    source_info = "📖 <b>المصدر:</b> الأسئلة الرسمية للمنصة" if mode == "lessons" else "🎯 <b>المصدر:</b> الأسئلة المقترحة والتدريبية"
    explanation = (
        "<blockquote>"
        "ℹ️ <b>دليل أعمدة خيارات الضبط (الخيار 3 ⬅️ 1):</b>\n\n"
        "⏱️ <b>الوقت:</b>\n"
        "• 1 (15ث) | 2 (30ث) | 3 (مفتوح)\n\n"
        "💬 <b>التصحيح:</b>\n"
        "• 1 (فوري): تصحيح وتعليق فوري بعد كل سؤال.\n"
        "• 2 (النهاية): مراجعة كافة الأجوبة بعد انتهاء التمرين.\n"
        "• 3 (امتحان): وضع اختبار رسمي بدون كشف الأجوبة (النتيجة فقط).\n\n"
        "🔢 <b>العدد:</b>\n"
        "• 1 (5 أسئلة) | 2 (10 أسئلة) | 3 (20 سؤالاً)\n\n"
        "🎯 <b>الفلترة:</b>\n"
        "• 1 (الأخطاء): الأسئلة التي أخطأت فيها سابقاً فقط.\n"
        "• 2 (الذكي): يركز على الأسئلة المتبقية غير المتقنة.\n"
        "• 3 (الكل): يطرح كامل بنك الأسئلة دون تصفية."
        "</blockquote>"
    )
    
    text = (
        f"⚙️ <b>إعدادات التمرين - {subject_ar} ({mode_ar})</b>\n\n"
        f"📌 <b>المحدد:</b> {selection_text}\n"
        f"{source_info}\n\n"
        f"{explanation}\n\n"
        "اضغط على الأزرار أدناه لتعديل خيارات التمرين قبل البدء:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_exam_settings_keyboard(settings, layout=layout, ai_disabled=ai_disabled),
        parse_mode="HTML"
    )

async def show_question(callback: CallbackQuery, state: FSMContext):
    """Render the current question to the student."""
    data = await state.get_data()
    questions = data.get("questions")
    current_index = data.get("current_index")
    settings = data.get("settings", DEFAULT_SETTINGS)
    
    if current_index >= len(questions):
        await finish_quiz(callback, state)
        return
        
    q = questions[current_index]
    
    # Store starting time
    await state.update_data(q_start_time=time.time())
    
    # Handle Choice Shuffling
    orig_choices = [
        ("a", q.get("choice_a")),
        ("b", q.get("choice_b")),
        ("c", q.get("choice_c")),
        ("d", q.get("choice_d"))
    ]
    active_choices = [item for item in orig_choices if item[1] and item[1].strip()]
    correct_choice_orig = db.get_correct_choice_letter(q)
    
    c_order = settings.get("order", "random")
    if c_order == "random":
        random.shuffle(active_choices)
        
    shuffled_choices = {}
    new_correct = None
    keys_list = ["a", "b", "c", "d"]
    for idx, item in enumerate(active_choices):
        new_key = keys_list[idx]
        shuffled_choices[new_key] = item[1]
        if item[0] == correct_choice_orig:
            new_correct = new_key
            
    await state.update_data(current_correct_answer=new_correct, current_active_choices=shuffled_choices)
    
    # Smart choices layout check: True if any choice is longer than 25 chars
    force_letters = any(len(v.strip()) > 25 for v in shuffled_choices.values())
    
    subject_ar = SUBJECT_MAP.get(q.get("subject", "").lower(), q.get("subject"))
    progress_ratio = current_index / len(questions)
    filled = int(progress_ratio * 10)
    progress_bar = "🟢" * filled + "⚪" * (10 - filled)
    
    question_clean = clean_islamic_salutations((q.get('question') or '').strip())
    text = f"❓ <b>{question_clean}</b>\n\n"
    
    # Choices text is always shown in message body
    for k, v in shuffled_choices.items():
        cleaned_choice = clean_islamic_salutations(v.strip())
        text += f"<blockquote><b>{ARABIC_CHARS[k]})</b> {cleaned_choice}</blockquote>\n"
        
    timer_val = settings.get("timer", "unlimited")
    if timer_val != "unlimited":
        if timer_val == "15s":
            sec = 15
        elif timer_val == "30s":
            sec = 30
        else:
            sec = 60
        text += f"\n⏱️ <i>لديك {sec} ثانية للإجابة!</i>\n"
        
    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    session_mastered = data.get("session_mastered", 0)
    mastered_str = f" | 🏅 \u202b{session_mastered} مُتقَن\u202c" if session_mastered > 0 else ""
    theme_str = f"\n📚 <b>المحور:</b> {q.get('theme')}" if q.get("subject") == "sira" and q.get("theme") else ""
    text += (
        f"📝 <b>السؤال {current_index + 1} من {len(questions)}</b> | <b>الدرس {q.get('course_number')}</b> ({subject_ar}){mastered_str}{theme_str}\n"
        f"📊 {progress_bar} {int(progress_ratio * 100)}%"
    )
        
    from handlers.start import is_admin
    user_id = callback.from_user.id
    is_fav = await db.is_favorite(user_id, q["id"])
    reply_markup = kb.get_answer_keyboard(
        shuffled_choices,
        force_letters=force_letters,
        is_fav=is_fav,
        question_id=q["id"],
        question_text=q.get("question"),
        is_admin=is_admin(user_id)
    )
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

# --- Setup Flow Handlers ---

@router.callback_query(QuizStates.selecting_subject, F.data.startswith("sel_sub:"))
async def handle_subject_selected(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":")[1]
    await state.update_data(subject=subject)
    
    data = await state.get_data()
    preselected_lesson = data.get("preselected_lesson")
    
    if preselected_lesson:
        # Directly set mode to lessons and select it
        await state.update_data(
            mode="lessons",
            selected_lessons=[preselected_lesson],
            selected_themes=[],
            settings=DEFAULT_SETTINGS.copy()
        )
        # Clear preselected lesson so subsequent flow is normal
        await state.update_data(preselected_lesson=None)
        
        # Go straight to settings page
        selection_text = f"الدرس {preselected_lesson}"
        await render_exam_settings(callback, state, subject, "lessons", selection_text, DEFAULT_SETTINGS)
    else:
        # Normal flow: ask for mode (lessons vs themes)
        await render_mode_selection(callback, state, subject)
    await callback.answer()


@router.callback_query(QuizStates.selecting_subject, F.data == "quiz_cancel")
async def handle_quiz_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    await callback.message.edit_text(
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة التمارين والمسار التعليمي:",
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(QuizStates.selecting_mode, F.data.startswith("sel_mode:"))
async def handle_mode_selected(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await state.update_data(mode=mode)
    
    data = await state.get_data()
    subject = data.get("subject")
    
    if mode == "lessons":
        await state.update_data(selected_lessons=[])
        await render_lessons_grid(callback, state, subject, [])
    elif mode == "years":
        await state.update_data(selected_years=[])
        await render_years_grid(callback, state, [])
    elif mode == "themes":
        await state.update_data(selected_themes=[])
        await render_themes_grid(callback, state, subject, [])
    await callback.answer()

@router.callback_query(QuizStates.selecting_mode, F.data == "mode_back")
async def handle_mode_back(callback: CallbackQuery, state: FSMContext):
    await render_subject_selection(callback, state)
    await callback.answer()

@router.callback_query(QuizStates.selecting_lessons, F.data.startswith("tog_les:"))
async def handle_toggle_lesson(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    lesson = int(callback.data.split(":")[1])
    data = await state.get_data()
    subject = data.get("subject")
    selected = data.get("selected_lessons", [])
    
    if lesson in selected:
        selected.remove(lesson)
    else:
        selected.append(lesson)
        
    await state.update_data(selected_lessons=selected)
    await render_lessons_grid(callback, state, subject, selected)

@router.callback_query(QuizStates.selecting_lessons, F.data.startswith("les_act:"))
async def handle_lessons_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    data = await state.get_data()
    subject = data.get("subject")
    
    if action == "all":
        # Fetch all available lessons for subject from DB
        available = await db.get_available_lessons(subject)
        if not available:
            available = list(range(14, 25))
        await state.update_data(selected_lessons=available)
        await render_lessons_grid(callback, state, subject, available)
    elif action == "none":
        await state.update_data(selected_lessons=[])
        await render_lessons_grid(callback, state, subject, [])
    await callback.answer()

@router.callback_query(QuizStates.selecting_lessons, F.data == "les_confirm")
async def handle_lessons_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    selected = data.get("selected_lessons", [])
    
    if not selected:
        await callback.answer("⚠️ يرجى اختيار درس واحد على الأقل للبدء!", show_alert=True)
        return
        
    settings = data.get("settings", get_default_settings(subject))
    await state.update_data(settings=settings)
    
    sorted_selected = sorted(selected)
    selection_text = ", ".join(f"الدرس {l}" for l in sorted_selected)
    await render_exam_settings(callback, state, subject, "lessons", selection_text, settings)
    await callback.answer()

@router.callback_query(QuizStates.selecting_lessons, F.data == "les_back")
async def handle_lessons_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    await render_mode_selection(callback, state, subject)
    await callback.answer()

@router.callback_query(QuizStates.selecting_themes, F.data.startswith("select_th:"))
async def handle_select_theme(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    theme_val = callback.data.split(":")[1]
    data = await state.get_data()
    subject = data.get("subject")
    
    if theme_val.isdigit():
        available_themes = data.get("available_themes", [])
        idx = int(theme_val)
        if 0 <= idx < len(available_themes):
            theme = available_themes[idx]
        else:
            await callback.message.answer("⚠️ حدث خطأ في اختيار المحور.")
            return
    else:
        theme = theme_val
        
    # Store selected theme and reset sub-themes selection
    await state.update_data(selected_theme=theme, selected_sub_themes=[])
    
    if subject in ["fiqh", "sira"]:
        settings = data.get("settings", get_default_settings(subject))
        await state.update_data(settings=settings, selected_themes=[theme])
        await render_exam_settings(callback, state, subject, "themes", theme, settings)
    else:
        await render_sub_themes_grid(callback, state, subject, theme, [])

async def render_sub_themes_grid(callback: CallbackQuery, state: FSMContext, subject: str, theme: str, selected_sub_themes: list[str]):
    await state.set_state(QuizStates.selecting_sub_themes)
    subject_ar = SUBJECT_MAP.get(subject, subject)
    
    # Get main theme label in Arabic
    if subject in ["fiqh", "sira", "tajweed"]:
        theme_label = theme
    else:
        from keyboards import THEMES
        theme_label = THEMES.get(subject, {}).get(theme, {}).get("label", theme)
        
    available_sub_themes = await db.get_available_sub_themes(subject, theme)
    
    text = (
        f"🎯 <b>مادة {subject_ar} - {theme_label}</b>\n\n"
        "<i>حدد المحاور الفرعية (الأحكام الدقيقة) التي تريد التمرّن عليها:</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_sub_themes_grid_keyboard(subject, selected_sub_themes, available_sub_themes),
        parse_mode="HTML"
    )

@router.callback_query(QuizStates.selecting_sub_themes, F.data.startswith("tog_subth:"))
async def handle_toggle_sub_theme(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    subth_val = callback.data.split(":")[1]
    data = await state.get_data()
    
    if subth_val.isdigit():
        available_sub_themes = data.get("available_sub_themes", [])
        idx = int(subth_val)
        if 0 <= idx < len(available_sub_themes):
            subth = available_sub_themes[idx]
        else:
            await callback.message.answer("⚠️ حدث خطأ.")
            return
    else:
        subth = subth_val
        
    subject = data.get("subject")
    theme = data.get("selected_theme")
    selected = data.get("selected_sub_themes", [])
    
    if subth in selected:
        selected.remove(subth)
    else:
        selected.append(subth)
        
    await state.update_data(selected_sub_themes=selected)
    await render_sub_themes_grid(callback, state, subject, theme, selected)

@router.callback_query(QuizStates.selecting_sub_themes, F.data == "subth_all")
async def handle_sub_themes_all(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    subject = data.get("subject")
    theme = data.get("selected_theme")
    available_sub_themes = await db.get_available_sub_themes(subject, theme)
    
    await state.update_data(selected_sub_themes=available_sub_themes)
    await render_sub_themes_grid(callback, state, subject, theme, available_sub_themes)

@router.callback_query(QuizStates.selecting_sub_themes, F.data == "subth_none")
async def handle_sub_themes_none(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    subject = data.get("subject")
    theme = data.get("selected_theme")
    
    await state.update_data(selected_sub_themes=[])
    await render_sub_themes_grid(callback, state, subject, theme, [])

@router.callback_query(QuizStates.selecting_sub_themes, F.data == "subth_back")
async def handle_sub_themes_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    subject = data.get("subject")
    selected_themes = data.get("selected_themes", [])
    await render_themes_grid(callback, state, subject, selected_themes)

@router.callback_query(QuizStates.selecting_sub_themes, F.data == "subth_confirm")
async def handle_sub_themes_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    theme = data.get("selected_theme")
    selected = data.get("selected_sub_themes", [])
    
    available = await db.get_available_sub_themes(subject, theme)
    if available and not selected:
        await callback.answer("⚠️ يرجى اختيار محور فرعي واحد على الأقل للبدء!", show_alert=True)
        return
        
    settings = data.get("settings", get_default_settings(subject))
    await state.update_data(settings=settings, selected_themes=[theme])
    
    # Format selection description
    if subject in ["fiqh", "sira", "tajweed"]:
        theme_label = theme
    else:
        from keyboards import THEMES
        theme_label = THEMES.get(subject, {}).get(theme, {}).get("label", theme)
        
    if selected:
        if len(selected) > 3:
            subth_desc = f"{theme_label} ({len(selected)} محاور)"
        else:
            subth_desc = f"{theme_label} - " + ", ".join(selected)
    else:
        subth_desc = theme_label
        
    await render_exam_settings(callback, state, subject, "themes", subth_desc, settings)
    await callback.answer()

@router.callback_query(QuizStates.selecting_themes, F.data == "th_back")
async def handle_themes_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    await render_mode_selection(callback, state, subject)
    await callback.answer()

# --- Hijri Years Handlers ---

async def render_years_grid(callback: CallbackQuery, state: FSMContext, selected_years: list[int]):
    await state.set_state(QuizStates.selecting_years)
    await callback.message.edit_text(
        "📅 <b>السيرة النبوية - اختيار السنوات الهجرية:</b>\n\n"
        "<i>حدد السنوات التي تريد الاختبار فيها:</i>",
        reply_markup=kb.get_years_grid_keyboard(selected_years),
        parse_mode="HTML"
    )

@router.callback_query(QuizStates.selecting_years, F.data.startswith("tog_yr:"))
async def handle_toggle_year(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    year = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = data.get("selected_years", [])
    
    if year in selected:
        selected.remove(year)
    else:
        selected.append(year)
        
    await state.update_data(selected_years=selected)
    await render_years_grid(callback, state, selected)

@router.callback_query(QuizStates.selecting_years, F.data.startswith("yr_act:"))
async def handle_years_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    
    if action == "all":
        available = list(range(1, 12))
        await state.update_data(selected_years=available)
        await render_years_grid(callback, state, available)
    elif action == "none":
        await state.update_data(selected_years=[])
        await render_years_grid(callback, state, [])
    await callback.answer()

@router.callback_query(QuizStates.selecting_years, F.data == "yr_confirm")
async def handle_years_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    selected = data.get("selected_years", [])
    
    if not selected:
        await callback.answer("⚠️ يرجى اختيار سنة واحدة على الأقل للبدء!", show_alert=True)
        return
        
    settings = data.get("settings", DEFAULT_SETTINGS.copy())
    await state.update_data(settings=settings)
    
    sorted_selected = sorted(selected)
    selection_text = ", ".join(f"{y} هـ" for y in sorted_selected)
    await render_exam_settings(callback, state, subject, "years", selection_text, settings)
    await callback.answer()

@router.callback_query(QuizStates.selecting_years, F.data == "yr_back")
async def handle_years_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    await render_mode_selection(callback, state, subject)
    await callback.answer()

@router.callback_query(QuizStates.customizing_settings, F.data.startswith("set_tog:"))
async def handle_setting_toggle(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    key = callback.data.split(":")[1]
    data = await state.get_data()
    subject = data.get("subject")
    mode = data.get("mode")
    selected_lessons = data.get("selected_lessons", [])
    selected_themes = data.get("selected_themes", [])
    selected_years = data.get("selected_years", [])
    settings = data.get("settings", DEFAULT_SETTINGS.copy())
    
    if key == "timer":
        cycle = ["unlimited", "30s", "60s"]
        current = settings.get("timer", "unlimited")
        settings["timer"] = cycle[(cycle.index(current) + 1) % len(cycle)]
    elif key == "correction":
        cycle = ["immediate", "end"]
        current = settings.get("correction", "immediate")
        settings["correction"] = cycle[(cycle.index(current) + 1) % len(cycle)]
    elif key == "order":
        cycle = ["random", "sequential"]
        current = settings.get("order", "random")
        settings["order"] = cycle[(cycle.index(current) + 1) % len(cycle)]
    elif key == "source":
        cycle = ["smart", "errors", "all"]
        current = settings.get("source", "smart")
        if current not in cycle:
            current = "smart"
        settings["source"] = cycle[(cycle.index(current) + 1) % len(cycle)]
    elif key == "origin":
        cycle = ["official", "practice", "all"]
        current = settings.get("origin", "official")
        if current not in cycle:
            current = "official"
        settings["origin"] = cycle[(cycle.index(current) + 1) % len(cycle)]
        
    await state.update_data(settings=settings)
    
    if mode == "lessons":
        selection_text = ", ".join(f"الدرس {l}" for l in sorted(selected_lessons))
    elif mode == "years":
        selection_text = ", ".join(f"{y} هـ" for y in sorted(selected_years))
    else:
        if subject == "sira":
            selection_text = ", ".join(selected_themes)
        else:
            from keyboards import THEMES
            theme_labels = [THEMES[subject][t]["label"] for t in selected_themes if t in THEMES.get(subject, {})]
            selection_text = ", ".join(theme_labels)
        
    await render_exam_settings(callback, state, subject, mode, selection_text, settings)



@router.callback_query(QuizStates.customizing_settings, F.data.startswith("set_val:"))
async def handle_setting_value(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    key = parts[1]
    value = parts[2]
    
    data = await state.get_data()
    subject = data.get("subject")
    mode = data.get("mode")
    selected_lessons = data.get("selected_lessons", [])
    selected_themes = data.get("selected_themes", [])
    selected_years = data.get("selected_years", [])
    settings = data.get("settings", DEFAULT_SETTINGS.copy())
    
    if key == "limit":
        settings[key] = int(value)
    else:
        settings[key] = value
        
    await state.update_data(settings=settings)
    
    if mode == "lessons":
        selection_text = ", ".join(f"الدرس {l}" for l in sorted(selected_lessons))
    elif mode == "years":
        selection_text = ", ".join(f"{y} هـ" for y in sorted(selected_years))
    else:
        selection_text = data.get("selected_theme", "غير محدد")
        
    await render_exam_settings(callback, state, subject, mode, selection_text, settings)

@router.callback_query(QuizStates.customizing_settings, F.data == "settings_back")
async def handle_settings_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    mode = data.get("mode")
    
    if mode == "lessons":
        selected = data.get("selected_lessons", [])
        await render_lessons_grid(callback, state, subject, selected)
    elif mode == "years":
        selected = data.get("selected_years", [])
        await render_years_grid(callback, state, selected)
    else:
        selected = data.get("selected_themes", [])
        await render_themes_grid(callback, state, subject, selected)
    await callback.answer()

async def initialize_and_start_quiz(callback: CallbackQuery, state: FSMContext, data: dict):
    subject = data.get("subject")
    mode = data.get("mode")
    selected_lessons = data.get("selected_lessons", [])
    selected_themes = data.get("selected_themes", [])
    selected_years = data.get("selected_years", [])
    settings = data.get("settings", get_default_settings(subject))
    
    ai_disabled = await db.get_setting("disable_ai_for_students", "False") == "True"
    if ai_disabled and subject != "tajweed":
        settings["origin"] = "official"
    
    if subject == "sira" and mode == "years":
        questions = await db.get_questions_for_sira_years(selected_years)
    elif mode == "themes":
        questions = await db.get_questions_for_themes(subject, selected_themes)
    else:
        course_numbers = selected_lessons
        questions = await db.get_questions_for_subject_courses(subject, course_numbers)
        
    # Apply filtering based on sub-themes (if in themes mode)
    if mode == "themes" and questions:
        selected_sub_themes = data.get("selected_sub_themes", [])
        if selected_sub_themes:
            questions = [q for q in questions if q.get("sub_theme") in selected_sub_themes]
            
    # Force origin: lessons -> official only, themes -> practice/training only
    origin_val = "practice" if mode == "themes" else "official"
    if origin_val == "official" and questions:
        # Platform/Official questions: source in ['official', None, '']
        questions = [q for q in questions if q.get("source") in ["official", None, ""]]
    elif origin_val == "practice" and questions:
        # Practice/Proposed questions: source in ['generated_by_gemini', 'student_proposal', 'ai']
        questions = [q for q in questions if q.get("source") in ["generated_by_gemini", "student_proposal", "ai"]]
        
    # Exclude questions reported by this user
    user_id = callback.from_user.id
    reported_ids = await db.get_user_reported_question_ids(user_id)
    if reported_ids and questions:
        questions = [q for q in questions if q["id"] not in reported_ids]
        
    # Apply continue_mode filter (only keep not_done or wrong questions)
    continue_mode = data.get("continue_mode", False)
    if continue_mode and questions:
        not_done_questions = await db.get_not_done_questions(user_id, subject)
        not_done_ids = {q["id"] for q in not_done_questions}
        questions = [q for q in questions if q["id"] in not_done_ids]
        
    if not questions:
        if continue_mode:
            await callback.message.answer("⚠️ لا توجد أسئلة متبقية للمذاكرة في هذا المحدد (جميعها مُتقنة). يمكنك اختيار دروس أخرى لمواصلة المذاكرة.")
        else:
            await callback.message.answer("⚠️ عذراً، لا توجد أسئلة متوفرة للمحدد حالياً.")
        return
        
    # Apply filtering based on source
    source_val = settings.get("source", "smart")
    if source_val == "smart" and questions:
        correct_ids = await db.get_user_correct_question_ids(user_id)
        questions = [q for q in questions if q["id"] not in correct_ids]
        if not questions:
            await callback.answer("⚠️ لا توجد أسئلة غير مجاب عليها أو أخطاء متبقية في هذا المحدد حالياً.", show_alert=True)
            return
    elif source_val == "errors" and questions:
        user_errors = await db.get_user_errors(user_id)
        questions = [q for q in questions if q["id"] in user_errors]
        if not questions:
            await callback.answer("⚠️ ليس لديك أي أخطاء مسجلة في هذا المحدد حالياً.", show_alert=True)
            return


    if settings.get("order", "random") == "random":
        random.shuffle(questions)
        
    limit = int(settings.get("limit", 10))
    questions = questions[:limit]
    
    await state.set_state(QuizStates.answering)
    await state.update_data(
        questions=questions,
        current_index=0,
        answers={},
        times={},
        results={},
        continue_mode=False
    )
    
    await show_question(callback, state)

@router.callback_query(QuizStates.customizing_settings, F.data == "settings_start")
async def handle_settings_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.answer("⏳ جاري تحضير الأسئلة...")
    await initialize_and_start_quiz(callback, state, data)

async def render_question_correction(callback: CallbackQuery, state: FSMContext, index: int):
    """Render the correction screen for an already answered question."""
    data = await state.get_data()
    questions = data.get("questions")
    results = data.get("results", {})
    
    if index < 0 or index >= len(questions):
        return
        
    q = questions[index]
    res = results.get(str(index))
    if not res:
        return
        
    is_correct = res["is_correct"]
    choice = res["choice"]
    correct_choice = res["correct_choice"]
    is_timeout = res.get("is_timeout", False)
    active_choices = res["active_choices"]
    
    subject_ar = SUBJECT_MAP.get(q.get("subject", "").lower(), q.get("subject"))
    
    # Progress bar (based on index + 1 since this question is completed)
    progress_ratio = (index + 1) / len(questions)
    filled = int(progress_ratio * 10)
    progress_bar = "🟢" * filled + "⚪" * (10 - filled)
    
    question_clean = clean_islamic_salutations((q.get('question') or '').strip())
    text = f"❓ <b>{question_clean}</b>\n\n"
    
    for k, v in active_choices.items():
        v_clean = clean_islamic_salutations(v.strip())
        if k == correct_choice:
            text += f"<blockquote><b>{ARABIC_CHARS[k]}) {v_clean}</b> (✅ الإجابة الصحيحة)</blockquote>\n"
        elif k == choice and not is_correct:
            text += f"<blockquote><s>{ARABIC_CHARS[k]}) {v_clean}</s> (❌ إجابتك)</blockquote>\n"
        else:
            text += f"<blockquote>{ARABIC_CHARS[k]}) {v_clean}</blockquote>\n"
            
    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    if is_timeout:
        text += "⌛ <b>انتهى الوقت! (تجاوزت حد الوقت المسموح)</b>\n\n"
    elif is_correct:
        text += "✅ <b>إجابة صحيحة! أحسنت.</b>\n\n"
    else:
        text += f"❌ <b>إجابة خاطئة.</b>\n\n"
        
    theme_str = f"\n📚 <b>المحور:</b> {q.get('theme')}" if q.get("subject") == "sira" and q.get("theme") else ""
    text += (
        f"📝 <b>السؤال {index + 1} من {len(questions)}</b> | <b>الدرس {q.get('course_number')}</b> ({subject_ar}){theme_str}\n"
        f"📊 {progress_bar} {int(progress_ratio * 100)}%"
    )
        
    user_id = callback.from_user.id
    is_fav = await db.is_favorite(user_id, q["id"])
    is_last = (index + 1 >= len(questions))
    has_expl = bool(q.get("explanation"))
    has_prev = index > 0
    
    map_pages = await db.get_mind_map_pages(q["subject"], q["course_number"])
    has_map = len(map_pages) > 0
    
    # Set current index in state to the browsed index
    await state.update_data(current_index=index)
    
    from handlers.start import is_admin
    reply_markup = kb.get_feedback_keyboard(
        q["id"], 
        is_fav, 
        is_last, 
        has_explanation=has_expl, 
        has_prev=has_prev,
        is_admin=is_admin(user_id),
        has_mind_map=has_map
    )
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

# --- Answering Phase Handlers ---

@router.callback_query(QuizStates.answering, F.data.startswith("ans:"))
async def handle_answer_callback(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    
    data = await state.get_data()
    questions = data.get("questions")
    current_index = data.get("current_index")
    settings = data.get("settings", DEFAULT_SETTINGS)
    q_start_time = data.get("q_start_time", time.time())
    answers = data.get("answers", {})
    times = data.get("times", {})
    results = data.get("results", {})
    correct_choice = data.get("current_correct_answer")
    active_choices = data.get("current_active_choices", {})
    
    if str(current_index) in answers:
        await callback.answer("لقد أجبت على هذا السؤال بالفعل.")
        return
        
    elapsed = time.time() - q_start_time
    timer_val = settings.get("timer", "unlimited")
    limit = 15.0 if timer_val == "15s" else (30.0 if timer_val == "30s" else (60.0 if timer_val == "60s" else None))
    is_timeout = (limit is not None and elapsed > limit + 2.0)
    
    q = questions[current_index]
    is_correct = (choice == correct_choice) and not is_timeout
    
    user_id = callback.from_user.id
    
    await db.log_quiz_answer(user_id, q["id"], is_correct)
    # Track mastery progress
    await db.update_question_progress(user_id, q["id"], is_correct)
    
    if is_correct:
        await db.remove_error(user_id, q["id"])
        # Increment session mastered counter for live display
        session_mastered = data.get("session_mastered", 0) + 1
        await state.update_data(session_mastered=session_mastered)
    else:
        wrong_val = "timeout" if is_timeout else choice
        await db.add_error(user_id, q["id"], q["subject"], wrong_val)

        
    answers[str(current_index)] = "timeout" if is_timeout else choice
    times[str(current_index)] = elapsed
    results[str(current_index)] = {
        "is_correct": is_correct,
        "choice": choice,
        "correct_choice": correct_choice,
        "elapsed": elapsed,
        "is_timeout": is_timeout,
        "active_choices": active_choices
    }
    
    await state.update_data(answers=answers, times=times, results=results)
    
    correction_val = settings.get("correction", "immediate")
    if correction_val == "immediate":
        await callback.answer()
        await render_question_correction(callback, state, current_index)
    else:
        if is_timeout:
            await callback.answer("⌛ انتهى الوقت!", show_alert=True)
        else:
            await callback.answer()
            
        next_idx = current_index + 1
        if next_idx < len(questions):
            await state.update_data(current_index=next_idx)
            await show_question(callback, state)
        else:
            await finish_quiz(callback, state)

@router.callback_query(QuizStates.answering, F.data.startswith("fav_add:"))
async def handle_fav_add(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split(":")[1])
    q = await db.get_question_by_id(q_id)
    if q:
        await db.add_favorite(callback.from_user.id, q_id, q["subject"])
        await callback.answer("⭐ تمت الإضافة للمفضلة")
        data = await state.get_data()
        current_index = data.get("current_index", 0)
        has_prev = current_index > 0
        is_last = any(btn.callback_data == "quiz_finish" for btn in callback.message.reply_markup.inline_keyboard[0])
        has_expl = bool(q.get("explanation"))
        
        map_pages = await db.get_mind_map_pages(q["subject"], q["course_number"])
        has_map = len(map_pages) > 0
        
        from handlers.start import is_admin
        await callback.message.edit_reply_markup(
            reply_markup=kb.get_feedback_keyboard(q_id, is_fav=True, is_last=is_last, has_explanation=has_expl, has_prev=has_prev, is_admin=is_admin(callback.from_user.id), has_mind_map=has_map)
        )

@router.callback_query(QuizStates.answering, F.data.startswith("fav_rem:"))
async def handle_fav_rem(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split(":")[1])
    await db.remove_favorite(callback.from_user.id, q_id)
    await callback.answer("🗑️ تم الحذف من المفضلة")
    data = await state.get_data()
    current_index = data.get("current_index", 0)
    has_prev = current_index > 0
    is_last = any(btn.callback_data == "quiz_finish" for btn in callback.message.reply_markup.inline_keyboard[0])
    q = await db.get_question_by_id(q_id)
    has_expl = bool(q.get("explanation")) if q else False
    
    has_map = False
    if q:
        map_pages_chk = await db.get_mind_map_pages(q["subject"], q["course_number"])
        has_map = len(map_pages_chk) > 0
        
    from handlers.start import is_admin
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_feedback_keyboard(q_id, is_fav=False, is_last=is_last, has_explanation=has_expl, has_prev=has_prev, is_admin=is_admin(callback.from_user.id), has_mind_map=has_map)
    )

@router.callback_query(QuizStates.answering, F.data.startswith("fav_q_add:"))
async def handle_fav_q_add(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split(":")[1])
    q = await db.get_question_by_id(q_id)
    if q:
        await db.add_favorite(callback.from_user.id, q_id, q["subject"])
        await callback.answer("⭐ تمت الإضافة للمفضلة")
        
        from handlers.start import is_admin
        data = await state.get_data()
        current_active_choices = data.get("current_active_choices", {})
        force_letters = any(len(v.strip()) > 25 for v in current_active_choices.values())
        await callback.message.edit_reply_markup(
            reply_markup=kb.get_answer_keyboard(current_active_choices, force_letters=force_letters, is_fav=True, question_id=q_id, question_text=q.get("question"), is_admin=is_admin(callback.from_user.id))
        )

@router.callback_query(QuizStates.answering, F.data.startswith("fav_q_rem:"))
async def handle_fav_q_rem(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split(":")[1])
    await db.remove_favorite(callback.from_user.id, q_id)
    await callback.answer("🗑️ تم الحذف من المفضلة")
    
    from handlers.start import is_admin
    data = await state.get_data()
    current_active_choices = data.get("current_active_choices", {})
    force_letters = any(len(v.strip()) > 25 for v in current_active_choices.values())
    
    q = await db.get_question_by_id(q_id)
    question_text = q.get("question") if q else None
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_answer_keyboard(current_active_choices, force_letters=force_letters, is_fav=False, question_id=q_id, question_text=question_text, is_admin=is_admin(callback.from_user.id))
    )

def split_explanation(explanation_text: str):
    import re
    if not explanation_text:
        return "", "", ""
        
    text = explanation_text.strip()
    
    # 1. Split into paragraphs/blocks by looking at double newlines
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    
    pedagogical_blocks = []
    citation_blocks = []
    source_blocks = []
    
    # Check if there is ANY citation marker or pedagogical marker in the entire text
    has_any_cit_marker = False
    has_any_ped_marker = False
    
    cit_markers = ["📖", "قول الشيخ", "الشيخ ياسين"]
    ped_markers = ["💡", "التفسير التربوي"]
    
    for m in cit_markers:
        if m in text:
            has_any_cit_marker = True
            break
            
    for m in ped_markers:
        if m in text:
            has_any_ped_marker = True
            break
            
    if not has_any_cit_marker and not has_any_ped_marker:
        return "", text, ""
        
    for block in blocks:
        is_src = False
        if block.startswith("📍") or "المصدر" in block[:40]:
            is_src = True
            
        if is_src:
            source_blocks.append(block)
            continue
            
        is_cit = False
        if block.startswith("📖") or "📖" in block[:15] or block.startswith("قول الشيخ") or "قول الشيخ" in block[:20]:
            is_cit = True
        elif "الشيخ ياسين" in block[:40] and ("يقول" in block[:60] or "العمري" in block[:50]):
            is_cit = True
            
        if is_cit:
            citation_blocks.append(block)
        else:
            pedagogical_blocks.append(block)
            
    pedagogical = "\n\n".join(pedagogical_blocks)
    citation = "\n\n".join(citation_blocks)
    source = "\n\n".join(source_blocks)
    
    # Clean pedagogical headers
    ped_prefixes = [
        r'^💡\s*',
        r'^<b>\s*(\d+\.)?\s*💡?\s*التفسير\s+التربوي\s*(:|：)?\s*</b>\s*(:|：)?\s*',
        r'^(\d+\.)?\s*💡?\s*التفسير\s+التربوي\s*(:|：)?\s*',
        r'^:\s*'
    ]
    for rx in ped_prefixes:
        pedagogical = re.sub(rx, '', pedagogical, flags=re.IGNORECASE).strip()
    pedagogical = pedagogical.replace("<blockquote>", "").replace("</blockquote>", "").strip()
    
    # Clean citation headers
    cit_prefixes = [
        r'^📖\s*',
        r'^<b>\s*(\d+\.)?\s*📖?\s*قول\s+الشيخ\s*(:|：)?\s*</b>\s*(:|：)?\s*',
        r'^<b>\s*(\d+\.)?\s*📖?\s*الشيخ\s+ياسين\s+العمري\s+يقول\s*(:|：)?\s*</b>\s*(:|：)?\s*',
        r'^<b>\s*(\d+\.)?\s*📖?\s*الشيخ\s+ياسين\s+العمري\s*</b>\s*(:|：)?\s*',
        r'^<b>\s*(\d+\.)?\s*📖?\s*الشيخ\s+ياسين\s*(:|：)?\s*</b>\s*(:|：)?\s*',
        r'^(\d+\.)?\s*📖?\s*قول\s+الشيخ\s*(:|：)?\s*',
        r'^(\d+\.)?\s*📖?\s*الشيخ\s+ياسين\s+العمري\s+يقول\s*(:|：)?\s*',
        r'^(\d+\.)?\s*📖?\s*الشيخ\s+ياسين\s*(:|：)?\s*',
        r'^:\s*'
    ]
    for rx in cit_prefixes:
        citation = re.sub(rx, '', citation, flags=re.IGNORECASE).strip()
    citation = citation.replace("<blockquote>", "").replace("</blockquote>", "").strip()
    
    # Clean source headers
    src_prefixes = [
        r'^📍\s*',
        r'^<b>\s*المصدر\s*(:|：)?\s*</b>\s*(:|：)?\s*',
        r'^المصدر\s*(:|：)?\s*',
        r'^:\s*'
    ]
    for rx in src_prefixes:
        source = re.sub(rx, '', source, flags=re.IGNORECASE).strip()
    source = source.replace("<blockquote>", "").replace("</blockquote>", "").strip()
    
    # Balance HTML tags
    def balance_html_tags(html_str: str) -> str:
        if not html_str:
            return ""
        b_open = html_str.count("<b>")
        b_close = html_str.count("</b>")
        if b_open > b_close:
            html_str = html_str + "</b>" * (b_open - b_close)
        elif b_close > b_open:
            html_str = "<b>" * (b_close - b_open) + html_str
            
        i_open = html_str.count("<i>")
        i_close = html_str.count("</i>")
        if i_open > i_close:
            html_str = html_str + "</i>" * (i_open - i_close)
        elif i_close > i_open:
            html_str = "<i>" * (i_close - i_open) + html_str
            
        a_open = html_str.count("<a ") + html_str.count("<a\n")
        a_close = html_str.count("</a>")
        if a_open > a_close:
            html_str = html_str + "</a>" * (a_open - a_close)
        elif a_close > a_open:
            html_str = "<a>" * (a_close - a_open) + html_str
            
        return html_str

    pedagogical = balance_html_tags(pedagogical)
    citation = balance_html_tags(citation)
    source = balance_html_tags(source)
    
    return pedagogical, citation, source


@router.callback_query(F.data.startswith("prof_quote:"))
async def handle_prof_quote(callback: CallbackQuery, state: FSMContext):
    """Show professor's transcript explanation in the same message, with a back button."""
    q_id = int(callback.data.split(":")[1])
    q = await db.get_question_by_id(q_id)
    
    if not q or not q.get("explanation"):
        await callback.answer("لا يوجد شرح متاح لهذا السؤال.", show_alert=True)
        return
    
    await callback.answer()
    
    # Format message text
    question_text = clean_islamic_salutations(q.get("question", ""))
    qa_block = f"❓ <b>السؤال :</b>\n<blockquote>{question_text}</blockquote>"
    
    explanation = q.get("explanation", "").strip()
    pedagogical, citation, source = split_explanation(explanation)
    
    subject = q.get("subject", "sira")
    teacher = SUBJECT_TEACHERS.get(subject, "الشيخ")
    
    import re
    parts_list = []
    if pedagogical:
        pedago_clean = clean_islamic_salutations(pedagogical.replace("<blockquote>", "").replace("</blockquote>", "").strip())
        parts_list.append(f"💡 <b>التفسير التربوي :</b>\n<blockquote>\u200f{pedago_clean}</blockquote>")
    if citation:
        cit_clean = clean_islamic_salutations(citation.replace("<blockquote>", "").replace("</blockquote>", "").strip())
        parts_list.append(f"📖 <b>{teacher} يقول :</b>\n<blockquote>\u200f{cit_clean}</blockquote>")
    if source:
        source_clean = clean_islamic_salutations(source.replace("<blockquote>", "").replace("</blockquote>", "").strip())
        import re
        # Remove any existing variations of the hint
        source_clean = re.sub(r'<\s*i\s*>\s*\(اضغط على التوقيت للانتقال لشرح الفيديو 🎥\)\s*<\s*/i\s*>', '', source_clean)
        source_clean = re.sub(r'\s*\(اضغط على التوقيت للانتقال لشرح الفيديو 🎥\)\s*', '', source_clean)
        source_clean = re.sub(r'<\s*i\s*>\s*\(يمكنك الضغط على الوقت للوصول إلى الفيديو\)\s*<\s*/i\s*>', '', source_clean)
        source_clean = re.sub(r'\s*\(يمكنك الضغط على الوقت للوصول إلى الفيديو\)\s*', '', source_clean)
        
        hint = "<i>(اضغط على التوقيت للانتقال لشرح الفيديو 🎥)</i>"
        parts_list.append(f"📍 <b>المصدر :</b>\n<blockquote>\u200f{source_clean.strip()}\n\n{hint}</blockquote>")
        
    full_text = f"{qa_block}\n\n" + "\n\n".join(parts_list)
    
    # Bouton YouTube
    youtube_url = None
    yt_match = re.search(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s\)"\'><]+', explanation)
    if yt_match:
        youtube_url = yt_match.group(0).strip()
        
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    if youtube_url:
        buttons.append([InlineKeyboardButton(text="🎥 مشاهدة على يوتيوب (YouTube)", url=youtube_url)])
        
    nav_row = [InlineKeyboardButton(text="⚠️ خطأ في الشرح", callback_data=f"report_expl_start:{q_id}")]
    current_state = await state.get_state()
    if current_state == QuizStates.answering.state:
        nav_row.append(InlineKeyboardButton(text="⏭️ السؤال التالي", callback_data="quiz_next"))
        
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="↩️ العودة", callback_data=f"back_to_corr:{q_id}")])
        
    back_kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text=full_text,
        reply_markup=back_kb,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )


@router.callback_query(F.data.startswith("back_to_corr:"))
async def handle_back_to_corr(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == QuizStates.answering.state:
        q_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        current_index = data.get("current_index", 0)
        await callback.answer()
        await render_question_correction(callback, state, current_index)
    else:
        from handlers.support import show_browser_question
        await callback.answer()
        await show_browser_question(callback, state)


@router.callback_query(QuizStates.answering, F.data == "quiz_next")
async def handle_quiz_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data.get("current_index")
    next_index = current_index + 1
    
    await state.update_data(current_index=next_index)
    questions = data.get("questions", [])
    
    if next_index >= len(questions):
        await finish_quiz(callback, state)
        await callback.answer()
        return
        
    answers = data.get("answers", {})
    if str(next_index) in answers:
        await render_question_correction(callback, state, next_index)
    else:
        await show_question(callback, state)
    await callback.answer()

@router.callback_query(QuizStates.answering, F.data == "quiz_prev")
async def handle_quiz_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data.get("current_index", 0)
    if current_index > 0:
        await render_question_correction(callback, state, current_index - 1)
    await callback.answer()

@router.callback_query(QuizStates.answering, F.data == "quiz_finish")
async def handle_quiz_finish(callback: CallbackQuery, state: FSMContext):
    await finish_quiz(callback, state)
    await callback.answer()

@router.callback_query(F.data == "quiz_exit")
async def handle_quiz_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    await callback.message.edit_text(
        "🚪 تم إنهاء الاختبار والعودة للقائمة الرئيسية.",
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining)
    )
    await callback.answer()

async def finish_quiz(callback: CallbackQuery, state: FSMContext):
    """Calculate and display final quiz results."""
    data = await state.get_data()
    questions = data.get("questions")
    results = data.get("results", {})
    settings = data.get("settings", DEFAULT_SETTINGS)
    
    total = len(questions)
    correct_count = sum(1 for r in results.values() if r.get("is_correct"))
    percentage = int((correct_count / total) * 100) if total > 0 else 0

    # Contextual encouragement messages based on percentage score
    if percentage == 100:
        encouragement = "🏆 <b>ما شاء الله! درجة كاملة! ممتاز جداً، استمر بهذا الأداء الرائع!</b>"
    elif percentage >= 80:
        encouragement = "🔥 <b>ممتاز! لقد قاربت على الإتقان الكامل، أحسنت صنعاً!</b>"
    elif percentage >= 50:
        encouragement = "👍 <b>أداء جيد! يمكنك تحسين النتيجة بمراجعة الأخطاء وتكرار المحاولة.</b>"
    else:
        encouragement = "📚 <b>بداية طيبة، العلم بالتعلم! راجع الأخطاء وستتحسن بالتأكيد في المرة القادمة.</b>"

    if data.get("guided_path_quiz"):
        user_id = callback.from_user.id
        guided_subject = data.get("guided_subject")
        guided_lesson = data.get("guided_lesson")
        
        success = (correct_count >= 3)
        if success:
            await db.update_student_course_progress(user_id, guided_subject, guided_lesson, quiz_done=1)
            
        rows = []
        if not success:
            rows.append([InlineKeyboardButton(text="🔄 إعادة محاولة تمرين التقييم", callback_data=f"guided_step:{guided_subject}:{guided_lesson}:quiz")])
        rows.append([InlineKeyboardButton(text="↩️ العودة لصفحة الدرس الموجه", callback_data=f"guided_path_les:{guided_subject}:{guided_lesson}")])
        rows.append([InlineKeyboardButton(text="↩️ مسار الدروس", callback_data=f"guided_path_sub:{guided_subject}")])
        
        status_msg = "🎉 <b>أحسنت! لقد نجحت في الاختبار التقييمي!</b>\n\nتم إكمال الدرس بالكامل بنجاح! 🟩" if success else "⚠️ <b>لقد أكملت الاختبار لكن لم تحقق درجة النجاح المطلوبة (60%).</b>\n\nيرجى إعادة المحاولة لتحقيق نتيجة أفضل وتثبيت المعلومات."
        
        result_text = (
            f"🏁 <b>نتيجة تمرين التقييم للمسار الموجه:</b>\n"
            f"📚 الدرس {guided_lesson} - مادة {SUBJECT_MAP.get(guided_subject, guided_subject)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 النتيجة: <b>{correct_count} من {total}</b> ({percentage}%)\n\n"
            f"{status_msg}\n\n"
            f"{encouragement}"
        )
        
        await state.clear()
        await callback.message.edit_text(
            result_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Calculate wrong questions to allow retrying them
    wrong_questions = []
    for i, q in enumerate(questions):
        r = results.get(str(i), {})
        if not r.get("is_correct"):
            wrong_questions.append(q)
            
    # Transition to showing_results state to handle retry/new quiz options
    await state.set_state(QuizStates.showing_results)
    await state.update_data(wrong_questions=wrong_questions)
    
    percentage = int((correct_count / total) * 100) if total > 0 else 0
    
    # Contextual encouragement messages based on percentage score
    if percentage == 100:
        encouragement = "🏆 <b>ما شاء الله! درجة كاملة! ممتاز جداً، استمر بهذا الأداء الرائع!</b>"
    elif percentage >= 80:
        encouragement = "🔥 <b>ممتاز! لقد قاربت على الإتقان الكامل، أحسنت صنعاً!</b>"
    elif percentage >= 50:
        encouragement = "👍 <b>أداء جيد! يمكنك تحسين النتيجة بمراجعة الأخطاء وتكرار المحاولة.</b>"
    else:
        encouragement = "📚 <b>بداية طيبة، العلم بالتعلم! راجع الأخطاء وستتحسن بالتأكيد في المرة القادمة.</b>"
    
    # Smart recommendation: detect the course with the most errors in this quiz
    course_error_counts = {}
    for q in wrong_questions:
        subj = q.get("subject", "").lower().strip()
        cn = q.get("course_number")
        key = (subj, cn)
        course_error_counts[key] = course_error_counts.get(key, 0) + 1
    
    worst_course = None
    worst_subject = None
    worst_count = 0
    if course_error_counts:
        worst_key = max(course_error_counts, key=lambda k: course_error_counts[k])
        worst_subject, worst_course = worst_key
        worst_count = course_error_counts[worst_key]
        
    correction_val = settings.get("correction", "immediate")
    reply_markup = kb.get_quiz_results_keyboard(
        len(wrong_questions),
        targeted_subject=worst_subject,
        targeted_course=worst_course,
        targeted_errors=worst_count
    )
    
    if correction_val == "strict":
        result_text = (
            f"🏁 <b>اكتمل الاختبار!</b>\n\n"
            f"📊 النتيجة النهائية: <b>{correct_count} من {total}</b> ({percentage}%)\n\n"
            f"{encouragement}\n\n"
            f"⚠️ <b>ملاحظة:</b> تم إجراء الاختبار في وضع الامتحان (لا يتم عرض الإجابات أو مراجعة الأخطاء)."
        )
        strict_reply_markup = kb.get_quiz_results_keyboard(0, None, None, 0)
        await callback.message.edit_text(result_text, reply_markup=strict_reply_markup, parse_mode="HTML")
    elif correction_val == "immediate":
        result_text = (
            f"🏁 <b>اكتمل الاختبار!</b>\n\n"
            f"📊 النتيجة النهائية: <b>{correct_count} من {total}</b> ({percentage}%)\n\n"
            f"{encouragement}\n\n"
        )
        if worst_course and worst_count >= 2:
            subj_ar = SUBJECT_MAP.get(worst_subject, worst_subject)
            result_text += (
                f"💡 <b>توصية:</b> لقد أخطأت <b>{worst_count} أسئلة</b> في {subj_ar} - الدرس {worst_course}.\n"
                f"هل تريد مراجعة هذا الدرس مباشرةً؟\n\n"
            )
        result_text += "🌟 يمكنك مراجعة أخطائك أو بدء اختبار جديد في أي وقت."
        await callback.message.edit_text(result_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        summary_header = (
            f"🏁 <b>نتيجة الاختبار:</b>\n\n"
            f"📊 النتيجة الإجمالية: <b>{correct_count} من {total}</b> ({percentage}%)\n\n"
            f"{encouragement}\n\n"
            f"📝 <b>مراجعة الأسئلة وتفاصيل الإجابات:</b>\n"
            f"=============================\n"
        )
        
        review_details = ""
        for i, q in enumerate(questions):
            r = results.get(str(i), {})
            user_ans = r.get("choice")
            correct_ans = r.get("correct_choice")
            elapsed = r.get("elapsed", 0.0)
            is_timeout = r.get("is_timeout", False)
            active_choices = r.get("active_choices", {})
            
            subject_ar = SUBJECT_MAP.get(q.get("subject", "").lower(), q.get("subject"))
            
            review_details += f"\n<b>السؤال {i + 1}:</b> <i>{q.get('question').strip()}</i>\n"
            
            if is_timeout:
                review_details += f"⏱️ إجابتك: <b>انتهى الوقت</b> ❌\n"
            elif r.get("is_correct"):
                ans_text = active_choices.get(user_ans, "")
                review_details += f"إجابتك: <b>{ARABIC_CHARS.get(user_ans, '').upper()}) {ans_text}</b> ✅ (في {elapsed:.1f}ث)\n"
            else:
                user_text = active_choices.get(user_ans, "")
                correct_text = active_choices.get(correct_ans, "")
                review_details += f"إجابتك: <s>{ARABIC_CHARS.get(user_ans, '').upper()}) {user_text}</s> ❌ (في {elapsed:.1f}ث)\n"
                review_details += f"الجواب الصحيح: <b>{ARABIC_CHARS.get(correct_ans, '').upper()}) {correct_text}</b>\n"
                
            if q.get("explanation"):
                review_details += f"💬 <b>قول الشيخ:</b>\n<blockquote>{q.get('explanation').strip()}</blockquote>\n"
                
            review_details += "-----------------------------\n"
            
        full_text = summary_header + review_details
        chunks = split_text(full_text)
        
        if len(chunks) == 1:
            await callback.message.edit_text(chunks[0], reply_markup=reply_markup, parse_mode="HTML")
        else:
            await callback.message.edit_text(chunks[0], parse_mode="HTML")
            # Send subsequent chunks as new messages
            for idx, chunk in enumerate(chunks[1:]):
                is_last_chunk = (idx == len(chunks) - 2)
                chunk_markup = reply_markup if is_last_chunk else None
                await callback.message.answer(chunk, reply_markup=chunk_markup, parse_mode="HTML")

# --- Generic Error Reporting Handlers ---

ERROR_TYPE_MAP = {
    "ans": "خطأ في الإجابة الصحيحة",
    "text": "خطأ في نص السؤال (المنشأ)",
    "choices": "خطأ في أحد الخيارات",
    "other": "مشكلة أخرى / سبب آخر"
}

@router.callback_query(F.data.startswith("rep_q:"))
async def handle_report_question_init(callback: CallbackQuery):
    # Format: rep_q:{question_id}:{source}
    parts = callback.data.split(":")
    question_id = int(parts[1])
    source = parts[2]
    
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_report_error_options_keyboard(question_id, source=source)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rep_cancel:"))
async def handle_report_cancel(callback: CallbackQuery, state: FSMContext):
    # Format: rep_cancel:{question_id}:{source}
    parts = callback.data.split(":")
    question_id = int(parts[1])
    source = parts[2] if len(parts) > 2 else "quiz"

    await callback.answer()

    if source == "quiz":
        is_fav = await db.is_favorite(callback.from_user.id, question_id)
        data = await state.get_data()
        questions = data.get("questions", [])
        current_index = data.get("current_index", 0)
        is_last = (current_index + 1 >= len(questions))
        has_prev = (current_index > 0)

        q = await db.get_question_by_id(question_id)
        has_expl = bool(q.get("explanation")) if q else False
        await callback.message.edit_reply_markup(
            reply_markup=kb.get_feedback_keyboard(
                question_id,
                is_fav,
                is_last,
                has_explanation=has_expl,
                has_prev=has_prev
            )
        )
        return

    data = await state.get_data()
    browser_ids = data.get("browser_ids", [])
    idx = data.get("browser_idx", 0)
    has_prev = idx > 0
    has_next = idx < len(browser_ids) - 1

    await callback.message.edit_reply_markup(
        reply_markup=kb.get_question_browser_nav_keyboard(question_id, has_prev, has_next)
    )

@router.callback_query(F.data.startswith("rep_err:"))
async def handle_report_error_submit(callback: CallbackQuery, state: FSMContext):
    # Format: rep_err:{question_id}:{error_type}:{source}
    parts = callback.data.split(":")
    question_id = int(parts[1])
    error_type = parts[2]
    source = parts[3]
    
    # Store report details in state to collect comment
    await state.update_data(
        rep_q_id=question_id,
        rep_error_type=error_type,
        rep_source=source,
        rep_msg_id=callback.message.message_id
    )
    
    await state.set_state(QuizStates.waiting_for_report_comment)
    
    error_label = ERROR_TYPE_MAP.get(error_type, error_type)
    prompt_text = (
        f"⚠️ <b>الإبلاغ عن خطأ في السؤال #{question_id}</b>\n"
        f"• نوع الخطأ: <b>{error_label}</b>\n\n"
        f"✏️ يرجى كتابة تفاصيل إضافية حول المشكلة في رسالة وإرسالها (مثال: الإجابة الصحيحة هي ب وليس أ لأن...).\n\n"
        f"💡 يمكنك أيضاً الضغط على زر <b>إرسال البلاغ بدون تعليق</b> بالأسفل لإرسال البلاغ مباشرة."
    )
    await callback.message.edit_text(
        text=prompt_text,
        reply_markup=kb.get_report_comment_keyboard(question_id, error_type, source),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rep_send_no_comment:"))
async def handle_report_send_no_comment(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    question_id = int(parts[1])
    error_type = parts[2]
    source = parts[3]
    
    await callback.answer()
    await submit_question_report(
        bot=callback.message.bot,
        user=callback.from_user,
        question_id=question_id,
        error_type=error_type,
        comment="",
        source=source,
        state=state,
        message_to_edit=callback.message
    )

@router.message(QuizStates.waiting_for_report_comment)
async def handle_report_comment_text(message: Message, state: FSMContext):
    data = await state.get_data()
    question_id = data.get("rep_q_id")
    error_type = data.get("rep_error_type")
    source = data.get("rep_source")
    rep_msg_id = data.get("rep_msg_id")
    
    media_file_id = None
    media_type = None
    if message.photo:
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.document:
        media_file_id = message.document.file_id
        media_type = "document"
    elif message.voice:
        media_file_id = message.voice.file_id
        media_type = "voice"
    elif message.audio:
        media_file_id = message.audio.file_id
        media_type = "audio"
    elif message.video:
        media_file_id = message.video.file_id
        media_type = "video"
        
    comment = (message.text or message.caption or "").strip()
    
    # Delete student's text message to keep the chat clean
    try:
        await message.delete()
    except Exception:
        pass
    class DummyMessageToEdit:
        def __init__(self, bot, chat_id, message_id):
            self.bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
        async def edit_text(self, text, reply_markup=None, parse_mode=None):
            try:
                return await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception:
                return await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                
    chat_id = message.chat.id
    dummy_msg = DummyMessageToEdit(message.bot, chat_id, rep_msg_id)
    
    await submit_question_report(
        bot=message.bot,
        user=message.from_user,
        question_id=question_id,
        error_type=error_type,
        comment=comment,
        source=source,
        state=state,
        message_to_edit=dummy_msg,
        media_file_id=media_file_id,
        media_type=media_type
    )


async def submit_question_report(bot, user, question_id: int, error_type: str, comment: str, source: str, state: FSMContext, message_to_edit, media_file_id: str = None, media_type: str = None):
    # 1. Fetch question details
    q = await db.get_question_by_id(question_id)
    if not q:
        if hasattr(message_to_edit, 'edit_text'):
            await message_to_edit.edit_text("⚠️ السؤال غير موجود. تم إلغاء العملية.")
        await state.clear()
        return
        
    username_str = f"@{user.username}" if user.username else ""
    first_name_str = user.first_name or ""
    error_label = ERROR_TYPE_MAP.get(error_type, error_type)
    
    notes_str = f"[{error_label}] {comment}" if comment else error_label
    
    # 2. Add to SQLite database
    report_id = await db.add_question_report(
        user_id=user.id,
        username=username_str,
        first_name=first_name_str,
        q_id=question_id,
        r_type="question_error",
        notes=notes_str,
        urgency="Moyen",
        media_file_id=media_file_id,
        media_type=media_type
    )
    
    # 3. Format and send ticket message using centralized helper
    from handlers.support import send_rich_support_ticket
    await send_rich_support_ticket(bot, report_id)
            
    # Edit the message in-place with confirmation and return button
    success_text = (
        f"✅ <b>تم إرسال البلاغ بنجاح للإدارة.</b>\n"
        f"🔖 رقم التذكرة: <b>#{report_id}</b>\n\n"
        f"📝 <b>ملاحظتك:</b>\n"
        f"<blockquote>{comment if comment else error_label}</blockquote>\n\n"
        f"ستقوم الإدارة بمراجعته والرد عليه في أقرب وقت. جزاك الله خيراً!"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ العودة للسؤال", callback_data=f"rep_back_to_q:{question_id}:{source}")]
    ])
    
    if hasattr(message_to_edit, 'edit_text'):
        try:
            await message_to_edit.edit_text(success_text, reply_markup=back_kb, parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id=user.id, text=success_text, reply_markup=back_kb, parse_mode="HTML")
    else:
        msg_id = message_to_edit.message_id if hasattr(message_to_edit, 'message_id') else message_to_edit
        try:
            await bot.edit_message_text(
                chat_id=user.id,
                message_id=int(msg_id),
                text=success_text,
                reply_markup=back_kb,
                parse_mode="HTML"
            )
        except Exception:
            await bot.send_message(
                chat_id=user.id,
                text=success_text,
                reply_markup=back_kb,
                parse_mode="HTML"
            )


# --- Explanation Error Reporting Handlers ---

# --- Explanation Error Reporting Handlers ---

EXPL_ERROR_TYPE_MAP = {
    "mismatch_time": "عدم تطابق النص ودقيقة الفيديو",
    "pedagogical": "خطأ في الشرح / المحتوى العلمي",
    "spelling": "خطأ إملائي أو مطبعي",
    "other": "سبب آخر"
}

@router.callback_query(F.data.startswith("report_expl_start:"))
async def handle_report_expl_start(callback: CallbackQuery):
    q_id = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_expl_error_options_keyboard(q_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rep_expl_type:"))
async def handle_report_expl_type(callback: CallbackQuery, state: FSMContext):
    # Format: rep_expl_type:{q_id}:{error_type}
    parts = callback.data.split(":")
    q_id = int(parts[1])
    error_type = parts[2]
    
    await state.update_data(
        expl_q_id=q_id,
        expl_error_type=error_type,
        expl_msg_id=callback.message.message_id,
        expl_timestamp=None
    )
    
    if error_type == "mismatch_time":
        await state.set_state(QuizStates.waiting_for_expl_timestamp)
        prompt_text = (
            f"⏱️ <b>عدم تطابق النص ودقيقة الفيديو (السؤال #{q_id})</b>\n\n"
            f"يرجى كتابة دقيقة الفيديو التي وقع فيها الخطأ (مثال: <code>12:45</code> أو <code>7:30</code>) ثم إرسالها في رسالة نصية :"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"prof_quote:{q_id}")]
        ])
        await callback.message.edit_text(text=prompt_text, reply_markup=back_kb, parse_mode="HTML")
    else:
        await state.set_state(QuizStates.waiting_for_expl_comment)
        error_label = EXPL_ERROR_TYPE_MAP.get(error_type, error_type)
        prompt_text = (
            f"⚠️ <b>الإبلاغ عن خطأ في شرح الشيخ للسؤال #{q_id}</b>\n"
            f"• نوع الخطأ: <b>{error_label}</b>\n\n"
            f"✏️ يرجى كتابة تفاصيل إضافية حول الخطأ وإرسالها في رسالة نصية.\n\n"
            f"💡 يمكنك أيضاً الضغط على زر <b>إرسال البلاغ بدون تعليق</b> بالأسفل لإرسال البلاغ مباشرة."
        )
        await callback.message.edit_text(
            text=prompt_text,
            reply_markup=kb.get_expl_report_comment_keyboard(q_id, error_type),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("rep_expl_send:"))
async def handle_report_expl_send_no_comment(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    q_id = int(parts[1])
    error_type = parts[2]
    await callback.answer()
    await submit_explanation_report(
        bot=callback.message.bot,
        user=callback.from_user,
        question_id=q_id,
        error_type=error_type,
        comment="",
        state=state,
        message_to_edit=callback.message
    )

@router.message(QuizStates.waiting_for_expl_timestamp)
async def handle_expl_report_timestamp_text(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("expl_q_id")
    error_type = data.get("expl_error_type")
    expl_msg_id = data.get("expl_msg_id")
    
    timestamp = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
        
    if not timestamp:
        return
        
    if not any(char.isdigit() for char in timestamp):
        await message.answer("⚠️ يرجى إدخال دقيقة صالحة (مثال: 12:45) :")
        return
        
    await state.update_data(expl_timestamp=timestamp)
    await state.set_state(QuizStates.waiting_for_expl_comment)
    
    prompt_text = (
        f"⏱️ <b>عدم تطابق النص ودقيقة الفيديو (السؤال #{q_id})</b>\n"
        f"• الدقيقة المسجلة: <b>{timestamp}</b>\n\n"
        f"✏️ يرجى كتابة تفاصيل إضافية حول عدم التطابق وإرسالها في رسالة نصية.\n\n"
        f"💡 يمكنك أيضاً الضغط على زر <b>إرسال البلاغ بدون تعليق</b> بالأسفل لإرسال البلاغ مباشرة."
    )
    
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=expl_msg_id,
            text=prompt_text,
            reply_markup=kb.get_expl_report_comment_keyboard(q_id, error_type),
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(
            text=prompt_text,
            reply_markup=kb.get_expl_report_comment_keyboard(q_id, error_type),
            parse_mode="HTML"
        )

@router.message(QuizStates.waiting_for_expl_comment)
async def handle_expl_report_comment_text(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get("expl_q_id")
    error_type = data.get("expl_error_type")
    expl_msg_id = data.get("expl_msg_id")
    
    media_file_id = None
    media_type = None
    if message.photo:
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.document:
        media_file_id = message.document.file_id
        media_type = "document"
    elif message.voice:
        media_file_id = message.voice.file_id
        media_type = "voice"
    elif message.audio:
        media_file_id = message.audio.file_id
        media_type = "audio"
    elif message.video:
        media_file_id = message.video.file_id
        media_type = "video"
        
    comment = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
        
    class DummyMessageToEdit:
        def __init__(self, bot, chat_id, message_id):
            self.bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
        async def edit_text(self, text, reply_markup=None, parse_mode=None):
            try:
                return await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception:
                return await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                
    chat_id = message.chat.id
    dummy_msg = DummyMessageToEdit(message.bot, chat_id, expl_msg_id)
    
    await submit_explanation_report(
        bot=message.bot,
        user=message.from_user,
        question_id=q_id,
        error_type=error_type,
        comment=comment,
        state=state,
        message_to_edit=dummy_msg,
        media_file_id=media_file_id,
        media_type=media_type
    )

async def submit_explanation_report(bot, user, question_id: int, error_type: str, comment: str, state: FSMContext, message_to_edit, media_file_id: str = None, media_type: str = None):
    q = await db.get_question_by_id(question_id)
    if not q:
        if hasattr(message_to_edit, 'edit_text'):
            await message_to_edit.edit_text("⚠️ السؤال غير موجود. تم إلغاء العملية.")
        await state.clear()
        return
        
    data = await state.get_data()
    timestamp = data.get("expl_timestamp")
    
    username_str = f"@{user.username}" if user.username else ""
    first_name_str = user.first_name or ""
    error_label = EXPL_ERROR_TYPE_MAP.get(error_type, error_type)
    
    if timestamp:
        notes_str = f"[{error_label}] [الدقيقة: {timestamp}] {comment}".strip()
    else:
        notes_str = f"[{error_label}] {comment}" if comment else error_label
        
    # Add report to DB
    report_id = await db.add_question_report(
        user_id=user.id,
        username=username_str,
        first_name=first_name_str,
        q_id=question_id,
        r_type="expl_error",
        notes=notes_str,
        urgency="Moyen",
        media_file_id=media_file_id,
        media_type=media_type
    )
    
    # Notify support group using the centralized helper
    from handlers.support import send_rich_support_ticket
    await send_rich_support_ticket(bot, report_id)
    
    # Success text to student
    success_text = (
        f"✅ <b>تم إرسال البلاغ بنجاح للإدارة.</b>\n"
        f"🔖 رقم التذكرة: <b>#{report_id}</b>\n\n"
        f"📝 <b>ملاحظتك:</b>\n"
        f"<blockquote>{comment if comment else error_label}</blockquote>\n\n"
        f"ستقوم الإدارة بمراجعته وتعديله في أقرب وقت. جزاك الله خيراً!"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ العودة للسؤال", callback_data=f"rep_back_to_q:{question_id}:quiz")]
    ])
    
    if hasattr(message_to_edit, 'edit_text'):
        try:
            await message_to_edit.edit_text(success_text, reply_markup=back_kb, parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id=user.id, text=success_text, reply_markup=back_kb, parse_mode="HTML")
    else:
        msg_id = message_to_edit.message_id if hasattr(message_to_edit, 'message_id') else message_to_edit
        try:
            await bot.edit_message_text(
                chat_id=user.id,
                message_id=int(msg_id),
                text=success_text,
                reply_markup=back_kb,
                parse_mode="HTML"
            )
        except Exception:
            await bot.send_message(chat_id=user.id, text=success_text, reply_markup=back_kb, parse_mode="HTML")
            
    
    # We remove the specific explanation report keys instead of clearing the whole state
    # so that the quiz context (questions, answers) remains available for the back button.
    data = await state.get_data()
    new_data = {k: v for k, v in data.items() if not k.startswith("expl_")}
    await state.set_data(new_data)

@router.callback_query(F.data.startswith("rep_back_to_q:"))
async def handle_rep_back_to_q(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    question_id = int(parts[1])
    source = parts[2]
    
    if source == "quiz":
        await state.set_state(QuizStates.answering)
        data = await state.get_data()
        current_index = data.get("current_index", 0)
        await render_question_correction(callback, state, current_index)
    else:
        from handlers.support import SupportStates, show_browser_question
        await state.set_state(SupportStates.browsing_questions)
        await show_browser_question(callback, state)


@router.callback_query(QuizStates.showing_results, F.data == "quiz_retry_errors")
async def handle_quiz_retry_errors(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wrong_questions = data.get("wrong_questions", [])
    if not wrong_questions:
        await callback.answer("⚠️ لا توجد أخطاء لإعادة محاولتها.", show_alert=True)
        return
    await callback.answer("🔄 جاري إعادة محاولة الأسئلة الخاطئة...")
    settings = data.get("settings", DEFAULT_SETTINGS)
    if settings.get("order", "random") == "random":
        random.shuffle(wrong_questions)
    await state.set_state(QuizStates.answering)
    await state.update_data(questions=wrong_questions, current_index=0, answers={}, times={}, results={})
    await show_question(callback, state)


@router.callback_query(QuizStates.showing_results, F.data == "quiz_new_direct")
async def handle_quiz_new_direct(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.answer("⏳ جاري تحضير أسئلة جديدة...")
    await initialize_and_start_quiz(callback, state, data)


@router.callback_query(QuizStates.showing_results, F.data == "quiz_exit_results")
async def handle_quiz_exit_results(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    await callback.message.edit_text(
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة التمارين والمسار التعليمي:",
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "q_ignored")
async def handle_q_ignored(callback: CallbackQuery):
    await callback.answer()

