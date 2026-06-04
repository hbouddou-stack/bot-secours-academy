from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
import keyboards as kb

router = Router(name="favorites_errors")

SUBJECT_MAP = {
    "fiqh": "الفقه",
    "sira": "السيرة النبوية",
    "nahw": "النحو",
    "aqeeda": "العقيدة"
}

ARABIC_CHARS = {"a": "أ", "b": "ب", "c": "ج", "d": "د"}

class BrowseStates(StatesGroup):
    browsing_favorites = State()
    browsing_errors = State()

# --- Browse Favorites Helpers & Handlers ---

async def show_favorite_browse(event, state: FSMContext):
    data = await state.get_data()
    fav_ids = data.get("fav_ids", [])
    idx = data.get("fav_idx", 0)
    
    if not fav_ids or idx >= len(fav_ids):
        msg = "⭐ ليس لديك أي أسئلة مفضلة حالياً."
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="fav_close")]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(msg, reply_markup=back_kb)
        else:
            await event.answer(msg, reply_markup=back_kb)
        return

    q_id = fav_ids[idx]
    q = await db.get_question_by_id(q_id)
    if not q:
        # Question deleted or missing, remove from list and recurse
        fav_ids.pop(idx)
        await state.update_data(fav_ids=fav_ids)
        await show_favorite_browse(event, state)
        return
        
    choices = {
        "a": q.get("choice_a"),
        "b": q.get("choice_b"),
        "c": q.get("choice_c"),
        "d": q.get("choice_d")
    }
    active_choices = {k: v for k, v in choices.items() if v and v.strip()}
    correct_choice = db.get_correct_choice_letter(q)
    
    subject_ar = SUBJECT_MAP.get(q.get("subject", "").lower(), q.get("subject"))
    progress_ratio = (idx + 1) / len(fav_ids)
    filled = int(progress_ratio * 10)
    progress_bar = "🟢" * filled + "⚪" * (10 - filled)
    
    question_clean = (q.get('question') or '').strip()
    text = f"❓ <b>{question_clean}</b>\n\n"
    
    for k, v in active_choices.items():
        if k == correct_choice:
            text += f"<blockquote><b>{ARABIC_CHARS[k]}) {v.strip()}</b> (✅ الإجابة الصحيحة)</blockquote>\n"
        else:
            text += f"<blockquote>{ARABIC_CHARS[k]}) {v.strip()}</blockquote>\n"
            
    text += "\n──────────────────\n"
    if q.get("explanation"):
        text += f"💬 <b>شرح الشيخ:</b>\n<i>{q.get('explanation').strip()}</i>\n\n"
        
    text += (
        f"⭐ <b>السؤال المفضّل {idx + 1} من {len(fav_ids)}</b> | <b>الدرس {q.get('course_number')}</b> ({subject_ar})\n"
        f"📊 {progress_bar} {int(progress_ratio * 100)}%"
    )
        
    has_prev = idx > 0
    has_next = idx < len(fav_ids) - 1
    
    reply_markup = kb.get_favorites_nav_keyboard(q_id, has_prev, has_next, len(fav_ids))
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=reply_markup, parse_mode="HTML")

@router.message(F.text == "⭐ المفضلة")
async def cmd_favorites(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    fav_ids = await db.get_user_favorites(user_id)
    if not fav_ids:
        text = "⭐ ليس لديك أسئلة مفضلة حالياً.\n\n<i>تستطيع إضافة الأسئلة للمفضلة أثناء خوض الاختبارات والحلول الفورية لكي تراجعها هنا.</i>"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="fav_close")]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=back_kb, parse_mode="HTML")
        return
        
    await state.set_state(BrowseStates.browsing_favorites)
    await state.update_data(fav_ids=fav_ids, fav_idx=0)
    await show_favorite_browse(event, state)

@router.callback_query(BrowseStates.browsing_favorites, F.data == "fav_next")
async def handle_fav_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("fav_idx", 0)
    fav_ids = data.get("fav_ids", [])
    if idx < len(fav_ids) - 1:
        await state.update_data(fav_idx=idx + 1)
        await show_favorite_browse(callback, state)
    await callback.answer()

@router.callback_query(BrowseStates.browsing_favorites, F.data == "fav_prev")
async def handle_fav_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("fav_idx", 0)
    if idx > 0:
        await state.update_data(fav_idx=idx - 1)
        await show_favorite_browse(callback, state)
    await callback.answer()

@router.callback_query(BrowseStates.browsing_favorites, F.data.startswith("fav_del_browse:"))
async def handle_fav_del_browse(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split(":")[1])
    await db.remove_favorite(callback.from_user.id, q_id)
    await callback.answer("🗑️ تم الحذف من المفضلة")
    
    # Reload and adjust index if necessary
    fav_ids = await db.get_user_favorites(callback.from_user.id)
    if not fav_ids:
        await state.clear()
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="fav_close")]
        ])
        await callback.message.edit_text("⭐ قائمة المفضلة فارغة الآن.", reply_markup=back_kb)
        return
        
    data = await state.get_data()
    idx = data.get("fav_idx", 0)
    if idx >= len(fav_ids):
        idx = len(fav_ids) - 1
        
    await state.update_data(fav_ids=fav_ids, fav_idx=idx)
    await show_favorite_browse(callback, state)

