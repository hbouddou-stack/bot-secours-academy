import re
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
import keyboards as kb

logger = logging.getLogger(__name__)
router = Router(name="revision")


def clean_islamic_salutations(text: str) -> str:
    if not text:
        return text
    # Replace common variations of the Prophet's blessing with the ligature symbol ﷺ
    pattern = r"صلى\s+الله\s+عليه\s+(?:وآله\s+)?و?\s?سلم"
    text = re.sub(pattern, "ﷺ", text)
    text = text.replace("صلى الله عليه وسلم", "ﷺ")
    text = text.replace("صلى الله عليه و سلم", "ﷺ")
    # Render Markdown bold (**) as HTML bold (<b>)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    # Strip any remaining loose double asterisks
    text = text.replace("**", "")
    return text


def extract_page_title(page_content: str, fallback_index: int) -> str:
    # Try to find the first <b>...</b> tag in the page_content
    match = re.search(r"<b>(.*?)</b>", page_content)
    if match:
        title = match.group(1).strip()
        # Clean up any HTML if nested
        title = re.sub(r"<[^>]*>", "", title)
        if 0 < len(title) <= 40:
            return title
        elif len(title) > 40:
            return title[:37] + "..."
            
    # Fallback to extracting the first line or first few words
    lines = [line.strip() for line in page_content.split("\n") if line.strip()]
    if lines:
        first_line = lines[0]
        # Remove any bold tags or other HTML tags
        first_line = re.sub(r"<[^>]*>", "", first_line)
        if len(first_line) <= 40:
            return first_line
        words = first_line.split()
        if len(words) >= 4:
            return " ".join(words[:4]) + "..."
            
    return f"الجزء {fallback_index}"



class StudentStudyPathStates(StatesGroup):
    reading = State()
    answering_validation = State()
    searching_keyword = State()
    viewing_search_results = State()


def highlight_arabic_keyword(text: str, keyword: str) -> str:
    if not keyword or not text:
        return text
    
    # Extract the base word by removing common prefixes from the search keyword
    base = keyword.strip()
    if len(base) > 3 and base.startswith("ال"):
        base = base[2:]
    elif len(base) > 4 and (base.startswith("وال") or base.startswith("فال") or base.startswith("بال") or base.startswith("كال")):
        base = base[3:]
        
    if len(base) < 2:
        return text
        
    # Regex to match the base word with common Arabic prefixes and suffixes
    prefixes = r"(?:ال|و|ف|ب|ك|لل|وال|فال|بال|كال|ول|فل|أ)?"
    suffixes = r"(?:ه|ها|هم|هن|كم|كن|نا|ي|ك|ت|وا|ون|ين|ان|ات|ة|اً|ا)?"
    
    # (?<![\w\u0621-\u064A]) and (?![\w\u0621-\u064A]) to safely enforce arabic word boundaries
    pattern = r"(?<![\w\u0621-\u064A])(" + prefixes + re.escape(base) + suffixes + r")(?![\w\u0621-\u064A])"
    
    highlighted = re.sub(pattern, r"<b>\1</b>", text)
    return highlighted



async def render_revision_lessons_fallback(message_or_callback, state: FSMContext, subject: str):
    await state.clear()
    lessons_status = await db.get_all_lessons_with_resources(subject)
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)

    text = (
        f"📚 <b>مكتبة المراجعة - مادة {sub_ar}:</b>\n\n"
        f"اختر الدرس الذي تود مراجعته:\n"
        f"✅ = ملخص وخريطة متوفرين | 🟡 = ملخص أو خريطة متوفرة"
    )
    lesson_kb = kb.get_revision_lessons_keyboard(subject, lessons_status)
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=lesson_kb, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=lesson_kb, parse_mode="HTML")

@router.message(Command("revision"))
@router.message(F.text == "📚 مكتبة المراجعة (ملخصات + خرائط)")
async def cmd_revision(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    pref_sub = await db.get_user_preferred_subject(user_id)
    if pref_sub:
        await render_revision_lessons_fallback(message, state, pref_sub)
        return
        
    await message.answer(
        "📚 <b>مكتبة المراجعة لأكاديمية الباجي:</b>\n\n"
        "اختر المادة الشرعية التي تود مراجعة ملخصاتها أو عرض خرائطها الذهنية:",
        reply_markup=kb.get_revision_subjects_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "main_revision")
async def handle_main_revision(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text = (
        "📖 <b>مكتبتي الشاملة لأكاديمية الباجي</b>\n\n"
        "مرحباً بك في مكتبتك الشاملة! هنا يمكنك الوصول إلى كافة الموارد التعليمية والبحث الذكي ومتابعة مسارك الموجه:"
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=kb.get_library_menu_keyboard(),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=kb.get_library_menu_keyboard(),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("rev_sub:"))
async def handle_rev_sub(callback: CallbackQuery):
    await callback.answer()
    subject = callback.data.split(":")[1]

    lessons_status = await db.get_all_lessons_with_resources(subject)
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)

    text = (
        f"📚 <b>مكتبة المراجعة - مادة {sub_ar}:</b>\n\n"
        f"اختر الدرس الذي تود مراجعته:\n"
        f"✅ = ملخص وخريطة متوفرين | 🟡 = ملخص أو خريطة متوفرة"
    )
    lesson_kb = kb.get_revision_lessons_keyboard(subject, lessons_status)

    # Try editing in place (works if current message is text)
    try:
        await callback.message.edit_text(text, reply_markup=lesson_kb, parse_mode="HTML")
    except TelegramBadRequest:
        # Current message is a photo (mind map menu) — delete it then send text
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=lesson_kb,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("rev_les:"))
async def handle_rev_les(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    # Check if study path exists in DB
    chapters = await db.get_course_chapters(subject, lesson)
    has_study_path = len(chapters) > 0

    map_pages = await db.get_mind_map_pages(subject, lesson)
    has_map = len(map_pages) > 0
    resources = await db.get_lesson_resources(subject, lesson)
    has_sum = bool(resources and resources.get("summary_file_id"))
    trans_pages = await db.get_transcription_pages(subject, lesson)
    has_trans = len(trans_pages) > 0
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)

    if has_map:
        # ━ Show mind map directly as the lesson menu (no intermediate text step) ━
        total_pages = len(map_pages)
        file_id = map_pages[0]["file_id"]
        page_label = f" - الصفحة 1 / {total_pages}" if total_pages > 1 else ""
        caption = (
            f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar}){page_label}</b>"
        )
        menu_kb = kb.get_map_as_menu_keyboard(subject, lesson, has_sum, has_trans, 1, total_pages, has_study_path=has_study_path)

        # Delete the current message (text lesson list) and send the photo
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete lesson list message: {e}")

        await _send_map_photo(callback.message.bot, callback.from_user.id, file_id, caption, menu_kb)
    else:
        # No map — show the regular text resource menu
        text = (
            f"📖 <b>مكتبة المراجعة - الدرس {lesson} (مادة {sub_ar}):</b>\n\n"
            f"اختر الملف الذي تود تحميله أو عرضه:"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=kb.get_revision_resources_keyboard(subject, lesson, False, has_sum, has_trans, has_study_path=has_study_path),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            # Coming back from a photo — send fresh
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.bot.send_message(
                chat_id=callback.from_user.id,
                text=text,
                reply_markup=kb.get_revision_resources_keyboard(subject, lesson, False, has_sum, has_trans, has_study_path=has_study_path),
                parse_mode="HTML"
            )


@router.callback_query(F.data == "rev_noop")
async def handle_rev_noop(callback: CallbackQuery):
    await callback.answer("⚠️ هذا الملف غير متوفر حالياً. يرجى المحاولة لاحقاً.", show_alert=True)


# ── Helper: send first page of mind map (deletes text menu, sends photo) ────

async def _send_map_photo(bot, chat_id: int, file_id: str, caption: str, reply_markup):
    """Send a mind map image — falls back to send_document if it was uploaded uncompressed."""
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=file_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "can't use file of type Document as Photo" in str(e):
            await bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            raise


# ── Student: open mind map from library ──────────────────────────────────────

@router.callback_query(F.data.startswith("rev_get_map:"))
async def handle_rev_get_map(callback: CallbackQuery):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    pages = await db.get_mind_map_pages(subject, lesson)
    if not pages:
        await callback.answer("⚠️ عذراً، الخريطة الذهنية غير متوفرة لهذا الدرس.", show_alert=True)
        return

    await callback.answer()

    total_pages = len(pages)
    file_id = pages[0]["file_id"]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    page_label = f" - الصفحة 1 / {total_pages}" if total_pages > 1 else ""
    caption = f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar}){page_label}</b>"
    reader_kb = kb.get_map_reader_keyboard(subject, lesson, 1, total_pages)

    # 1. Delete text menu message FIRST so photo appears in its place
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete menu message before map: {e}")

    # 2. Send the photo
    await _send_map_photo(callback.message.bot, callback.from_user.id, file_id, caption, reader_kb)


@router.callback_query(F.data.startswith("rev_map_page:"))
async def handle_rev_map_page(callback: CallbackQuery):
    """Navigate between mind map pages — current message is already a photo, use edit_media."""
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    page = int(parts[3])

    pages = await db.get_mind_map_pages(subject, lesson)
    if not pages or page < 1 or page > len(pages):
        await callback.answer()
        return

    await callback.answer()
    total_pages = len(pages)
    file_id = pages[page - 1]["file_id"]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    page_label = f" - الصفحة {page} / {total_pages}" if total_pages > 1 else ""
    caption = f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar}){page_label}</b>"

    # Determine if we need the full resource menu keyboard or just nav
    resources = await db.get_lesson_resources(subject, lesson)
    has_sum = bool(resources and resources.get("summary_file_id"))
    trans_pages = await db.get_transcription_pages(subject, lesson)
    has_trans = len(trans_pages) > 0
    chapters = await db.get_course_chapters(subject, lesson)
    has_study_path = len(chapters) > 0
    menu_kb = kb.get_map_as_menu_keyboard(subject, lesson, has_sum, has_trans, page, total_pages, has_study_path=has_study_path)

    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(media=file_id, caption=caption, parse_mode="HTML"),
            reply_markup=menu_kb
        )
    except TelegramBadRequest as e:
        logger.warning(f"edit_media failed for map page navigation: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await _send_map_photo(callback.message.bot, callback.from_user.id, file_id, caption, menu_kb)


@router.callback_query(F.data.startswith("rev_map_back:"))
async def handle_rev_map_back(callback: CallbackQuery):
    """User pressed ↩️ back from map photo — delete photo and re-show text menu."""
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    # Delete the photo message
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Re-send the text resources menu
    map_pages = await db.get_mind_map_pages(subject, lesson)
    has_map = len(map_pages) > 0
    resources = await db.get_lesson_resources(subject, lesson)
    has_sum = bool(resources and resources.get("summary_file_id"))
    trans_pages = await db.get_transcription_pages(subject, lesson)
    has_trans = len(trans_pages) > 0
    chapters = await db.get_course_chapters(subject, lesson)
    has_study_path = len(chapters) > 0

    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    text = (
        f"📖 <b>مكتبة المراجعة - الدرس {lesson} (مادة {sub_ar}):</b>\n\n"
        f"اختر الملف الذي تود تحميله أو عرضه:"
    )
    await callback.message.bot.send_message(
        chat_id=callback.from_user.id,
        text=text,
        reply_markup=kb.get_revision_resources_keyboard(subject, lesson, has_map, has_sum, has_trans, has_study_path=has_study_path),
        parse_mode="HTML"
    )

# ── Student: show map from quiz correction ───────────────────────────────────

@router.callback_query(F.data.startswith("student_show_map_q:"))
async def handle_student_show_map_q(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split(":")[1])
    q = await db.get_question_by_id(q_id)
    if not q:
        await callback.answer("⚠️ عذراً، السؤال غير موجود.", show_alert=True)
        return

    pages = await db.get_mind_map_pages(q["subject"], q["course_number"])
    if not pages:
        await callback.answer("⚠️ عذراً، الخريطة الذهنية غير متوفرة لهذا الدرس.", show_alert=True)
        return

    await callback.answer()
    total_pages = len(pages)
    file_id = pages[0]["file_id"]
    sub_ar = kb.SUBJECT_LABELS.get(q["subject"], q["subject"])
    page_label = f" - الصفحة 1 / {total_pages}" if total_pages > 1 else ""
    caption = f"🗺️ <b>الخريطة الذهنية للدرس {q['course_number']} ({sub_ar}){page_label}</b>"
    map_kb = kb.get_quiz_map_keyboard(q_id)

    # 1. Delete the correction message first
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete correction message before map: {e}")

    # 2. Send the mind map photo in its place
    await _send_map_photo(callback.message.bot, callback.from_user.id, file_id, caption, map_kb)


@router.callback_query(F.data.startswith("student_map_back:"))
async def handle_student_map_back(callback: CallbackQuery, state: FSMContext):
    """User pressed ↩️ from quiz map — delete photo and re-render the correction."""
    await callback.answer()

    # Delete the map photo
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Re-render the correction from quiz state
    from handlers.quiz import render_question_correction
    data = await state.get_data()
    current_index = data.get("current_index", 0)
    await render_question_correction(callback, state, current_index)


# ── Summary download ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rev_get_sum:"))
async def handle_rev_get_sum(callback: CallbackQuery):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    resources = await db.get_lesson_resources(subject, lesson)
    file_id = resources.get("summary_file_id") if resources else None

    if not file_id:
        await callback.answer("⚠️ عذراً، الملف غير متوفر لهذا الدرس.", show_alert=True)
        return

    await callback.answer("📄 جاري تحميل ملف الملخص...")
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    await callback.message.bot.send_document(
        chat_id=callback.from_user.id,
        document=file_id,
        caption=f"📄 <b>ملخص الدرس {lesson} ({sub_ar})</b>",
        parse_mode="HTML"
    )


# ── Transcription reader ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rev_read_trans_start:"))
async def handle_rev_read_trans_start(callback: CallbackQuery):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    pages = await db.get_transcription_pages(subject, lesson)
    if not pages:
        await callback.answer("⚠️ عذراً، صفحات التفريغ غير متوفرة لهذا الدرس.", show_alert=True)
        return

    await callback.answer("📝 جاري تحميل التفريغ الورقي...")
    total_pages = len(pages)
    page_data = pages[0]
    file_id = page_data["file_id"]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    caption = f"📝 <b>تفريغ الدرس {lesson} ({sub_ar}) - الصفحة 1 / {total_pages}</b>"

    # Send the first photo page
    await callback.message.bot.send_photo(
        chat_id=callback.from_user.id,
        photo=file_id,
        caption=caption,
        reply_markup=kb.get_transcription_reader_keyboard(subject, lesson, 1, total_pages),
        parse_mode="HTML"
    )
    # Delete text menu message
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("rev_read_page:"))
async def handle_rev_read_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    page = int(parts[3])

    pages = await db.get_transcription_pages(subject, lesson)
    if not pages or page < 1 or page > len(pages):
        await callback.answer()
        return

    await callback.answer()
    total_pages = len(pages)
    page_data = pages[page - 1]
    file_id = page_data["file_id"]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    caption = f"📝 <b>تفريغ الدرس {lesson} ({sub_ar}) - الصفحة {page} / {total_pages}</b>"

    # Edit existing media with the new photo page
    await callback.message.edit_media(
        media=InputMediaPhoto(media=file_id, caption=caption, parse_mode="HTML"),
        reply_markup=kb.get_transcription_reader_keyboard(subject, lesson, page, total_pages)
    )