@router.callback_query(F.data == "fav_close")
async def handle_fav_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    await callback.message.edit_text(
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة المذاكرة والاختبارات:",
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining),
        parse_mode="HTML"
    )
    await callback.answer()

# --- Browse & Resolve Errors Helpers & Handlers ---

async def show_error_question(event, state: FSMContext):
    data = await state.get_data()
    err_ids = data.get("err_ids", [])
    idx = data.get("err_idx", 0)
    
    if not err_ids or idx >= len(err_ids):
        msg = "❌ لا يوجد لديك أخطاء مسجلة حالياً! أحسنت."
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="err_close")]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(msg, reply_markup=back_kb)
        else:
            await event.answer(msg, reply_markup=back_kb)
        return

    q_id = err_ids[idx]
    q = await db.get_question_by_id(q_id)
    if not q:
        err_ids.pop(idx)
        await state.update_data(err_ids=err_ids)
        await show_error_question(event, state)
        return
        
    choices = {
        "a": q.get("choice_a"),
        "b": q.get("choice_b"),
        "c": q.get("choice_c"),
        "d": q.get("choice_d")
    }
    active_choices = {k: v for k, v in choices.items() if v and v.strip()}
    
    subject_ar = SUBJECT_MAP.get(q.get("subject", "").lower(), q.get("subject"))
    progress_ratio = (idx + 1) / len(err_ids)
    filled = int(progress_ratio * 10)
    progress_bar = "🟢" * filled + "⚪" * (10 - filled)
    
    question_clean = (q.get('question') or '').strip()
    text = f"❓ <b>{question_clean}</b>\n\n"
    
    for k, v in active_choices.items():
        text += f"<blockquote><b>{ARABIC_CHARS[k]})</b> {v.strip()}</blockquote>\n"
        
    text += "\n──────────────────\n"
    text += "📝 <i>اختر الإجابة الصحيحة لتصحيح الخطأ وحذفه من قائمتك.</i>\n\n"
    text += (
        f"❌ <b>مراجعة الأخطاء {idx + 1} من {len(err_ids)}</b> | <b>الدرس {q.get('course_number')}</b> ({subject_ar})\n"
        f"📊 {progress_bar} {int(progress_ratio * 100)}%"
    )
    
    has_prev = idx > 0
    has_next = idx < len(err_ids) - 1
    
    reply_markup = kb.get_errors_nav_keyboard(q_id, active_choices, has_prev, has_next)
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=reply_markup, parse_mode="HTML")