@router.callback_query(F.data.startswith("rev_les:"))
async def handle_rev_les_back(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    # Delete photo reader message (transcription back)
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Send new text files menu
    map_pages = await db.get_mind_map_pages(subject, lesson)
    has_map = len(map_pages) > 0
    resources = await db.get_lesson_resources(subject, lesson)
    has_sum = bool(resources and resources.get("summary_file_id"))
    trans_pages = await db.get_transcription_pages(subject, lesson)
    has_trans = len(trans_pages) > 0
    chapters = await db.get_course_chapters(subject, lesson)
    has_study_path = len(chapters) > 0

    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    text = (
        f"📖 <b>مكتبة المراجعة - الدرس {lesson} (مادة {sub_ar}):</b>\n\n"
        f"اختر الملف الذي تود تحميله أو عرضه:"
    )
    await callback.message.bot.send_message(
        chat_id=callback.from_user.id,
        text=text,
        reply_markup=kb.get_revision_resources_keyboard(subject, lesson, has_map, has_sum, has_trans, has_study_path=has_study_path),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rev_study_path_start:"))
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
        f"📚 <b>خطة الدرس {lesson} - {sub_ar}</b>\n"
        f"المسار التفاعلي مقسم إلى المحاور التالية:\n\n"
    )
    for i, ch in enumerate(chapters):
        status = "✅" if i < idx else "⏳"
        text += f"<blockquote>{status} {i+1}. {ch['title']}</blockquote>\n"
        
    if idx > 0 and idx < len(chapters):
        text += f"\n💡 <i>أنت حالياً عند المحور {idx + 1}. يمكنك استئناف التعلم من حيث توقفت.</i>"
    elif idx >= len(chapters):
        text += f"\n🎉 <i>لقد أتممت جميع محاور هذا الدرس بنجاح!</i>"
        
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
        content_html = "\n\n".join(content_html)
        
    def _get_progress_bar(current: int, total: int) -> str:
        filled = "🟩" * current
        empty = "⬜" * (total - current)
        return f"[{filled}{empty}] {current}/{total} محاور"
        
    pbar = _get_progress_bar(idx + 1, len(chapters))
    text = f"📖 <b>المحور {idx+1}: {chapter['title']}</b>\n\n<blockquote>{content_html}</blockquote>\n\n📊 <b>التقدم:</b>\n{pbar}"
    
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
        content_html = "\n\n".join(content_html)
        
    def _get_progress_bar(current: int, total: int) -> str:
        filled = "🟩" * current
        empty = "⬜" * (total - current)
        return f"[{filled}{empty}] {current}/{total} محاور"
        
    pbar = _get_progress_bar(idx + 1, len(chapters))
    text = f"📖 <b>المحور {idx+1}: {chapter['title']}</b>\n\n<blockquote>{content_html}</blockquote>\n\n📊 <b>التقدم:</b>\n{pbar}"
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
    
    text = f"❓ <b>سؤال المحور:</b>\n\n<blockquote>{q_data[0]}</blockquote>"
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
    
    def _get_progress_bar(current: int, total: int) -> str:
        filled = "🟩" * current
        empty = "⬜" * (total - current)
        return f"[{filled}{empty}] {current}/{total} محاور"
        
    pbar = _get_progress_bar(new_idx, len(chapters))
    text = f"🎉 <b>ممتاز يا {callback.from_user.first_name}! لقد أتممت المحور بنجاح.</b>\n\n📊 <b>التقدم:</b>\n{pbar}\n"
    if explanation:
        text += f"\n💡 <b>توضيح:</b> {explanation}\n"
        
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
    caption = f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar})</b>\n\nأنت الآن جاهز للملخص الشامل والاختبار!"
    
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



async def render_study_path_syllabus(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("path_subject")
    lesson = data.get("path_lesson")
    chapters = data.get("path_chapters")
    if not chapters:
        if subject and lesson:
            chapters = await db.get_course_chapters(subject, lesson)
            await state.update_data(path_chapters=chapters)
            
    if not chapters:
        await callback.answer("⚠️ انتهت الجلسة أو تمت إعادة تشغيل البوت. يرجى البدء من جديد.", show_alert=True)
        return
        
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    text = (
        f"📘 <b>الدرس {lesson} — {sub_ar}</b>\n"
        f"📌 <b>فهرس وتفاصيل محاور الدرس:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    buttons = []
    row = []
    for idx, ch in enumerate(chapters):
        cleaned_ch_title = clean_islamic_salutations(ch['title'])
        text += f"├── 🔖 <b>المحور {idx + 1} : {cleaned_ch_title}</b>\n"
        
        # Split chapter into pages
        content_text = ch['content']
        pages = _split_into_pages(content_text)
        total_pages = len(pages)
        
        for p_idx, page_content in enumerate(pages):
            p_title = extract_page_title(page_content, p_idx + 1)
            p_title = clean_islamic_salutations(p_title)
            # Tree branch symbol
            branch = "└──" if (p_idx == total_pages - 1) else "├──"
            indent = "│     "
            text += f"{indent}{branch} 📄 صفحة {p_idx + 1}/{total_pages} : {p_title}\n"
            
        text += "│\n" # spacer between chapters
        
        # Grid of buttons for fast navigation
        row.append(InlineKeyboardButton(text=f"{idx + 1}", callback_data=f"rev_study_nav:{idx}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
            
    # Remove trailing spacer line if any
    if text.endswith("│\n"):
        text = text[:-2]
        
    if row:
        buttons.append(row)
        
    text += f"\n━━━━━━━━━━━━━━━━━━━━━━\n<i>اختر رقم المحور للانتقال إليه مباشرة، أو ابدأ القراءة:</i>"
    
    buttons.append([InlineKeyboardButton(text="🚀 ابدأ القراءة من الأول", callback_data="rev_study_nav:0")])
    buttons.append([InlineKeyboardButton(text="🚪 العودة للمكتبة", callback_data="rev_study_exit")])
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )


CHAPTER_PAGE_MAX_CHARS = 550  # Max characters per page within a chapter

def _split_into_pages(content: str, max_chars: int = CHAPTER_PAGE_MAX_CHARS) -> list[str]:
    """Split chapter content into pages of at most max_chars characters.
    
    Tries to split on paragraph breaks (\\n\\n), then on sentence-ending punctuation,
    to avoid cutting in the middle of a word or sentence.
    """
    if len(content) <= max_chars:
        return [content]
    
    pages = []
    remaining = content
    
    while len(remaining) > max_chars:
        # Try to find a paragraph break within the limit
        chunk = remaining[:max_chars]
        split_pos = chunk.rfind('\n\n')
        if split_pos > max_chars // 3:
            # Good paragraph break found
            pages.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
        else:
            # Try sentence-ending punctuation: . ؟ ! ، ؛
            best = -1
            for sep in ['. ', '؟ ', '! ', '، ', '؛ ', '\n']:
                pos = chunk.rfind(sep)
                if pos > best:
                    best = pos
            if best > max_chars // 3:
                pages.append(remaining[:best + 1].strip())
                remaining = remaining[best + 1:].strip()
            else:
                # Hard cut at max_chars
                pages.append(remaining[:max_chars].strip())
                remaining = remaining[max_chars:].strip()
    
    if remaining:
        pages.append(remaining.strip())
    
    return [p for p in pages if p]


async def render_student_chapter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("path_subject")
    lesson = data.get("path_lesson")
    chapters = data.get("path_chapters")
    current_idx = data.get("path_current_idx", 0)
    current_page = data.get("path_current_page", 0)  # page within chapter
    
    if not chapters:
        if subject and lesson:
            chapters = await db.get_course_chapters(subject, lesson)
            await state.update_data(path_chapters=chapters)
            
    if not chapters:
        await callback.answer("⚠️ انتهت الجلسة أو تمت إعادة تشغيل البوت. يرجى البدء من جديد.", show_alert=True)
        return
        
    if current_idx >= len(chapters):
        # Completed all chapters!
        await render_study_path_completion(callback, state)
        return
        
    ch = chapters[current_idx]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    # Split chapter content into pages
    content_text = ch['content']
    pages = _split_into_pages(content_text)
    total_pages = len(pages)
    
    # Clamp current page
    if current_page >= total_pages:
        current_page = total_pages - 1
    if current_page < 0:
        current_page = 0
    
    is_last_page = (current_page == total_pages - 1)
    page_content = clean_islamic_salutations(pages[current_page])
    
    # Header
    chapter_label = f"{current_idx + 1} من {len(chapters)}"
    page_label = f" — صفحة {current_page + 1} / {total_pages}" if total_pages > 1 else ""
    
    cleaned_title = clean_islamic_salutations(ch['title'])
    text = (
        f"📖 <b>مسار القراءة التفاعلي - الدرس {lesson} ({sub_ar})</b>\n"
        f"📌 <b>{chapter_label} :</b>\n"
        f"<blockquote><b>{cleaned_title}</b></blockquote>"
        f"<i>{page_label}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Add page content inside blockquote
    blockquote_content = page_content
    
    # Vocabulary spoilers — only on last page, placed inside the blockquote
    if is_last_page and ch.get("vocabulary_spoilers"):
        v_spoilers = clean_islamic_salutations(ch['vocabulary_spoilers'].strip())
        blockquote_content += f"\n\n🔑 <b>مفاهيم ومصطلحات :</b> <tg-spoiler>{v_spoilers}</tg-spoiler>"
        
    text += f"<blockquote>{blockquote_content}</blockquote>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # Build buttons
    buttons = []
    
    # YouTube link — only on first page to avoid clutter
    if current_page == 0 and ch.get("youtube_link"):
        buttons.append([InlineKeyboardButton(text="🎥 مشاهدة الشرح بالفيديو (YouTube)", url=ch["youtube_link"])])
    
    # Comprehension question — only on last page
    if is_last_page:
        buttons.append([InlineKeyboardButton(text="❓ أجب عن سؤال الفهم لتجاوز هذا الجزء", callback_data=f"rev_study_q:{ch['id']}")])
    
    # Page navigation row (within chapter)
    page_nav = []
    if current_page > 0:
        page_nav.append(InlineKeyboardButton(text="◀️ الصفحة السابقة", callback_data=f"rev_study_page:{current_idx}:{current_page - 1}"))
    if not is_last_page:
        page_nav.append(InlineKeyboardButton(text="▶️ الصفحة التالية", callback_data=f"rev_study_page:{current_idx}:{current_page + 1}"))
    if page_nav:
        buttons.append(page_nav)
    
    # Chapter navigation row
    nav_row = []
    if current_idx > 0:
        nav_row.append(InlineKeyboardButton(text="⏮️ الجزء السابق", callback_data=f"rev_study_nav:{current_idx - 1}"))
    nav_row.append(InlineKeyboardButton(text="📋 الفهرس", callback_data="rev_study_syllabus"))
    nav_row.append(InlineKeyboardButton(text="🚪 خروج", callback_data="rev_study_exit"))
    buttons.append(nav_row)
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )



@router.callback_query(F.data == "rev_study_syllabus")
async def handle_rev_study_syllabus_btn(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await render_study_path_syllabus(callback, state)


@router.callback_query(F.data.startswith("rev_study_nav:"))
async def handle_rev_study_nav(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    idx = int(parts[1])
    # Reset page to 0 whenever switching chapters
    await state.update_data(path_current_idx=idx, path_current_page=0)
    await render_student_chapter(callback, state)


@router.callback_query(F.data.startswith("rev_study_page:"))
async def handle_rev_study_page(callback: CallbackQuery, state: FSMContext):
    """Navigate between pages within the same chapter."""
    await callback.answer()
    parts = callback.data.split(":")
    chapter_idx = int(parts[1])
    page_idx = int(parts[2])
    await state.update_data(path_current_idx=chapter_idx, path_current_page=page_idx)
    await render_student_chapter(callback, state)


@router.callback_query(F.data.startswith("rev_study_q:"))
async def handle_rev_study_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    chapter_id = int(callback.data.split(":")[1])
    
    q = await db.get_course_chapter_question(chapter_id)
    if not q:
        data = await state.get_data()
        idx = data.get("path_current_idx", 0)
        # Move to next chapter, reset page
        await state.update_data(path_current_idx=idx + 1, path_current_page=0)
        await render_student_chapter(callback, state)
        return
        
    await state.set_state(StudentStudyPathStates.answering_validation)
    await state.update_data(current_path_question=q)
    
    clean_q_question = clean_islamic_salutations(q['question'])
    text = (
        f"❓ <b>سؤال فهم واستيعاب :</b>\n\n"
        f"<blockquote>{clean_q_question}</blockquote>\n\n"
    )
    if q.get("hint"):
        # Ensure hint has tg-spoiler tags
        hint_text = clean_islamic_salutations(q["hint"])
        if "<tg-spoiler>" not in hint_text:
            hint_text = f"<tg-spoiler>{hint_text}</tg-spoiler>"
        text += f"💡 <b>تلميح للحل (انقر للرؤية) :</b>\n{hint_text}\n\n"
    
    choices = [
        ("a", clean_islamic_salutations(q["choice_a"])),
        ("b", clean_islamic_salutations(q["choice_b"]))
    ]
    if q.get("choice_c"):
        choices.append(("c", clean_islamic_salutations(q["choice_c"])))
    if q.get("choice_d"):
        choices.append(("d", clean_islamic_salutations(q["choice_d"])))
        
    buttons = []
    for letter, label in choices:
        buttons.append([InlineKeyboardButton(text=f"📍 {letter.upper()}) {label}", callback_data=f"rev_study_ans:{letter}")])
        
    buttons.append([InlineKeyboardButton(text="↩️ العودة لفقرة القراءة", callback_data="rev_study_back_read")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "rev_study_back_read")
async def handle_rev_study_back_read(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(StudentStudyPathStates.reading)
    await render_student_chapter(callback, state)


@router.callback_query(F.data.startswith("rev_study_ans:"))
async def handle_rev_study_answer(callback: CallbackQuery, state: FSMContext):
    user_choice = callback.data.split(":")[1]
    data = await state.get_data()
    q = data.get("current_path_question")
    idx = data.get("path_current_idx", 0)
    
    if not q:
        await callback.answer()
        return
        
    is_correct = (user_choice.lower() == q["correct_answer"].lower())
    
    if is_correct:
        await callback.answer("✅ إجابة صحيحة وممتازة! تابع القراءة.", show_alert=True)
        await state.set_state(StudentStudyPathStates.reading)
        # Move to next chapter, reset page to 0
        await state.update_data(path_current_idx=idx + 1, path_current_page=0)
        await render_student_chapter(callback, state)
    else:
        explanation = q['explanation'] or 'راجع فقرة القراءة جيداً لإيجاد الجواب الصحيح.'
        cleaned_explanation = clean_islamic_salutations(explanation)
        text = (
            f"❌ <b>إجابة خاطئة للأسف.</b>\n\n"
            f"💡 <b>الشرح والتفسير (انقر للرؤية) :</b>\n"
            f"<tg-spoiler>{cleaned_explanation}</tg-spoiler>"
        )
        buttons = [
            [InlineKeyboardButton(text="🔄 إعادة المحاولة", callback_data=f"rev_study_q:{q['chapter_id']}")],
            [InlineKeyboardButton(text="📖 العودة لفقرة القراءة", callback_data="rev_study_back_read")]
        ]
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )


async def render_study_path_completion(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subject = data.get("path_subject")
    lesson = data.get("path_lesson")
    
    await state.clear()
    
    # Check if there is a mind map available
    map_pages = await db.get_mind_map_pages(subject, lesson)
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    if map_pages:
        # Show mind map directly as synthesis
        total_pages = len(map_pages)
        file_id = map_pages[0]["file_id"]
        page_label = f" - الصفحة 1 / {total_pages}" if total_pages > 1 else ""
        caption = (
            f"🏆 <b>تهانينا! لقد أتممت قراءة الدرس {lesson} ({sub_ar}) بنجاح!</b>\n\n"
            f"🗺️ <b>الخريطة الذهنية (سنتييز) للدرس {lesson}:</b>\n"
            f"راجع الخريطة لتثبيت معلوماتك النهائية قبل خوض الاختبار التقييمي:"
        )
        
        buttons = [
            [InlineKeyboardButton(text="🎯 خوض الاختبار والتمارين لهذا الدرس", callback_data=f"study_path_launch_quiz:{subject}:{lesson}")],
            [InlineKeyboardButton(text="🚪 العودة لمكتبة المراجعة", callback_data=f"rev_sub:{subject}")]
        ]
        
        try:
            await callback.message.delete()
        except Exception:
            pass
            
        await _send_map_photo(
            callback.message.bot, 
            callback.from_user.id, 
            file_id, 
            caption, 
            InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    else:
        # No mind map, just regular completion screen
        text = (
            f"🏆 <b>تهانينا! لقد أتممت قراءة وفهم مسار الدرس {lesson} ({sub_ar}) بنجاح!</b>\n\n"
            f"لقد قرأت جميع الأجزاء وأجبت عن أسئلة الفهم بشكل صحيح.\n\n"
            f"🎯 <b>ما هي خطوتك التالية ؟</b>"
        )
        buttons = [
            [InlineKeyboardButton(text="🎯 خوض الاختبار والتمارين لهذا الدرس", callback_data=f"study_path_launch_quiz:{subject}:{lesson}")],
            [InlineKeyboardButton(text="🚪 العودة لمكتبة المراجعة", callback_data=f"rev_sub:{subject}")]
        ]
        
        try:
            await callback.message.delete()
        except Exception:
            pass
            
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "rev_study_exit")
async def handle_rev_study_exit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    subject = data.get("path_subject", "sira")
    lesson = data.get("path_lesson", 14)
    
    await state.clear()
    
    map_pages = await db.get_mind_map_pages(subject, lesson)
    has_map = len(map_pages) > 0
    resources = await db.get_lesson_resources(subject, lesson)
    has_sum = bool(resources and resources.get("summary_file_id"))
    trans_pages = await db.get_transcription_pages(subject, lesson)
    has_trans = len(trans_pages) > 0
    chapters = await db.get_course_chapters(subject, lesson)
    has_study_path = len(chapters) > 0

    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    text = (
        f"📖 <b>مكتبة المراجعة - الدرس {lesson} (مادة {sub_ar}):</b>\n\n"
        f"اختر الملف الذي تود تحميله أو عرضه:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.get_revision_resources_keyboard(subject, lesson, has_map, has_sum, has_trans, has_study_path=has_study_path),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=kb.get_revision_resources_keyboard(subject, lesson, has_map, has_sum, has_trans, has_study_path=has_study_path),
            parse_mode="HTML"
        )



@router.callback_query(F.data.startswith("study_path_launch_quiz:"))
async def handle_study_path_launch_quiz(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ جاري تحضير أسئلة الاختبار...")
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    # Directly set state and launch the quiz for this lesson
    from handlers.quiz import QuizStates, initialize_and_start_quiz
    
    await state.clear()
    await state.update_data(
        subject=subject,
        mode="lessons",
        selected_lessons=[lesson],
        settings={
            "timer": "unlimited",
            "correction": "immediate",
            "order": "random",
            "source": "all",
            "origin": "official"
        }
    )
    # Launch quiz using the standard quiz initiator
    await initialize_and_start_quiz(callback, state, await state.get_data())


# ── 7. SQL-BASED KEYWORD SEARCH ENGINE (NO AI) ──────────────────────────────────

@router.callback_query(F.data == "rev_study_search_start")
async def handle_rev_study_search_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(StudentStudyPathStates.searching_keyword)
    await callback.message.edit_text(
        "🔍 <b>البحث في محاور الدروس :</b>\n\n"
        "أرسل الكلمة أو العبارة التي تبحث عنها (مثال: <i>الزواج</i>، <i>المدينة</i>، <i>الخندق</i>):\n\n"
        "💡 <i>سأقوم بالبحث في نصوص الفصول والعناوين المضافة في قاعدة البيانات.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="main_revision")]
        ]),
        parse_mode="HTML"
    )


def balance_html_tags(html_str: str) -> str:
    if not html_str:
        return ""
    for tag in ["b", "i", "a"]:
        op = html_str.count(f"<{tag}")
        cl = html_str.count(f"</{tag}>")
        if op > cl:
            html_str += f"</{tag}>" * (op - cl)
        elif cl > op:
            html_str = f"<{tag}>" * (cl - op) + html_str
    return html_str



@router.message(StudentStudyPathStates.searching_keyword)
async def handle_rev_study_search_query(message: Message, state: FSMContext):
    keyword = (message.text or "").strip()
    if not keyword:
        await message.answer("⚠️ يرجى إدخال كلمة بحث صالحة.")
        return
        
    status_msg = await message.answer("🔍 <b>جاري البحث في تفريغات الدروس...</b>", parse_mode="HTML")
    results = await db.search_transcripts_local(keyword)
              
    if not results:
        try:
            await status_msg.delete()
        except:
            pass
        await message.answer(
            f"🔍 لم نعثر على أي نتائج للبحث عن: <b>\"{keyword}\"</b>\n\n"
            "يرجى محاولة البحث بكلمة أخرى, أو العودة للمكتبة:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 بحث جديد", callback_data="rev_study_search_start")],
                [InlineKeyboardButton(text="🚪 العودة للمكتبة", callback_data="main_revision")]
            ]),
            parse_mode="HTML"
        )
        return
        
    await state.set_state(StudentStudyPathStates.viewing_search_results)
    await state.update_data(search_results=results, search_keyword=keyword, search_page=0)
    
    try:
        await status_msg.delete()
    except:
        pass
        
    await render_search_result(message, state)


async def render_search_result(message_or_callback, state: FSMContext):
    data = await state.get_data()
    results = data.get("search_results", [])
    keyword = data.get("search_keyword", "")
    page = data.get("search_page", 0)
    
    if not results or page < 0 or page >= len(results):
        return
        
    row = results[page]
    total = len(results)
    
    subject = row['subject']
    course_number = row['course_number']
    course_name = row.get('course_name') or ""
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    cname_str = f" ({course_name})" if course_name else ""
    
    content = row['content'] or ""
    k_idx = content.find(keyword)
    if k_idx == -1:
        start = 0
        end = min(len(content), 150)
    else:
        start = max(0, k_idx - 50)
        end = min(len(content), k_idx + 150)
        
    snip = content[start:end].strip()
    if start > 0: snip = "..." + snip
    if end < len(content): snip = snip + "..."
    
    import html
    snip = html.escape(snip)
    snip = clean_islamic_salutations(snip)
    snip = highlight_arabic_keyword(snip, keyword)
    snip = balance_html_tags(snip)
    
    text = (
        f"🔍 <b>نتيجة البحث {page + 1} من {total}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 <b>مادة {sub_ar}</b>\n"
        f"🔖 <b>الدرس {course_number}{cname_str}</b>\n\n"
        f"<blockquote>« {snip} »</blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    # Buttons
    buttons = []
    
    # Row 1: Actions (Context + Video)
    action_row = [
        InlineKeyboardButton(
            text="📖 سياق التفريغ",
            callback_data=f"search_context:{row['subject']}:{row['course_number']}:{row['seconds']}"
        )
    ]
    
    youtube_base_url = await db.get_lesson_youtube_link(subject, course_number)
    if youtube_base_url:
        secs = int(row['seconds'])
        if "watch?v=" in youtube_base_url:
            youtube_url = f"{youtube_base_url}&t={secs}s"
        elif "youtu.be/" in youtube_base_url:
            youtube_url = f"{youtube_base_url}?t={secs}"
        else:
            youtube_url = f"{youtube_base_url}&t={secs}s"
            
        action_row.append(
            InlineKeyboardButton(
                text="🎥 الفيديو",
                url=youtube_url
            )
        )
    buttons.append(action_row)
    
    # Row 2: Pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"search_page:{page - 1}"))
    if page < total - 1:
        nav_row.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"search_page:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)
        
    # Row 3: Navigation
    buttons.append([
        InlineKeyboardButton(text="🔍 بحث جديد", callback_data="rev_study_search_start"),
        InlineKeyboardButton(text="🚪 العودة للمكتبة", callback_data="main_revision")
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=reply_markup, parse_mode="HTML")

@router.callback_query(StudentStudyPathStates.viewing_search_results, F.data.startswith("search_page:"))
async def handle_search_page_nav(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    page = int(callback.data.split(":")[1])
    await state.update_data(search_page=page)
    await render_search_result(callback, state)

@router.callback_query(F.data.startswith("search_context:"))
async def process_view_full_transcript_local(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    subject = parts[1]
    course_number = int(parts[2])
    seconds = int(parts[3])
    
    await callback.answer("⏳ جاري جلب السياق...")
    
    import aiosqlite
    from config import MAIN_DATABASE_PATH
    import os
    
    if not os.path.exists(MAIN_DATABASE_PATH):
        await callback.message.answer("❌ تعذر الوصول لقاعدة بيانات التفريغات.")
        return
        
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    async with aiosqlite.connect(MAIN_DATABASE_PATH) as db_main:
        db_main.row_factory = aiosqlite.Row
        
        async with db_main.execute(
            "SELECT timestamp, seconds, content FROM transcript_segments "
            "WHERE subject = ? AND course_number = ? AND seconds BETWEEN ? AND ? "
            "ORDER BY seconds ASC",
            (subject, course_number, seconds - 60, seconds + 120)
        ) as cursor:
            rows = await cursor.fetchall()
            
        if not rows:
            await callback.message.answer("❌ لم يتم العثور على سياق تفصيلي لهذا التوقيت.")
            return
            
        # Concatenate plain text instead of using AI to save cost and time
        cleaned_text = " ".join([r["content"].strip() for r in rows if r["content"]])
        cleaned_text = clean_islamic_salutations(cleaned_text)
        
        response_text = (
            f"📖 <b>التفريغ الكامل للسياق (نص الشيخ) :</b>\n"
            f"📍 <b>{sub_ar} - الدرس {course_number}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 <b>كلام الشيخ ياسين العمري :</b>\n"
            f"<blockquote><i>{cleaned_text}</i></blockquote>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
        )
            
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 بحث جديد", callback_data="rev_study_search_start"),
            InlineKeyboardButton(text="🚪 العودة للمكتبة", callback_data="main_revision")
        ]
    ])
    
    await callback.message.answer(
        text=response_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


class GuidedPathStates(StatesGroup):
    flashcards = State()


async def render_guided_flashcard(message_or_callback, state: FSMContext, show_answer: bool = False):
    data = await state.get_data()
    questions = data.get("flashcards_list", [])
    idx = data.get("flashcards_idx", 0)
    subject = data.get("flashcards_subj")
    lesson = data.get("flashcards_les")
    
    if not questions or idx >= len(questions):
        user_id = (message_or_callback.from_user.id 
                   if isinstance(message_or_callback, CallbackQuery) 
                   else message_or_callback.chat.id)
        await db.update_student_course_progress(user_id, subject, lesson, flashcards_done=1)
        
        text = (
            f"🎉 <b>أحسنت يا {callback.from_user.first_name}! لقد أكملت مراجعة جميع بطاقات الاستذكار للدرس {lesson}!</b>\n\n"
            f"تم تحديث تقدمك بنجاح. يمكنك الآن الانتقال إلى الخطوة التالية (الخريطة الذهنية)."
        )
        kb_next = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺️ الانتقال للخريطة الذهنية", callback_data=f"guided_step:{subject}:{lesson}:mindmap")],
            [InlineKeyboardButton(text="↩️ العودة لصفحة الدرس", callback_data=f"guided_path_les:{subject}:{lesson}")]
        ])
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(text, reply_markup=kb_next, parse_mode="HTML")
        else:
            await message_or_callback.answer(text, reply_markup=kb_next, parse_mode="HTML")
        return
        
    q = questions[idx]
    clean_question = clean_islamic_salutations(q["question"])
    
    total = len(questions)
    indicator = "🎴" * (idx + 1) + "⬜" * (total - idx - 1)
    
    if not show_answer:
        text = (
            f"🎴 <b>بطاقة الاستذكار {idx + 1} / {total}</b>\n"
            f"📊 {indicator}\n\n"
            f"🤔 <b>السؤال:</b>\n"
            f"<blockquote>{clean_question}</blockquote>\n\n"
            f"💡 <i>فكر في الإجابة ثم اضغط على زر الكشف لرؤية الإجابة الصحيحة.</i>"
        )
        kb_flash = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁️ كشف الإجابة", callback_data="guided_flash:reveal")],
            [InlineKeyboardButton(text="🚪 خروج للمسار", callback_data=f"guided_path_les:{subject}:{lesson}")]
        ])
    else:
        correct_letter = q["correct_answer"].lower()
        correct_text = q[f"choice_{correct_letter}"]
        clean_correct = clean_islamic_salutations(correct_text)
        explanation = q.get("explanation") or ""
        clean_explanation = clean_islamic_salutations(explanation)
        
        explanation_section = ""
        if clean_explanation:
            explanation_section = f"\n\n💬 <b>الشرح:</b>\n{clean_explanation}"
            
        text = (
            f"🎴 <b>بطاقة الاستذكار {idx + 1} / {total} (الجواب)</b>\n"
            f"📊 {indicator}\n\n"
            f"🤔 <b>السؤال:</b>\n"
            f"<blockquote>{clean_question}</blockquote>\n\n"
            f"✅ <b>الإجابة الصحيحة:</b>\n"
            f"<blockquote>{clean_correct}</blockquote>"
            f"{explanation_section}"
        )
        
        btn_text = "➡️ البطاقة التالية" if idx < total - 1 else "🏁 إنهاء البطاقات"
        kb_flash = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data="guided_flash:next")],
            [InlineKeyboardButton(text="↩️ إعادة عرض السؤال", callback_data="guided_flash:recto")],
            [InlineKeyboardButton(text="🚪 خروج للمسار", callback_data=f"guided_path_les:{subject}:{lesson}")]
        ])
        
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=kb_flash, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=kb_flash, parse_mode="HTML")