@router.message(F.text == "❌ أخطائي")
async def cmd_errors(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    await _show_points_faibles_menu(event, user_id)

async def _show_points_faibles_menu(event, user_id: int):
    """Show the Points Faibles landing screen with per-subject / per-course breakdown."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    errors_by_course = await db.get_user_errors_by_subject_and_course(user_id)
    all_err_ids = await db.get_user_errors(user_id)
    
    if not all_err_ids:
        text = "❌ لا يوجد لديك أخطاء مسجلة حالياً! أحسنت ومبارك عليك. 🎉"
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="err_close")]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=back_kb, parse_mode="HTML")
        return
    
    # Build the breakdown text
    total_errors = len(all_err_ids)
    text = (
        f"❌ <b>نقاط ضعفي</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"لديك <b>{total_errors}</b> سؤال غير مُتقَن موزّع على الدروس التالية:\n\n"
    )
    
    # Build inline keyboard rows
    rows = []
    
    SUBJECT_LABELS_MAP = {
        "fiqh": "الفقه",
        "sira": "السيرة النبوية",
        "nahw": "النحو",
        "aqeeda": "العقيدة"
    }
    
    for subject in ["fiqh", "sira", "nahw", "aqeeda"]:
        if subject not in errors_by_course:
            continue
        subj_label = SUBJECT_LABELS_MAP.get(subject, subject)
        subj_total = sum(len(ids) for ids in errors_by_course[subject].values())
        text += f"📚 <b>{subj_label}</b> ({subj_total} خطأ):\n"
        
        for cn in sorted(errors_by_course[subject].keys()):
            count = len(errors_by_course[subject][cn])
            text += f"   • الدرس {cn}: <b>{count}</b> أخطاء ❌\n"
            rows.append([
                InlineKeyboardButton(
                    text=f"🎯 مراجعة {subj_label} - الدرس {cn} ({count} أخطاء)",
                    callback_data=f"err_drill:{subject}:{cn}"
                )
            ])
        text += "\n"
    
    # Row to review all errors at once
    rows.insert(0, [
        InlineKeyboardButton(
            text=f"📋 مراجعة جميع الأخطاء دفعةً واحدة ({total_errors})",
            callback_data="err_all"
        )
    ])
    rows.append([InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="err_close")])
    
    kb_markup = InlineKeyboardMarkup(inline_keyboard=rows)
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb_markup, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb_markup, parse_mode="HTML")

@router.callback_query(F.data == "err_all")
async def handle_err_all(callback: CallbackQuery, state: FSMContext):
    """Launch error review for ALL errors."""
    await state.clear()
    user_id = callback.from_user.id
    err_ids = await db.get_user_errors(user_id)
    await callback.answer()
    if not err_ids:
        await callback.message.edit_text("🎉 لا توجد أخطاء! أحسنت.")
        return
    await state.set_state(BrowseStates.browsing_errors)
    await state.update_data(err_ids=err_ids, err_idx=0)
    await show_error_question(callback, state)

@router.callback_query(F.data.startswith("err_drill:"))
async def handle_err_drill(callback: CallbackQuery, state: FSMContext):
    """Launch error review for a specific subject + course."""
    await state.clear()
    parts = callback.data.split(":")
    subject = parts[1]
    cn = int(parts[2])
    user_id = callback.from_user.id
    await callback.answer()
    
    errors_by_course = await db.get_user_errors_by_subject_and_course(user_id)
    err_ids = errors_by_course.get(subject, {}).get(cn, [])
    
    if not err_ids:
        await callback.message.edit_text("🎉 لا توجد أخطاء في هذا الدرس بعد الآن!")
        return
    
    await state.set_state(BrowseStates.browsing_errors)
    await state.update_data(err_ids=err_ids, err_idx=0)
    await show_error_question(callback, state)

@router.callback_query(BrowseStates.browsing_errors, F.data == "err_next")
async def handle_err_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("err_idx", 0)
    err_ids = data.get("err_ids", [])
    if idx < len(err_ids) - 1:
        await state.update_data(err_idx=idx + 1)
        await show_error_question(callback, state)
    await callback.answer()

@router.callback_query(BrowseStates.browsing_errors, F.data == "err_prev")
async def handle_err_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("err_idx", 0)
    if idx > 0:
        await state.update_data(err_idx=idx - 1)
        await show_error_question(callback, state)
    await callback.answer()

@router.callback_query(BrowseStates.browsing_errors, F.data.startswith("err_ans:"))
async def handle_err_ans(callback: CallbackQuery, state: FSMContext):
    # Format: err_ans:{q_id}:{choice}
    parts = callback.data.split(":")
    q_id = int(parts[1])
    choice = parts[2]
    
    q = await db.get_question_by_id(q_id)
    if not q:
        await callback.answer("⚠️ حدث خطأ ما. السؤال لم يعد موجوداً.")
        return
        
    correct_choice = db.get_correct_choice_letter(q)
    user_id = callback.from_user.id
    
    if choice == correct_choice:
        # Correct answer solves the error!
        subj_for_q = q.get("subject", "").lower().strip()
        cn_for_q = q.get("course_number")
        
        await db.remove_error(user_id, q_id)
        
        # Contextual feedback — count remaining errors in the same course
        errors_by_course = await db.get_user_errors_by_subject_and_course(user_id)
        SUBJECT_LABELS_LOCAL = {"fiqh": "الفقه", "sira": "السيرة النبوية", "nahw": "النحو", "aqeeda": "العقيدة"}
        remaining_in_course = len(errors_by_course.get(subj_for_q, {}).get(cn_for_q, []))
        subj_ar = SUBJECT_LABELS_LOCAL.get(subj_for_q, subj_for_q)
        
        if remaining_in_course == 0:
            feedback = f"✅ أحسنت! تم حذف الخطأ. لقد أتقنت جميع أخطاء {subj_ar} - الدرس {cn_for_q} 🎊"
        elif remaining_in_course == 1:
            feedback = f"✅ أحسنت! تم حذف الخطأ. تبقّى سؤال واحد فقط في {subj_ar} - الدرس {cn_for_q} 💪"
        else:
            feedback = f"✅ أحسنت! تم حذف الخطأ. تبقّى {remaining_in_course} أخطاء في {subj_ar} - الدرس {cn_for_q}"
        
        await callback.answer(feedback, show_alert=True)
        
        # Refresh errors list
        err_ids = await db.get_user_errors(user_id)
        if not err_ids:
            await state.clear()
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            back_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة للقائمة الرئيسية", callback_data="err_close")]
            ])
            await callback.message.edit_text("🎉 مبارك! لقد قمت بحل جميع الأخطاء بنجاح.", reply_markup=back_kb)
            return
            
        data = await state.get_data()
        idx = data.get("err_idx", 0)
        if idx >= len(err_ids):
            idx = len(err_ids) - 1
            
        await state.update_data(err_ids=err_ids, err_idx=idx)
        await show_error_question(callback, state)
    else:
        # Incorrect answer
        await callback.answer("❌ إجابة خاطئة! حاول مجدداً لمحو هذا الخطأ.", show_alert=True)

@router.callback_query(F.data == "err_close")
async def handle_err_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    await callback.message.edit_text(
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة المذاكرة والاختبارات:",
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining),
        parse_mode="HTML"
    )
    await callback.answer()