@router.callback_query(F.data == "library_subjects")
async def handle_library_subjects(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📚 <b>مكتبة المراجعة لأكاديمية الباجي:</b>\n\n"
        "اختر المادة الشرعية التي تود مراجعة ملخصاتها أو عرض خرائطها الذهنية:",
        reply_markup=kb.get_revision_subjects_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "guided_path_start")
async def handle_guided_path_start(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🚀 <b>المسار التوجيهي المنهجي:</b>\n\n"
        "اختر المادة التي ترغب في دراسة مسارها المنهجي الموجه خطوة بخطوة:",
        reply_markup=kb.get_guided_subjects_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("guided_path_sub:"))
async def handle_guided_path_sub(callback: CallbackQuery):
    await callback.answer()
    subject = callback.data.split(":")[1]
    
    lessons = await db.get_available_lessons(subject)
    lessons = sorted(lessons)
    
    progress_map = {}
    user_id = callback.from_user.id
    for l in lessons:
        prog = await db.get_student_course_progress(user_id, subject, l)
        progress_map[l] = prog
        
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    text = (
        f"🚀 <b>المسار التوجيهي المنهجي - مادة {sub_ar}:</b>\n\n"
        f"اختر الدرس الذي تود دراسته ومتابعته:\n"
        f"🟩 = مكتمل | 🟨 = قيد التقدم | ⬜ = لم يبدأ"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.get_guided_lessons_keyboard(subject, lessons, progress_map),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot.send_message(
            chat_id=callback.from_user.id,
            text=text,
            reply_markup=kb.get_guided_lessons_keyboard(subject, lessons, progress_map),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("guided_path_les:"))
async def handle_guided_path_les(callback: CallbackQuery, state: FSMContext):
    # Redirect directly to Active Study
    parts = callback.data.split(":")
    subject = parts[1]
    lesson_num = parts[2]
    
    # We forge a new callback.data to trick the other handler
    class FakeCallback:
        def __init__(self, cb):
            self.id = cb.id
            self.from_user = cb.from_user
            self.message = cb.message
            self.data = f"rev_study_path_start:{subject}:{lesson_num}"
            self._real_cb = cb
            
        async def answer(self, *args, **kwargs):
            return await self._real_cb.answer(*args, **kwargs)
            
    fake_cb = FakeCallback(callback)
    await handle_rev_study_path_start(fake_cb, state)



import html
import re
def format_gemini_markdown_to_html(text):
    if not text:
        return []
    
    # 1. Clean HTML escaping but preserve Gemini's <b> tags
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
    
    # 2. Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # 3. Headers: ## text
    text = re.sub(r'^#+\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # 4. Bullets: * text
    text = re.sub(r'^\s*[\*\-]\s+(.+)$', r'• \1', text, flags=re.MULTILINE)
    
    # 4.5 Spoilers: ||text||
    text = re.sub(r'\|\|(.*?)\|\|', r'<tg-spoiler>\1</tg-spoiler>', text)
    
    # 5. Split by sections and wrap in blockquotes
    parts = re.split(r'\n(?=\d+\.\s+🔹)', text)
    
    messages = []
    current_msg = ""
    
    for p in parts:
        p = p.strip()
        if not p:
            continue
            
        # Wrap section in blockquote
        if re.match(r'^\d+\.\s+🔹', p):
            p = f"<blockquote>{p}</blockquote>"
            
        # Check length
        if len(current_msg) + len(p) > 3800:
            messages.append(current_msg)
            current_msg = p + "\n\n"
        else:
            current_msg += p + "\n\n"
            
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
                await callback.message.answer(f"📑 <b>الملخص الشامل - {sub_ar} (درس {lesson})</b>\n\n{chunk}", parse_mode="HTML")
            else:
                await callback.message.answer(chunk, parse_mode="HTML")
                
        text_done = (
            f"🎉 <b>أحسنت يا {callback.from_user.first_name}! لقد أتممت قراءة الملخص للدرس {lesson}!</b>\n\n"
            f"أنت الآن جاهز لاختبار معلوماتك في الأسئلة الشاملة (التمارين الرسمية للدرس)."
        )
        kb_next = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 الانتقال للاختبار الشامل", callback_data=f"guided_step:{subject}:{lesson}:quiz")],
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
            f"🎉 <b>أحسنت يا {callback.from_user.first_name}! لقد أتممت قراءة الملخص للدرس {lesson}!</b>\n\n"
            f"أنت الآن جاهز لاختبار معلوماتك في الأسئلة الشاملة (التمارين الرسمية للدرس)."
        )
        kb_next = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 الانتقال للاختبار الشامل", callback_data=f"guided_step:{subject}:{lesson}:quiz")],
            [InlineKeyboardButton(text="↩️ العودة لصفحة الدرس", callback_data=f"guided_path_les:{subject}:{lesson}")]
        ])
        await callback.message.answer(text_done, reply_markup=kb_next, parse_mode="HTML")

@router.callback_query(F.data.startswith("guided_step:") & F.data.endswith(":flashcards"))
async def handle_guided_step_flashcards(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    questions = await db.get_questions_by_lesson_for_flashcards(subject, lesson)
    if not questions:
        user_id = callback.from_user.id
        await db.update_student_course_progress(user_id, subject, lesson, flashcards_done=1)
        await callback.message.edit_text(
            "⚠️ لا توجد أسئلة متوفرة كبطاقات استذكار لهذا الدرس حالياً.\n"
            "تم تمييز هذه الخطوة كمنجزة تلقائياً.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗺️ الانتقال للخريطة الذهنية", callback_data=f"guided_step:{subject}:{lesson}:mindmap")],
                [InlineKeyboardButton(text="↩️ العودة لصفحة الدرس", callback_data=f"guided_path_les:{subject}:{lesson}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    await state.set_state(GuidedPathStates.flashcards)
    await state.update_data(
        flashcards_list=questions,
        flashcards_idx=0,
        flashcards_subj=subject,
        flashcards_les=lesson
    )
    await render_guided_flashcard(callback, state, show_answer=False)


@router.callback_query(GuidedPathStates.flashcards, F.data.startswith("guided_flash:"))
async def handle_guided_flash_action(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    action = callback.data.split(":")[1]
    
    if action == "reveal":
        await render_guided_flashcard(callback, state, show_answer=True)
    elif action == "recto":
        await render_guided_flashcard(callback, state, show_answer=False)
    elif action == "next":
        data = await state.get_data()
        idx = data.get("flashcards_idx", 0)
        await state.update_data(flashcards_idx=idx + 1)
        await render_guided_flashcard(callback, state, show_answer=False)


@router.callback_query(F.data.startswith("guided_step:") & F.data.endswith(":mindmap"))
async def handle_guided_step_mindmap(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    user_id = callback.from_user.id
    
    pages = await db.get_mind_map_pages(subject, lesson)
    if not pages:
        await callback.answer("⚠️ عذراً، الخريطة الذهنية غير متوفرة لهذا الدرس.", show_alert=True)
        return
        
    await callback.answer()
    
    await db.update_student_course_progress(user_id, subject, lesson, mindmap_done=1)
    
    total_pages = len(pages)
    file_id = pages[0]["file_id"]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    page_label = f" - الصفحة 1 / {total_pages}" if total_pages > 1 else ""
    caption = (
        f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar}){page_label}</b>\n\n"
        f"🎉 ممتاز يا {callback.from_user.first_name}! لقد أنهيت الخطوة بنجاح. هل أنت مستعد للخطوة التالية؟"
    )
    
    buttons = [
        [InlineKeyboardButton(text="📝 الخطوة التالية: تمرين التقييم", callback_data=f"guided_step:{subject}:{lesson}:quiz")],
        [InlineKeyboardButton(text="↩️ العودة لصفحة الدرس", callback_data=f"guided_path_les:{subject}:{lesson}")]
    ]
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await _send_map_photo(
        callback.message.bot, 
        callback.from_user.id, 
        file_id, 
        caption, 
        InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("guided_step:") & F.data.endswith(":quiz"))
async def handle_guided_step_quiz(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ جاري تحضير أسئلة التمرين...")
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    from handlers.quiz import initialize_and_start_quiz
    
    await state.clear()
    await state.update_data(
        subject=subject,
        mode="lessons",
        selected_lessons=[lesson],
        guided_path_quiz=True,
        guided_subject=subject,
        guided_lesson=lesson,
        settings={
            "timer": "unlimited",
            "correction": "immediate",
            "limit": 5,
            "source": "all",
            "order": "random",
            "origin": "official",
            "diff": "all"
        }
    )
    data = await state.get_data()
    await initialize_and_start_quiz(callback, state, data)

@router.callback_query(F.data.startswith("exam_blanc_sub:"))
async def handle_exam_blanc_sub(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ جاري تجهيز الامتحان التجريبي...")
    subject = callback.data.split(":")[1]
    
    from handlers.quiz import initialize_and_start_quiz
    
    # Get all available lessons for the subject
    lessons = await db.get_available_lessons(subject)
    
    if not lessons:
        await callback.answer("⚠️ لا توجد دروس متاحة حالياً لهذه المادة لإجراء الامتحان التجريبي.", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        subject=subject,
        mode="lessons",
        selected_lessons=lessons,
        settings={
            "timer": "unlimited",
            "correction": "end",
            "limit": 20,
            "source": "all",
            "origin": "official",
            "diff": "all"
        }
    )
    data = await state.get_data()
    await initialize_and_start_quiz(callback, state, data)

@router.callback_query(F.data == "exam_blanc_start")
async def handle_exam_blanc_start(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🎓 <b>الامتحان التجريبي الشامل:</b>\n\n"
        "يرجى اختيار المادة التي تود اجتياز الامتحان التجريبي فيها (20 سؤالاً):",
        reply_markup=kb.get_exam_blanc_subjects_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "rev_search_start")
async def handle_rev_search_start_main(callback: CallbackQuery):
    # Route to the existing search handler
    await handle_rev_study_search_start(callback)
