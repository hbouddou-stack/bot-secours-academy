import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
import keyboards as kb
from config import TELEGRAM_ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router(name="admin")

SUBJECT_MAP = {
    "fiqh": "الفقه",
    "sira": "السيرة النبوية",
    "nahw": "النحو",
    "aqeeda": "العقيدة"
}

SUBJECT_TEACHERS = {
    "sira": "الشيخ ياسين العمري",
    "fiqh": "الشيخ",
    "nahw": "الشيخ",
    "aqeeda": "الشيخ"
}

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_admin_reply = State()
    waiting_for_status_decision = State()
    waiting_for_proposal_rejection_reason = State()

class AdminManagementStates(StatesGroup):
    waiting_for_new_admin_id = State()
    waiting_for_new_admin_name = State()

class AdminQuestionEditStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_a = State()
    waiting_for_b = State()
    waiting_for_c = State()
    waiting_for_d = State()
    waiting_for_correct = State()

class AdminQuestionFactoryStates(StatesGroup):
    waiting_for_model = State()
    waiting_for_count = State()
    waiting_for_instruction = State()
    reviewing_questions = State()
    waiting_for_subject = State()
    waiting_for_course = State()
    editing_question = State()


def is_admin(user_id: int) -> bool:
    # Check config list first
    if user_id in TELEGRAM_ADMIN_IDS:
        return True
    # Check SQLite databases synchronously
    import sqlite3
    import os
    from config import DATABASE_PATH, MAIN_DATABASE_PATH
    # Try local database
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (user_id,))
        res = c.fetchone()
        conn.close()
        if res:
            return True
    except Exception:
        pass
    # Try main database
    if MAIN_DATABASE_PATH and os.path.exists(MAIN_DATABASE_PATH):
        try:
            conn = sqlite3.connect(MAIN_DATABASE_PATH)
            c = conn.cursor()
            c.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (user_id,))
            res = c.fetchone()
            conn.close()
            if res:
                return True
        except Exception:
            pass
    return False

async def _get_admin_keyboard(user_id: int) -> kb.InlineKeyboardMarkup:
    pending_count = await db.get_pending_reports_count()
    pending_props = len(await db.get_pending_proposals())
    role = await db.get_admin_role(user_id)
    show_settings = (role in ("super_admin", "backup_admin"))
    return kb.get_admin_panel_keyboard(pending_reports=pending_count, pending_proposals=pending_props, show_settings=show_settings)

# --- Emergency Purge Command ---
@router.message(Command("purge_course"))
async def cmd_purge_course(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("⚠️ الاستخدام الصحيح:\n`/purge_course fiqh 17`", parse_mode="Markdown")
        return
        
    subject = parts[1].lower()
    try:
        course_number = int(parts[2])
    except ValueError:
        await message.answer("⚠️ رقم الدرس يجب أن يكون رقماً.")
        return
        
    import aiosqlite
    from config import DATABASE_PATH
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            # Delete questions
            async with db_conn.execute("DELETE FROM questions WHERE subject = ? AND course_number = ?", (subject, course_number)) as cur:
                deleted_q = cur.rowcount
            # Delete resources
            async with db_conn.execute("DELETE FROM lesson_resources WHERE subject = ? AND course_number = ?", (subject, course_number)) as cur:
                deleted_r = cur.rowcount
            await db_conn.commit()
            
        await message.answer(
            f"✅ تم الحذف بنجاح!\n\n"
            f"🗑️ الأسئلة المحذوفة: {deleted_q}\n"
            f"🗑️ الموارد المحذوفة: {deleted_r}\n\n"
            f"يمكنك الآن إعادة توليدها من (مصنع الأسئلة IA)."
        )
    except Exception as e:
        await message.answer(f"❌ حدث خطأ أثناء الحذف:\n{str(e)}")

# --- Open Admin Panel ---

@router.message(Command("admin"))
@router.message(F.text == "⚙️ الإدارة")
@router.message(F.text == "🛠️ وضع المشرف")
async def cmd_admin(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    if not is_admin(user_id):
        return
        
    import os
    text = (
        "🛠️ <b>مرحباً بك في لوحة الإدارة الخاصة بالبوت البديل:</b>\n\n"
        "يمكنك من هنا الاطلاع على إحصائيات الاستخدام، إدارة الرسائل والبلاغات، أو إرسال الإعلانات."
    )
    
    admin_webapp = os.getenv("ADMIN_WEBAPP_URL") or "http://localhost:8082/admin"
    if not admin_webapp.startswith("https"):
        text += f"\n\n🖥️ <b>رابط لوحة التحكم العام للمشرف:</b>\n🔗 <a href='{admin_webapp}'>{admin_webapp}</a>"
        
    reply_markup = await _get_admin_keyboard(user_id)
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=reply_markup, parse_mode="HTML")

# --- Settings & Navigation Toggles ---

@router.callback_query(F.data == "admin_settings_menu")
async def handle_admin_settings_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    role = await db.get_admin_role(user_id)
    show_mgmt = (role == "super_admin")
    restrict_val = await db.get_setting("restrict_to_academy_group", "True") == "True"
    display_pref = await db.get_admin_display_preference(user_id)
    
    await callback.message.edit_text(
        "⚙️ <b>إعدادات النظام والتحكم:</b>\n\n"
        "اختر الإجراء المطلوب من القائمة أدناه:",
        reply_markup=kb.get_admin_settings_keyboard(
            restrict_active=restrict_val,
            show_admin_mgmt=show_mgmt,
            display_pref=display_pref
        ),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "admin_toggle_pref_display")
async def handle_admin_toggle_pref_display(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    current_pref = await db.get_admin_display_preference(user_id)
    new_pref = "category_first" if current_pref == "grid" else "grid"
    await db.set_admin_display_preference(user_id, new_pref)
    
    ticket_detail_level = await db.get_setting("ticket_detail_level", "compact")
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_dir_display_keyboard(new_pref, ticket_detail_level, show_ticket_level=True)
    )
    await callback.answer(f"🔄 تم تغيير طريقة العرض إلى: {'جدول 📊' if new_pref == 'grid' else 'قائمة 📂'}")


@router.callback_query(F.data == "admin_toggle_ticket_level")
async def handle_admin_toggle_ticket_level(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    current_level = await db.get_setting("ticket_detail_level", "compact")
    new_level = "hidden" if current_level == "compact" else "compact"
    await db.set_setting("ticket_detail_level", new_level)
    
    display_pref = await db.get_admin_display_preference(callback.from_user.id)
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_dir_display_keyboard(display_pref, new_level, show_ticket_level=True)
    )
    await callback.answer(f"🔄 تم تغيير مستوى التفاصيل الافتراضي إلى: {'معاينة خفيفة 👁️' if new_level == 'compact' else 'مخفي بالكامل 🔒'}")

@router.callback_query(F.data.startswith("admin_reports_cat:"))
async def handle_admin_reports_cat(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    category = callback.data.split(":")[1]
    matrix_counts = await db.get_matrix_counts()
    cat_counts = matrix_counts.get(category, {"pending": 0, "in_progress": 0, "resolved": 0})
    
    cat_labels = {
        "tech": "🚨 مشاكل تقنية",
        "question_error": "📚 خطأ سؤال",
        "expl_error": "⚠️ خطأ شرح",
        "course_question": "❓ سؤال مقرر",
        "suggestion": "💡 اقتراح/رأي"
    }
    label = cat_labels.get(category, category)
    
    text = (
        f"📂 <b>قسم: {label}</b>\n\n"
        "اختر حالة البلاغات التي ترغب في استعراضها:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_category_status_keyboard(category, cat_counts),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_matrix_list:"))
async def handle_admin_matrix_list(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    category = parts[1]
    status = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 1
    
    current_filter = f"{category}:{status}"
    await state.update_data(admin_rep_filter=current_filter, admin_rep_page=page)
    
    reports = await db.get_reports_by_category_and_status(category, status)
    
    cat_labels = {
        "tech": "🚨 مشاكل تقنية",
        "question_error": "📚 خطأ سؤال",
        "expl_error": "⚠️ خطأ شرح",
        "course_question": "❓ سؤال مقرر",
        "suggestion": "💡 اقتراح/رأي"
    }
    status_labels = {
        "pending": "🔴 غير معالجة",
        "in_progress": "⏳ قيد المراجعة",
        "resolved": "✅ معالجة"
    }
    
    cat_label = cat_labels.get(category, category)
    status_label = status_labels.get(status, status)
    
    if not reports:
        text = (
            f"📋 <b>قائمة البلاغات: {cat_label} ({status_label})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>✨ لا توجد بلاغات في هذا القسم حالياً.</i>"
        )
    else:
        text = (
            f"📋 <b>قائمة البلاغات: {cat_label} ({status_label})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"اختر أي بلاغ من الجدول أدناه لمراجعته والرد عليه:"
        )
        
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_reports_list_keyboard(reports, current_filter, page=page),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_back_panel")
async def handle_admin_back_panel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await cmd_admin(callback, state)

@router.callback_query(F.data == "admin_switch_student")
async def handle_admin_switch_student(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer("🎓 تم الانتقال لوضع الطالب")
    await state.clear()
    
    user = await db.get_user(user_id)
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    
    from handlers.start import get_user_greeting
    greeting = get_user_greeting(user) if user else "يا طالبنا العزيز"
    welcome_text = (
        f"مرحباً بك مجدداً {greeting}! 🎓\n\n"
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة المذاكرة والاختبارات:"
    )
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=kb.get_main_inline_keyboard(is_admin=True, remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )

# --- Statistics Handler ---

@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    await callback.answer("⏳ جاري تحميل الإحصائيات...")
    stats = await db.get_admin_stats()
    
    text = (
        "📊 <b>إحصائيات استخدام البوت البديل:</b>\n\n"
        f"• الطلاب المسجلين بالبوت: <b>{stats['users_total']}</b> طالب\n"
        f"• الطلاب النشطين (الذين حلوا أسئلة): <b>{stats['active_total']}</b> طالب\n"
        f"• الطلاب النشطين خلال الـ 24 ساعة الماضية: <b>{stats['active_24h']}</b> طالب\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📚 <b>الدروس الأكثر تفاعلاً وممارسة:</b>\n"
    )
    
    for r in stats["lessons_practice"][:3]:
        text += f"• الدرس {r['course_number']}: تم حل <b>{r['practice_count']}</b> سؤالاً.\n"
    if not stats["lessons_practice"]:
        text += "• لا يوجد تفاعل بعد.\n"
        
    text += (
        "\n🗂️ <b>المواد الأكثر تفاعلاً وممارسة:</b>\n"
    )
    for r in stats["subjects_practice"][:3]:
        sub_ar = SUBJECT_MAP.get(r['subject'], r['subject'])
        text += f"• {sub_ar}: تم حل <b>{r['practice_count']}</b> سؤالاً.\n"
    if not stats["subjects_practice"]:
        text += "• لا يوجد تفاعل بعد.\n"
        
    text += (
        "\n⚠️ <b>الأسئلة الأكثر صعوبة (الأكثر خطأً):</b>\n"
    )
    for idx, r in enumerate(stats["most_failed"][:3]):
        sub_ar = SUBJECT_MAP.get(r['subject'], r['subject'])
        q_snippet = (r['question'] or '').strip()
        if len(q_snippet) > 60:
            q_snippet = q_snippet[:60] + "..."
        text += f"<b>{idx+1}.</b> <i>{q_snippet}</i>\n"
        text += f"   (المادة: {sub_ar} | الدرس {r['course_number']} | أخطاء: <b>{r['fail_count']}</b>)\n"
    if not stats["most_failed"]:
        text += "• لا توجد أخطاء مسجلة بعد.\n"
        
    await callback.message.edit_text(
        text,
        reply_markup=await _get_admin_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )

# --- Broadcast Handlers ---

@router.callback_query(F.data == "admin_broadcast")
async def handle_admin_broadcast_init(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text(
        "📢 <b>إرسال إعلان للطلاب:</b>\n\n"
        "يرجى كتابة نص الرسالة (الإعلان) التي تود إرسالها إلى جميع الطلاب المسجلين بالبوت.\n"
        "يمكنك استخدام وسوم HTML البسيطة مثل <code>&lt;b&gt;</code> و <code>&lt;i&gt;</code>.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast)
async def handle_broadcast_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    broadcast_text = message.text
    await state.update_data(broadcast_text=broadcast_text)
    
    await message.answer(
        "📝 <b>معاينة الإعلان:</b>\n\n"
        f"{broadcast_text}\n\n"
        "⚠️ هل تريد إرسال هذا الإعلان الآن لجميع الطلاب؟",
        reply_markup=kb.get_broadcast_confirm_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_broad_confirm")
async def handle_admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    await state.clear()
    
    if not broadcast_text:
        await callback.message.edit_text("❌ لم يتم العثور على نص الإعلان. تم إلغاء العملية.")
        return
        
    await callback.message.edit_text("⏳ جاري بدء إرسال الإعلان للجميع...")
    await callback.answer()
    
    user_ids = await db.get_all_user_ids()
    success_count = 0
    failed_count = 0
    
    for uid in user_ids:
        # Avoid sending to admins themselves if they don't want to, but it's safe to send to everyone
        try:
            await callback.message.bot.send_message(
                chat_id=uid,
                text=broadcast_text,
                parse_mode="HTML"
            )
            success_count += 1
            await db.add_broadcast_report(uid, broadcast_text)
        except Exception as e:
            failed_count += 1
            logger.warning(f"Failed to send broadcast to user {uid}: {e}")
            
    await callback.message.answer(
        "🏁 <b>اكتمل إرسال الإعلان بنجاح!</b>\n\n"
        f"• تم الإرسال بنجاح إلى: <b>{success_count}</b> طالب.\n"
        f"• فشل الإرسال (حظر البوت أو خطأ): <b>{failed_count}</b> طالب.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_broad_cancel")
async def handle_admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    await state.clear()
    await callback.message.edit_text(
        "❌ تم إلغاء الإرسال والعودة للوحة الإدارة.",
        reply_markup=await _get_admin_keyboard(callback.from_user.id)
    )
    await callback.answer()

@router.callback_query(F.data == "admin_close")
async def handle_admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "admin_sync_questions")
async def handle_admin_sync_questions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    await callback.answer("⏳ جاري المزامنة...")
    await callback.message.edit_text("⏳ جاري سحب الأسئلة والتحديثات من قاعدة البيانات الرئيسية ومن Google Sheets...")
    
    from scripts.sync_questions import sync_from_local_db, sync_from_gsheets
    
    db_success = await sync_from_local_db()
    gs_success = await sync_from_gsheets()
    
    if db_success or gs_success:
        await callback.message.edit_text(
            "✅ <b>تمت المزامنة بنجاح !</b>\n\n"
            f"• مزامنة قاعدة البيانات الرئيسية: {'مكتملة ✅' if db_success else 'فشلت ❌'}\n"
            f"• مزامنة Google Sheets: {'مكتملة ✅' if gs_success else 'فشلت ❌'}\n\n"
            "تم تحديث جميع الأسئلة والإجابات والتفسيرات في البوت البديل.",
            reply_markup=await _get_admin_keyboard(callback.from_user.id),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ <b>فشلت المزامنة !</b>\n\n"
            "يرجى التحقق من الاتصال بالإنترنت والملفات وسجلات النظام.",
            reply_markup=await _get_admin_keyboard(callback.from_user.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin_toggle_restrict")
async def handle_admin_toggle_restrict(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    current_val = await db.get_setting("restrict_to_academy_group", "True") == "True"
    new_val = not current_val
    await db.set_setting("restrict_to_academy_group", str(new_val))
    
    ai_disabled = await db.get_setting("disable_ai_for_students", "False") == "True"
    
    status_text = "🔒 تم تفعيل تقييد الدخول للطلاب فقط." if new_val else "🔓 تم فتح الدخول للجميع (وضع التجربة)."
    await callback.answer(status_text, show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=kb.get_admin_dir_security_keyboard(new_val, ai_disabled=ai_disabled))


@router.callback_query(F.data == "admin_toggle_ai_questions")
async def handle_admin_toggle_ai_questions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    current_val = await db.get_setting("disable_ai_for_students", "False") == "True"
    new_val = not current_val
    await db.set_setting("disable_ai_for_students", str(new_val))
    
    restrict_val = await db.get_setting("restrict_to_academy_group", "True") == "True"
    
    status_text = "🚫 تم إيقاف أسئلة الذكاء الاصطناعي للطلاب." if new_val else "✨ تم تفعيل أسئلة الذكاء الاصطناعي للطلاب."
    await callback.answer(status_text, show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=kb.get_admin_dir_security_keyboard(restrict_val, ai_disabled=new_val))


@router.callback_query(F.data.startswith("admin_group_details:"))
async def handle_admin_group_details_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    report_id = int(parts[1])
    action = parts[2] # "show" or "hide"
    
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    show_full = (action == "show")
    
    from handlers.support import format_admin_group_ticket_text, extract_timestamp_from_report
    ticket_text = format_admin_group_ticket_text(report, show_full=show_full)
    
    status = report.get("status", "pending")
    claimed_by = report.get("claimed_by") or ""
    
    original_text = callback.message.text or ""
    extra_suffix = ""
    if "قيد المعالجة بواسطة" in original_text:
        for line in original_text.split("\n"):
            if "قيد المعالجة بواسطة" in line:
                extra_suffix = f"\n\n{line}"
                break
    elif "تم حل البلاغ" in original_text:
        for line in original_text.split("\n"):
            if "تم حل البلاغ" in line:
                extra_suffix = f"\n\n{line}"
                break
    elif "تم رفض البلاغ" in original_text:
        for line in original_text.split("\n"):
            if "تم رفض البلاغ" in line:
                extra_suffix = f"\n\n{line}"
                break
                
    ticket_text = ticket_text + extra_suffix
    
    q_id = report.get("question_id")
    has_question = q_id and q_id > 0
    timestamp_url, timestamp_display = extract_timestamp_from_report(report)
    
    new_kb = kb.get_admin_group_ticket_keyboard(
        report_id,
        has_question=has_question,
        status=status,
        claimed_by=claimed_by,
        timestamp_url=timestamp_url,
        timestamp_display=timestamp_display,
        show_details=show_full
    )
    
    try:
        await callback.message.edit_text(text=ticket_text, reply_markup=new_kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error toggling ticket details: {e}")
        
    await callback.answer()


# --- Admin Report Actions (Support Ticket Interactive Buttons) ---

# --- Admin Report Actions (Support Ticket Interactive Buttons) ---

@router.callback_query(F.data.startswith("admin_rep_claim:"))
async def handle_admin_report_claim(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    report_id = int(callback.data.split(":")[1])
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    admin_name = callback.from_user.full_name
    await db.claim_question_report(report_id, admin_name)
    
    # Update original message card text in support group
    original_text = callback.message.text or ""
    updated_text = (
        original_text + "\n\n"
        f"🟡 <b>قيد المعالجة بواسطة المشرف: {admin_name}</b>"
    )
    
    has_question = bool(report.get("question_id"))
    from handlers.support import extract_timestamp_from_report
    timestamp_url, timestamp_display = extract_timestamp_from_report(report)
    
    # Update buttons to show claimed status (remove claim button)
    new_kb = kb.get_admin_group_ticket_keyboard(
        report_id, 
        has_question=has_question, 
        status='in_progress', 
        claimed_by=admin_name,
        timestamp_url=timestamp_url,
        timestamp_display=timestamp_display
    )
    
    try:
        await callback.message.edit_text(text=updated_text, reply_markup=new_kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error claiming ticket in group: {e}")
        
    await callback.answer(f"🟡 تم استلام البلاغ #{report_id} بنجاح.")


@router.callback_query(F.data.startswith("admin_rep_quick_reject:"))
async def handle_admin_report_quick_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    report_id = int(callback.data.split(":")[1])
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    admin_name = callback.from_user.full_name
    # Update status in DB
    await db.update_question_report_status(report_id, 'rejected', 'السؤال صحيح تماماً ولا توجد فيه أي أخطاء.')
    
    # Notify student
    student_id = report["user_id"]
    try:
        notify_text = (
            f"📢 <b>تحديث بخصوص بلاغك حول السؤال #{report['question_id']}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>الحالة: تم رفض البلاغ</b>\n\n"
            f"💬 السؤال صحيح تماماً بعد مراجعته وتدقيقه من قبل الإدارة."
        )
        await callback.bot.send_message(chat_id=student_id, text=notify_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not notify student {student_id}: {e}")
        
    # Update original card text
    original_text = callback.message.text or ""
    updated_text = (
        original_text + "\n\n"
        f"❌ <b>تم رفض البلاغ (السؤال صحيح) بواسطة المشرف: {admin_name}</b>"
    )
    
    try:
        await callback.message.edit_text(text=updated_text, reply_markup=None, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error quick rejecting ticket in group: {e}")
        
    await callback.answer("❌ تم رفض البلاغ وتنبيه الطالب.")


@router.callback_query(F.data.startswith("admin_rep_resolve:"))
async def handle_admin_report_resolve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    report_id = int(callback.data.split(":")[1])
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    # Update status to resolved
    await db.update_question_report_status(report_id, 'resolved', 'تم تصحيح الخطأ.')
    
    # Format dynamic subject
    if report.get("report_type") == "expl_error":
        subject_text = f"شرح الشيخ للسؤال #{report['question_id']}"
    elif report.get("question_id"):
        subject_text = f"السؤال #{report['question_id']}"
    else:
        subject_text = f"البلاغ #{report_id}"

    # Notify student
    student_id = report["user_id"]
    try:
        notify_text = (
            f"📢 <b>تحديث بخصوص بلاغك حول {subject_text}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>الحالة: تم الحل وتعديل المحتوى</b>\n\n"
            f"💬 شكراً لك على تنبيهك! تم تصحيح الخطأ وتحديث المحتوى بنجاح."
        )
        await callback.bot.send_message(chat_id=student_id, text=notify_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not notify student {student_id}: {e}")
        
    # Edit the admin support ticket to remove buttons
    admin_name = callback.from_user.full_name
    updated_text = (
        callback.message.text + "\n\n"
        f"✅ <b>تم حل البلاغ وتصحيحه بواسطة المشرف: {admin_name}</b>"
    )
    await callback.message.edit_text(text=updated_text, reply_markup=None, parse_mode="HTML")
    await callback.answer("✅ تم حل البلاغ وتنبيه الطالب.")


@router.callback_query(F.data.startswith("admin_rep_reject:"))
async def handle_admin_report_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    report_id = int(callback.data.split(":")[1])
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    # Update status to rejected
    await db.update_question_report_status(report_id, 'rejected', 'المحتوى الحالي صحيح.')
    
    # Format dynamic subject
    if report.get("report_type") == "expl_error":
        subject_text = f"شرح الشيخ للسؤال #{report['question_id']}"
    elif report.get("question_id"):
        subject_text = f"السؤال #{report['question_id']}"
    else:
        subject_text = f"البلاغ #{report_id}"

    # Notify student
    student_id = report["user_id"]
    try:
        notify_text = (
            f"📢 <b>تحديث بخصوص بلاغك حول {subject_text}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>الحالة: تم رفض البلاغ / المحتوى صحيح</b>\n\n"
            f"💬 تمت مراجعة البلاغ وهو غير دقيق أو أن المحتوى الحالي صحيح تماماً."
        )
        await callback.bot.send_message(chat_id=student_id, text=notify_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not notify student {student_id}: {e}")
        
    # Edit the admin support ticket to remove buttons
    admin_name = callback.from_user.full_name
    updated_text = (
        callback.message.text + "\n\n"
        f"❌ <b>تم رفض البلاغ بواسطة المشرف: {admin_name}</b>"
    )
    await callback.message.edit_text(text=updated_text, reply_markup=None, parse_mode="HTML")
    await callback.answer("❌ تم رفض البلاغ وتنبيه الطالب.")


@router.callback_query(F.data.startswith("admin_rep_edit:"))
async def handle_admin_report_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    report_id = int(callback.data.split(":")[1])
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    admin_id = callback.from_user.id
    
    try:
        # Save edit context in FSM state of the admin's private chat
        from aiogram.fsm.storage.base import StorageKey
        pm_key = StorageKey(bot_id=callback.bot.id, chat_id=admin_id, user_id=admin_id)
        pm_state = FSMContext(storage=state.storage, key=pm_key)
        
        await pm_state.set_state(AdminQuestionEditStates.waiting_for_text)
        await pm_state.update_data(
            edit_q_id=report["question_id"],
            edit_report_id=report_id,
            edit_admin_group_msg_id=callback.message.message_id
        )
        
        from handlers.support import map_correct_answer_to_arabic
        correct_ans_mapped = map_correct_answer_to_arabic(report['correct_answer'])
        pm_text = (
            f"✏️ <b>بدء تعديل السؤال #{report['question_id']}</b> (البلاغ #{report_id}):\n\n"
            f"❓ <b>السؤال الحالي:</b>\n"
            f"<blockquote>{report['question']}</blockquote>\n"
            f"A. {report['choice_a']}\n"
            f"B. {report['choice_b']}\n"
            f"C. {report['choice_c']}\n"
            f"D. {report['choice_d']}\n\n"
            f"✅ <b>الإجابة الصحيحة الحالية:</b> {correct_ans_mapped}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✏️ يرجى إرسال <b>نص السؤال الجديد</b>، أو اضغط على الخيارات أدناه للإبقاء على النص الحالي أو إلغاء العملية:"
        )
        await callback.bot.send_message(chat_id=admin_id, text=pm_text, reply_markup=kb.get_admin_edit_options_keyboard(), parse_mode="HTML", disable_web_page_preview=True)
        await callback.answer("📬 أرسلت لك رسالة خاصة لبدء التعديل في الخاص.", show_alert=True)
    except Exception as e:
        logger.error(f"Error starting admin edit in PM: {e}")
        await callback.answer("⚠️ فشل بدء التعديل. يرجى التأكد من أنك قمت بتفعيل البوت في الخاص (/start).", show_alert=True)


@router.callback_query(F.data.startswith("admin_direct_edit:"))
async def handle_admin_direct_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    q_id = int(parts[1])
    source = parts[2]
    
    q = await db.get_question_by_id(q_id)
    if not q:
        await callback.answer("⚠️ السؤال غير موجود.", show_alert=True)
        return
        
    admin_id = callback.from_user.id
    
    try:
        # Save edit context in FSM state of the admin's private chat
        from aiogram.fsm.storage.base import StorageKey
        pm_key = StorageKey(bot_id=callback.bot.id, chat_id=admin_id, user_id=admin_id)
        pm_state = FSMContext(storage=state.storage, key=pm_key)
        
        await pm_state.set_state(AdminQuestionEditStates.waiting_for_text)
        await pm_state.update_data(
            edit_q_id=q_id,
            edit_report_id=0, # 0 means direct edit, no report
            edit_admin_group_msg_id=callback.message.message_id,
            edit_return_mode=source
        )
        
        from handlers.support import map_correct_answer_to_arabic
        correct_ans_mapped = map_correct_answer_to_arabic(q['correct_answer'])
        pm_text = (
            f"✏️ <b>بدء تعديل السؤال #{q_id} (تعديل مباشر):</b>\n\n"
            f"❓ <b>السؤال الحالي:</b>\n"
            f"<blockquote>{q['question']}</blockquote>\n"
            f"A. {q['choice_a']}\n"
            f"B. {q['choice_b']}\n"
            f"C. {q['choice_c']}\n"
            f"D. {q['choice_d']}\n\n"
            f"✅ <b>الإجابة الصحيحة الحالية:</b> {correct_ans_mapped}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✏️ يرجى إرسال <b>نص السؤال الجديد</b>، أو اضغط على الخيارات أدناه للإبقاء على النص الحالي أو إلغاء العملية:"
        )
        await callback.bot.send_message(chat_id=admin_id, text=pm_text, reply_markup=kb.get_admin_edit_options_keyboard(), parse_mode="HTML", disable_web_page_preview=True)
        await callback.answer("📬 أرسلت لك رسالة خاصة لبدء التعديل في الخاص.", show_alert=True)
    except Exception as e:
        logger.error(f"Error starting admin direct edit in PM: {e}")
        await callback.answer("⚠️ فشل بدء التعديل. يرجى التأكد من أنك قمت بتفعيل البوت في الخاص (/start).", show_alert=True)


# --- Global Cancel Command for Admin Edit Process ---
@router.message(Command("cancel"))
@router.message(F.text.casefold() == "cancel")
@router.message(F.text == "إلغاء")
async def handle_admin_global_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None or not current_state.startswith("AdminQuestionEditStates:"):
        return
    await state.clear()
    await message.answer("❌ تم إلغاء تعديل السؤال بنجاح.")


@router.callback_query(F.data == "admin_edit_cancel")
async def handle_admin_edit_cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ تم إلغاء تعديل السؤال.")
    await callback.answer()


@router.callback_query(F.data == "admin_edit_skip")
async def handle_admin_edit_skip_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await callback.answer()
        return
        
    # Fake message for /skip
    fake_msg = Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
        text="/skip"
    )
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    if current_state == AdminQuestionEditStates.waiting_for_text:
        await edit_q_text(fake_msg, state)
    elif current_state == AdminQuestionEditStates.waiting_for_a:
        await edit_q_a(fake_msg, state)
    elif current_state == AdminQuestionEditStates.waiting_for_b:
        await edit_q_b(fake_msg, state)
    elif current_state == AdminQuestionEditStates.waiting_for_c:
        await edit_q_c(fake_msg, state)
    elif current_state == AdminQuestionEditStates.waiting_for_d:
        await edit_q_d(fake_msg, state)
    elif current_state == AdminQuestionEditStates.waiting_for_correct:
        await edit_q_correct(fake_msg, state)
        
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_ans:"))
async def handle_admin_edit_ans_callback(callback: CallbackQuery, state: FSMContext):
    ans = callback.data.split(":")[2]
    current_state = await state.get_state()
    if current_state != AdminQuestionEditStates.waiting_for_correct:
        await callback.answer()
        return
        
    fake_msg = Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
        text=ans
    )
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
        
    await edit_q_correct(fake_msg, state)
    await callback.answer()


# --- Admin Question Editing FSM Handlers ---

@router.message(AdminQuestionEditStates.waiting_for_text)
async def edit_q_text(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_question=message.text.strip())
    
    data = await state.get_data()
    q_id = data['edit_q_id']
    q = await db.get_question_by_id(q_id)
    
    await state.set_state(AdminQuestionEditStates.waiting_for_a)
    await message.answer(f"الخيار A الحالي: {q['choice_a']}\nأرسل الجديد أو اختر من الأسفل:", reply_markup=kb.get_admin_edit_options_keyboard())


@router.message(AdminQuestionEditStates.waiting_for_a)
async def edit_q_a(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_choice_a=message.text.strip())
    
    data = await state.get_data()
    q_id = data['edit_q_id']
    q = await db.get_question_by_id(q_id)
    
    await state.set_state(AdminQuestionEditStates.waiting_for_b)
    await message.answer(f"الخيار B الحالي: {q['choice_b']}\nأرسل الجديد أو اختر من الأسفل:", reply_markup=kb.get_admin_edit_options_keyboard())


@router.message(AdminQuestionEditStates.waiting_for_b)
async def edit_q_b(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_choice_b=message.text.strip())
    
    data = await state.get_data()
    q_id = data['edit_q_id']
    q = await db.get_question_by_id(q_id)
    
    await state.set_state(AdminQuestionEditStates.waiting_for_c)
    await message.answer(f"الخيار C الحالي: {q['choice_c']}\nأرسل الجديد أو اختر من الأسفل:", reply_markup=kb.get_admin_edit_options_keyboard())


@router.message(AdminQuestionEditStates.waiting_for_c)
async def edit_q_c(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_choice_c=message.text.strip())
    
    data = await state.get_data()
    q_id = data['edit_q_id']
    q = await db.get_question_by_id(q_id)
    
    await state.set_state(AdminQuestionEditStates.waiting_for_d)
    await message.answer(f"الخيار D الحالي: {q['choice_d']}\nأرسل الجديد أو اختر من الأسفل:", reply_markup=kb.get_admin_edit_options_keyboard())


@router.message(AdminQuestionEditStates.waiting_for_d)
async def edit_q_d(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_choice_d=message.text.strip())
    
    data = await state.get_data()
    q_id = data['edit_q_id']
    q = await db.get_question_by_id(q_id)
    
    await state.set_state(AdminQuestionEditStates.waiting_for_correct)
    from handlers.support import map_correct_answer_to_arabic
    correct_ans_mapped = map_correct_answer_to_arabic(q['correct_answer'])
    await message.answer(f"الإجابة الصحيحة الحالية: {correct_ans_mapped}\nاختر الإجابة الصحيحة أو اختر من الأسفل:", reply_markup=kb.get_admin_edit_correct_keyboard())


@router.message(AdminQuestionEditStates.waiting_for_correct)
async def edit_q_correct(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data['edit_q_id']
    report_id = data['edit_report_id']
    admin_group_msg_id = data.get('edit_admin_group_msg_id')
    
    q = await db.get_question_by_id(q_id)
    if not q:
        await message.answer("⚠️ السؤال غير موجود.")
        await state.clear()
        return
        
    correct_input = message.text.strip().upper() if message.text != "/skip" else q['correct_answer']
    
    if correct_input not in ['A', 'B', 'C', 'D']:
        await message.answer("⚠️ يرجى إدخال الحرف A أو B أو C أو D.")
        return
        
    new_q = data.get('new_question', q['question'])
    new_a = data.get('new_choice_a', q['choice_a'])
    new_b = data.get('new_choice_b', q['choice_b'])
    new_c = data.get('new_choice_c', q['choice_c'])
    new_d = data.get('new_choice_d', q['choice_d'])
    
    try:
        await message.delete()
    except Exception:
        pass

    # Update SQLite question in backup DB
    await db.update_question_in_db(q_id, new_q, new_a, new_b, new_c, new_d, correct_input)
    
    if report_id and report_id > 0:
        # Update report status to resolved
        await db.update_question_report_status(report_id, 'resolved', 'تم تعديل السؤال وتصحيح الخطأ.')
        
        # Notify student
        report = await db.get_question_report_by_id(report_id)
        if report:
            try:
                student_id = report['user_id']
                notify_text = (
                    f"📢 <b>تحديث بخصوص بلاغك حول السؤال #{q_id}:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ <b>الحالة: تم الحل وتعديل السؤال</b>\n\n"
                    f"💬 شكراً لك على تنبيهك! تم تصحيح الخطأ وتعديل السؤال بنجاح في قاعدة البيانات."
                )
                await message.bot.send_message(chat_id=student_id, text=notify_text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                logger.warning(f"Could not notify student {student_id}: {e}")
                
        # Update the support group message or private admin console
        success_text = f"✅ <b>تم تعديل السؤال #{q_id} بنجاح وحل البلاغ رقم #{report_id}!</b>"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        return_page = data.get('admin_rep_return_page', 1)
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة لقائمة البلاغات", callback_data=f"admin_db_rep_back_list:{return_page}")]
        ])
        
        # If edited in private chat, update the private chat message
        try:
            await message.bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=admin_group_msg_id,
                text=success_text,
                reply_markup=back_kb,
                parse_mode="HTML"
            )
        except Exception:
            # Fallback if from group chat support ticket
            from config import TELEGRAM_SUPPORT_GROUP_ID
            if TELEGRAM_SUPPORT_GROUP_ID:
                try:
                    support_group_id = int(TELEGRAM_SUPPORT_GROUP_ID)
                    admin_name = message.from_user.full_name
                    updated_text = (
                        f"🚨 <b>تقرير عن خطأ في سؤال (رقم البلاغ: #{report_id}) - [تم الحل]:</b>\n"
                        f"• السؤال: {new_q}\n"
                        f"• الإجابة الصحيحة الجديدة: {correct_input}\n"
                        f"• تم التعديل والحل بواسطة المشرف: {admin_name} ✅"
                    )
                    await message.bot.edit_message_text(
                        chat_id=support_group_id,
                        message_id=admin_group_msg_id,
                        text=updated_text,
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error editing support group message: {e}")
            await message.answer(success_text, reply_markup=back_kb)
    else:
        success_text = f"✅ <b>تم تعديل السؤال #{q_id} بنجاح في قاعدة البيانات!</b>"
        await message.answer(success_text, parse_mode="HTML")
            
    await state.clear()


# --- NEW ADMIN REPORTS CENTER HANDLERS ---

@router.callback_query(F.data == "admin_reports_center")
async def handle_admin_reports_center(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    
    role = await db.get_admin_role(user_id) or "super_admin"
    matrix_counts = await db.get_matrix_counts()
    
    # Calculate totals
    pending_total = sum(matrix_counts[c]["pending"] for c in matrix_counts)
    in_progress_total = sum(matrix_counts[c]["in_progress"] for c in matrix_counts)
    resolved_total = sum(matrix_counts[c]["resolved"] for c in matrix_counts)
    
    role_labels = {
        "super_admin": "مدير عام 👑",
        "backup_admin": "مدير احتياطي 🛡️",
        "support_admin": "مشرف دعم 🛠️",
        "moderator": "مشرف تربوي ✍️",
        "improvement_admin": "مشرف تطوير 🚀",
    }
    role_display = role_labels.get(role, role)
    
    # Get user display preference
    display_pref = await db.get_admin_display_preference(user_id)
    
    text = (
        "📋 <b>صندوق رسائل الإدارة (Inbox):</b>\n\n"
        f"👤 دورك الحالي: <b>{role_display}</b>\n"
        "استعرض التبليغات والرسائل لمراجعتها:\n\n"
        f"• 🔴 غير معالجة: <b>{pending_total} بلاغ</b>\n"
        f"• ⏳ قيد المراجعة: <b>{in_progress_total} بلاغ</b>\n"
        f"• ✅ معالجة: <b>{resolved_total} بلاغ</b>"
    )
    
    if display_pref == "grid":
        reply_markup = kb.get_admin_matrix_dashboard_keyboard(matrix_counts, role)
    else:
        reply_markup = kb.get_admin_category_first_keyboard(matrix_counts, role)
        
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("admin_db_rep_filter:"))
async def handle_admin_reports_filter(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    status_filter = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 1
    
    await state.update_data(admin_rep_filter=status_filter, admin_rep_page=page)
    
    reports = await db.get_reports_list(status=status_filter)
    
    labels = {
        "pending": "🔴 غير معالجة",
        "in_progress": "⏳ قيد المراجعة",
        "resolved": "✅ معالجة"
    }
    label = labels.get(status_filter, status_filter)
    
    if not reports:
        text = (
            f"📋 <b>قائمة البلاغات ({label}):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>✨ لا توجد بلاغات في هذا القسم حالياً.</i>"
        )
    else:
        text = (
            f"📋 <b>قائمة البلاغات ({label}):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"اختر أي بلاغ من الجدول أدناه لمراجعته والرد عليه:"
        )
        
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_reports_list_keyboard(reports, status_filter, page=page),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("admin_db_rep_page:"))
async def handle_admin_reports_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    if len(parts) >= 4:
        category = parts[1]
        status = parts[2]
        page = int(parts[3])
        current_filter = f"{category}:{status}"
        reports = await db.get_reports_by_category_and_status(category, status)
    else:
        status_filter = parts[1]
        page = int(parts[2])
        current_filter = status_filter
        reports = await db.get_reports_list(status=status_filter)
        
    await state.update_data(admin_rep_page=page)
    
    cat_labels = {
        "tech": "🚨 مشاكل تقنية",
        "question_error": "📚 أخطاء الأسئلة",
        "expl_error": "⚠️ أخطاء الشرح",
        "course_question": "❓ أسئلة المقررات",
        "suggestion": "💡 اقتراح/رأي",
        "all": "الكل"
    }
    status_labels = {
        "pending": "🔴 غير معالجة",
        "in_progress": "⏳ قيد المراجعة",
        "resolved": "✅ معالجة"
    }
    
    if ":" in current_filter:
        c_parts = current_filter.split(":")
        cat_label = cat_labels.get(c_parts[0], c_parts[0])
        status_label = status_labels.get(c_parts[1], c_parts[1])
        title = f"{cat_label} ({status_label})"
    else:
        status_label = status_labels.get(current_filter, current_filter)
        title = status_label

    text = (
        f"📋 <b>قائمة البلاغات: {title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"اختر أي بلاغ من الجدول أدناه لمراجعته والرد عليه:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_reports_list_keyboard(reports, current_filter, page=page),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("admin_db_rep_view:"))
async def handle_admin_report_detail(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    report_id = int(parts[1])
    
    if len(parts) >= 5:
        category = parts[2]
        status = parts[3]
        page = int(parts[4])
        return_page = f"{category}:{status}:{page}"
    else:
        # Fallback
        page = int(parts[2]) if len(parts) > 2 else 1
        return_page = str(page)
    
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.message.edit_text(
            "⚠️ هذا البلاغ لم يعد موجوداً في النظام.",
            reply_markup=kb.get_admin_reports_center_keyboard(0, 0, 0)
        )
        return
        
    # Auto-transition status from 'pending' to 'in_progress'
    if report.get("status") == "pending":
        await db.update_question_report_status(report_id, 'in_progress', '')
        # Refetch updated report
        report = await db.get_question_report_by_id(report_id)
        
    status_icons = {
        "pending": "⏳ غير معالجة",
        "in_progress": "🟡 قيد المعالجة",
        "resolved": "🟢 تم الحل / معالجته",
        "rejected": "❌ تم الرفض"
    }
    type_labels = {
        "tech": "🛠️ مشكلة تقنية",
        "course_question": "❓ سؤال في المقرر",
        "content_error": "⚠️ خطأ في المحتوى",
        "suggestion": "💡 اقتراح أو غير ذلك",
        "improvement": "💡 اقتراح أو غير ذلك",
        "review": "⭐ تقييم / رأي",
        "question_error": "📚 خطأ في سؤال",
        "content": "📚 خطأ في سؤال",
        "expl_error": "⚠️ خطأ في الشرح",
        "أخرى / سبب آخر": "أخرى",
        "خطأ في الإجابة الصحيحة": "إجابة",
        "خطأ في نص السؤال": "نص",
        "خطأ في أحد الخيارات": "خيارات",
        "سبب آخر / مشكلة أخرى": "أخرى"
    }
    
    status_str = status_icons.get(report.get("status"), report.get("status"))
    raw_type = report.get("report_type")
    type_str = type_labels.get(raw_type, raw_type if raw_type else "بلاغ")
    
    username_val = report.get("username") or ""
    username_display = f"@{username_val}" if username_val else "بدون معرف"
    first_name_val = report.get("first_name") or "طالب"
    
    from handlers.support import format_date_to_long_arabic, re
    notes_raw = report.get("notes") or ""
    error_type_extracted = None
    timestamp_extracted = None
    comment_extracted = notes_raw
    
    m_full = re.match(r'^\[([^\]]+)\]\s+(?:\[الدقيقة:\s*([^\]]+)\]\s+)?(.*)$', notes_raw, re.DOTALL)
    if m_full:
        error_type_extracted = m_full.group(1).strip()
        if m_full.group(2):
            timestamp_extracted = m_full.group(2).strip()
        comment_extracted = m_full.group(3).strip()
    else:
        m_simple = re.match(r'^\[([^\]]+)\]$', notes_raw)
        if m_simple:
            error_type_extracted = m_simple.group(1).strip()
            comment_extracted = ""
            
    notes_display = ""
    if error_type_extracted:
        notes_display += f"• <b>نوع الخطأ:</b> {error_type_extracted}\n"
    if timestamp_extracted:
        notes_display += f"• <b>التوقيت المشكل:</b> دقيقة {timestamp_extracted}\n"
        
    if comment_extracted:
        notes_display += f"📝 <b>الملاحظات وتفاصيل البلاغ:</b>\n<blockquote>{comment_extracted}</blockquote>"
    else:
        notes_display += "📝 <b>الملاحظات وتفاصيل البلاغ:</b> <i>(لا توجد تفاصيل إضافية)</i>"

    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>تفاصيل البلاغ رقم #{report['id']}</b>\n"
        f"📂 <b>القسم:</b> {type_str}\n"
        f"👤 <b>الطالب:</b> {first_name_val} ({username_display})\n"
        f"⚖️ <b>الحالة:</b> {status_str}\n"
        f"📅 <b>التاريخ:</b> {format_date_to_long_arabic(report.get('created_at', ''))}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{notes_display}\n\n"
    )
    
    has_question = False
    if report.get("question_id"):
        has_question = True
        text += (
            f"❓ <b>السؤال المرتبط (ID: #{report['question_id']}):</b>\n"
            f"<blockquote>{(report.get('question') or '').strip()}</blockquote>\n\n"
        )
        
    if report.get("admin_reply"):
        text += (
            f"💬 <b>رد الإدارة المكتوب:</b>\n"
            f"<blockquote><b>{report['admin_reply']}</b></blockquote>\n"
        )
    else:
        text += "💬 <b>رد الإدارة:</b> <i>لم يتم الرد بعد. سيصلك إشعار فور مراجعته.</i>\n"
        
    text += "━━━━━━━━━━━━━━━━━━━━━━"
    
    from handlers.support import extract_timestamp_from_report
    timestamp_url, timestamp_display = extract_timestamp_from_report(report)
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_report_actions_keyboard(
            report_id, 
            has_question, 
            return_page=return_page,
            timestamp_url=timestamp_url,
            timestamp_display=timestamp_display
        ),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.callback_query(F.data.startswith("admin_db_rep_resolve:"))
async def handle_db_report_resolve(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    
    parts = callback.data.split(":")
    report_id = int(parts[1])
    if len(parts) >= 5:
        return_page = f"{parts[2]}:{parts[3]}:{parts[4]}"
    else:
        return_page = parts[2] if len(parts) > 2 else "1"
    
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    await db.update_question_report_status(report_id, 'resolved', 'تم حل المشكلة وتصحيح الخطأ.')
    await callback.answer("✅ تم تحديد البلاغ كمحلول.")
    
    # Notify student
    student_id = report["user_id"]
    try:
        notify_text = (
            f"📢 <b>تحديث بخصوص بلاغك رقم #{report_id}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>الحالة: تم الحل</b>\n\n"
            f"💬 شكراً لتنبيهك، تم حل المشكلة بنجاح."
        )
        await callback.bot.send_message(chat_id=student_id, text=notify_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass
        
    callback.data = f"admin_db_rep_view:{report_id}:{return_page}"
    await handle_admin_report_detail(callback, state)

@router.callback_query(F.data.startswith("admin_db_rep_reject:"))
async def handle_db_report_reject(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    report_id = int(parts[1])
    if len(parts) >= 5:
        return_page = f"{parts[2]}:{parts[3]}:{parts[4]}"
    else:
        return_page = parts[2] if len(parts) > 2 else "1"
    
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    await db.update_question_report_status(report_id, 'rejected', 'البلاغ غير دقيق أو المحتوى صحيح علمياً.')
    await callback.answer("❌ تم رفض البلاغ.")
    
    # Notify student
    student_id = report["user_id"]
    try:
        notify_text = (
            f"📢 <b>تحديث بخصوص بلاغك رقم #{report_id}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>الحالة: تم رفض البلاغ</b>\n\n"
            f"💬 تمت مراجعة البلاغ وهو غير دقيق أو أن المحتوى صحيح تماماً."
        )
        await callback.bot.send_message(chat_id=student_id, text=notify_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass
        
    callback.data = f"admin_db_rep_view:{report_id}:{return_page}"
    await handle_admin_report_detail(callback, state)

@router.callback_query(F.data.startswith("admin_db_rep_reply:"))
async def handle_db_report_reply_init(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    report_id = int(parts[1])
    if len(parts) >= 5:
        return_page = f"{parts[2]}:{parts[3]}:{parts[4]}"
    else:
        return_page = parts[2] if len(parts) > 2 else "1"
    
    await state.set_state(AdminStates.waiting_for_admin_reply)
    await state.update_data(
        admin_rep_reply_id=report_id,
        admin_rep_msg_id=callback.message.message_id,
        admin_rep_return_page=return_page
    )
    
    text = (
        f"✏️ <b>الرد المباشر على البلاغ رقم #{report_id}:</b>\n\n"
        "الرجاء كتابة نص الرد الذي تود إرساله للطالب في رسالة نصية:"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_db_rep_view:{report_id}:{return_page}")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")

@router.message(AdminStates.waiting_for_admin_reply)
async def handle_db_report_reply_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    report_id = data.get("admin_rep_reply_id")
    msg_id = data.get("admin_rep_msg_id")
    return_page = data.get("admin_rep_return_page", 1)
    reply_text = message.text.strip() if message.text else ""
    
    try:
        await message.delete()
    except Exception:
        pass
        
    if not reply_text:
        return
        
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await message.answer("⚠️ البلاغ غير موجود.")
        await state.clear()
        return
        
    await state.update_data(
        admin_reply_text=reply_text,
        admin_rep_reply_id=report_id,
        admin_rep_msg_id=msg_id,
        admin_rep_return_page=return_page
    )
    await state.set_state(AdminStates.waiting_for_status_decision)
    
    confirm_text = (
        f"✍️ <b>تم تسجيل ردك للبلاغ #{report_id}:</b>\n"
        f"<blockquote>{reply_text}</blockquote>\n"
        f"⚖️ <b>يرجى تحديد حالة هذا البلاغ لإرسال الرد للطالب:</b>"
    )
    
    await message.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=msg_id,
        text=confirm_text,
        reply_markup=kb.get_admin_status_decision_keyboard(report_id, return_page=str(return_page)),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_decide:"))
async def handle_admin_status_decision(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    await callback.answer()
    
    parts = callback.data.split(":")
    report_id = int(parts[1])
    status = parts[2]
    return_page_str = parts[3]
    
    data = await state.get_data()
    
    if return_page_str == "group":
        reply_text = data.get("group_reply_text")
        await state.clear()
        
        report = await db.get_question_report_by_id(report_id)
        if not report or not reply_text:
            await callback.message.edit_text("⚠️ حدث خطأ أو أن تفاصيل الرد مفقودة.")
            return
            
        await db.update_question_report_status(report_id, status, reply_text)
        
        # Notify student
        student_id = report["user_id"]
        from handlers.support import format_student_notification
        notify_text = format_student_notification(report, reply_text, status)
        try:
            await callback.message.bot.send_message(
                chat_id=student_id,
                text=notify_text,
                reply_markup=kb.get_student_notification_keyboard(report_id),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            pass
            
        status_displays = {
            "resolved": "تم الحل ✅",
            "rejected": "تم الرفض ❌",
            "in_progress": "قيد المعالجة 🟡"
        }
        success_text = (
            f"✅ <b>تم إرسال ردك للطالب بنجاح للبلاغ #{report_id}!</b>\n"
            f"• الحالة المحددة: <b>{status_displays.get(status, status)}</b>\n\n"
            f"الرد:\n<i>{reply_text}</i>"
        )
        await callback.message.edit_text(success_text, reply_markup=None, parse_mode="HTML")
        
    else:
        reply_text = data.get("admin_reply_text")
        msg_id = data.get("admin_rep_msg_id")
        return_page = return_page_str
        
        await state.clear()
        
        report = await db.get_question_report_by_id(report_id)
        if not report or not reply_text:
            await callback.message.edit_text("⚠️ حدث خطأ أو أن تفاصيل الرد مفقودة.")
            return
            
        await db.update_question_report_status(report_id, status, reply_text)
        
        # Notify student
        student_id = report["user_id"]
        from handlers.support import format_student_notification
        notify_text = format_student_notification(report, reply_text, status)
        try:
            await callback.message.bot.send_message(
                chat_id=student_id,
                text=notify_text,
                reply_markup=kb.get_student_notification_keyboard(report_id),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            pass
            
        status_displays = {
            "resolved": "تم الحل ✅",
            "rejected": "تم الرفض ❌",
            "in_progress": "قيد المعالجة 🟡"
        }
        success_text = (
            f"✅ <b>تم إرسال الرد بنجاح للبلاغ رقم #{report_id}!</b>\n"
            f"• الحالة: <b>{status_displays.get(status, status)}</b>\n\n"
            f"الرد المرسل:\n<i>{reply_text}</i>"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة لقائمة البلاغات", callback_data=f"admin_db_rep_back_list:{return_page}")]
        ])
        await callback.message.edit_text(
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("admin_db_rep_edit_q:"))
async def handle_db_report_edit_q(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    report_id = int(parts[1])
    if len(parts) >= 5:
        return_page = f"{parts[2]}:{parts[3]}:{parts[4]}"
    else:
        return_page = parts[2] if len(parts) > 2 else "1"
    
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await callback.answer("⚠️ البلاغ غير موجود.", show_alert=True)
        return
        
    await state.set_state(AdminQuestionEditStates.waiting_for_text)
    await state.update_data(
        edit_q_id=report["question_id"],
        edit_report_id=report_id,
        edit_admin_group_msg_id=callback.message.message_id,
        admin_rep_return_page=return_page
    )
    
    text = (
        f"✏️ <b>تعديل السؤال المرتبط #{report['question_id']}:</b>\n\n"
        f"❓ <b>السؤال الحالي:</b>\n"
        f"<blockquote>{report['question']}</blockquote>\n"
        "أرسل نص السؤال الجديد، أو أرسل <code>/skip</code> للإبقاء على النص الحالي:"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء والتراجع", callback_data=f"admin_db_rep_view:{report_id}:{return_page}")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_db_rep_back_list"))
async def handle_db_report_back_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    # Format can be admin_db_rep_back_list:category:status:page or admin_db_rep_back_list:page
    if len(parts) >= 4:
        category = parts[1]
        status = parts[2]
        page = int(parts[3])
        current_filter = f"{category}:{status}"
        reports = await db.get_reports_by_category_and_status(category, status)
    else:
        # Fallback for old style
        data = await state.get_data()
        current_filter = data.get("admin_rep_filter", "pending")
        page = int(parts[1]) if len(parts) > 1 else 1
        if ":" in current_filter:
            c_parts = current_filter.split(":")
            category = c_parts[0]
            status = c_parts[1]
            reports = await db.get_reports_by_category_and_status(category, status)
        else:
            category = "all"
            status = current_filter
            reports = await db.get_reports_list(status=status)
            
    cat_labels = {
        "tech": "🚨 مشاكل تقنية",
        "question_error": "📚 أخطاء الأسئلة",
        "expl_error": "⚠️ أخطاء الشرح",
        "course_question": "❓ أسئلة المقررات",
        "suggestion": "💡 اقتراح/رأي",
        "all": "الكل"
    }
    status_labels = {
        "pending": "🔴 غير معالجة",
        "in_progress": "⏳ قيد المراجعة",
        "resolved": "✅ معالجة"
    }
    
    cat_label = cat_labels.get(category, category)
    status_label = status_labels.get(status, status)
    
    if not reports:
        text = (
            f"📋 <b>قائمة البلاغات: {cat_label} ({status_label})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>✨ لا توجد بلاغات في هذا القسم حالياً.</i>"
        )
    else:
        text = (
            f"📋 <b>قائمة البلاغات: {cat_label} ({status_label})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"اختر أي بلاغ من الجدول أدناه لمراجعته والرد عليه:"
        )
        
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_reports_list_keyboard(reports, current_filter, page=page),
        parse_mode="HTML"
    )


# ==================================================
# --- Admin User Management Handlers (Super Admin Only) ---
# ==================================================

@router.callback_query(F.data.startswith("admin_manage_list"))
async def handle_admin_management_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    
    # Only super_admin can manage admins
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        await callback.answer("⚠️ عذراً، هذا القسم مخصص للمدير العام (super_admin) فقط.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1
    
    admins = await db.get_all_admins()
    
    text = (
        "👥 <b>إدارة مشرفي البوت وصلاحياتهم:</b>\n\n"
        "يمكنك من هنا تسجيل مشرفين جدد أو إزالة صلاحيات الإشراف عن المشرفين الحاليين.\n"
        "اختر أي مشرف من القائمة أدناه لعرض تفاصيل صلاحياته:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_management_keyboard(admins, page=page),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_pg:"))
async def handle_admin_pg(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":")[1])
    admins = await db.get_all_admins()
    
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_management_keyboard(admins, page=page)
    )
    await callback.answer()


@router.callback_query(F.data == "adm_add")
async def handle_admin_add_init(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        await callback.answer("⚠️ غير مصرح لك.", show_alert=True)
        return
        
    await state.set_state(AdminManagementStates.waiting_for_new_admin_id)
    
    text = (
        "➕ <b>إضافة مشرف جديد للبوت:</b>\n\n"
        "يرجى إرسال <b>المعرف الرقمي (Telegram ID)</b> للمشرف الجديد كأرقام فقط.\n"
        "أو قم **بتوجيه (Forward) أي رسالة** من حسابه إلى هنا مباشرة ليستخرج البوت بياناته تلقائياً."
    )
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء وتراجع", callback_data="admin_manage_list")]
    ])
    
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.message(AdminManagementStates.waiting_for_new_admin_id)
async def handle_admin_id_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        return
        
    new_admin_id = None
    new_admin_username = ""
    new_admin_first_name = ""
    
    # Check if message is forwarded
    if message.forward_from:
        new_admin_id = message.forward_from.id
        new_admin_username = message.forward_from.username or ""
        new_admin_first_name = message.forward_from.first_name or ""
    elif message.forward_sender_name:
        await message.answer(
            "⚠️ عذراً، هذا المستخدم يقوم بإخفاء حسابه عند توجيه الرسائل.\n"
            "الرجاء إرسال <b>المعرف الرقمي (Telegram ID)</b> الخاص به كأرقام فقط (مثال: <code>123456789</code>).",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ إلغاء وتراجع", callback_data="admin_manage_list")]
            ]),
            parse_mode="HTML"
        )
        return
    else:
        # Read text as ID
        text = message.text.strip() if message.text else ""
        if text.isdigit():
            new_admin_id = int(text)
        else:
            await message.answer(
                "⚠️ إدخال غير صالح. يرجى إرسال المعرف الرقمي كأرقام فقط أو توجيه رسالة من حسابه.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ إلغاء وتراجع", callback_data="admin_manage_list")]
                ])
            )
            return
            
    await state.update_data(
        new_admin_id=new_admin_id,
        new_admin_username=new_admin_username,
        new_admin_first_name=new_admin_first_name
    )
    
    # If name is already resolved from forwarded message, skip name input
    if new_admin_first_name:
        # Prompt directly for role
        await state.clear()
        role_kb = kb.get_admin_role_selection_keyboard(new_admin_id)
        text = (
            "👑 <b>تحديد صلاحيات ورتبة المشرف الجديد:</b>\n\n"
            f"• الاسم: <b>{new_admin_first_name}</b>\n"
            f"• اسم المستخدم: @{new_admin_username or 'لا يوجد'}\n"
            f"• المعرف الرقمي: <code>{new_admin_id}</code>\n\n"
            "يرجى تحديد الرتبة المناسبة له من الخيارات أدناه:"
        )
        await message.answer(text, reply_markup=role_kb, parse_mode="HTML")
    else:
        # Prompt for first name/nickname
        await state.set_state(AdminManagementStates.waiting_for_new_admin_name)
        await message.answer(
            f"👤 تم تسجيل المعرف الرقمي: <code>{new_admin_id}</code>\n\n"
            "يرجى كتابة اسم أو لقب المشرف الجديد الذي سيظهر في القائمة:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ إلغاء وتراجع", callback_data="admin_manage_list")]
            ]),
            parse_mode="HTML"
        )


@router.message(AdminManagementStates.waiting_for_new_admin_name)
async def handle_admin_name_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        return
        
    first_name = message.text.strip() if message.text else ""
    if not first_name:
        await message.answer("⚠️ الرجاء كتابة اسم أو لقب صحيح للمشرف:")
        return
        
    data = await state.get_data()
    new_admin_id = data.get("new_admin_id")
    new_admin_username = data.get("new_admin_username", "")
    
    await state.update_data(new_admin_first_name=first_name)
    
    text = (
        "👑 <b>تحديد صلاحيات ورتبة المشرف الجديد:</b>\n\n"
        f"• الاسم: <b>{first_name}</b>\n"
        f"• المعرف الرقمي: <code>{new_admin_id}</code>\n\n"
        "يرجى تحديد الرتبة المناسبة له من الخيارات أدناه:"
    )
    
    await message.answer(text, reply_markup=kb.get_admin_role_selection_keyboard(new_admin_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_role:"))
async def handle_admin_role_save(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        await callback.answer("⚠️ غير مصرح لك.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    new_admin_id = int(parts[1])
    selected_role = parts[2]
    
    # Fetch first_name & username from state if present
    data = await state.get_data()
    first_name = data.get("new_admin_first_name", "")
    username = data.get("new_admin_username", "")
    
    # If state is empty (e.g. direct forward), we try to get info
    if not first_name:
        first_name = callback.from_user.first_name or "مشرف"
        
    await state.clear()
    
    # Save to databases
    success = await db.add_admin_to_db(
        telegram_id=new_admin_id,
        role=selected_role,
        username=username,
        first_name=first_name,
        added_by=user_id
    )
    
    role_labels = {
        "super_admin": "👑 مدير عام (super_admin)",
        "backup_admin": "🛡️ مدير احتياطي (backup_admin)",
        "support_admin": "🛠️ مشرف دعم (support_admin)",
        "moderator": "✍️ مشرف تربوي (moderator)",
        "improvement_admin": "🚀 مشرف تطوير (improvement_admin)"
    }
    role_label = role_labels.get(selected_role, selected_role)
    
    if success:
        text = f"✅ تم إضافة المشرف <b>{first_name}</b> بنجاح ورتبته هي: <b>{role_label}</b>"
    else:
        text = "❌ حدث خطأ أثناء إضافة المشرف لقاعدة البيانات."
        
    await callback.message.answer(text, parse_mode="HTML")
    
    # Back to list
    admins = await db.get_all_admins()
    await callback.message.edit_text(
        "👥 <b>إدارة مشرفي البوت وصلاحياتهم:</b>\n\n"
        "يمكنك من هنا تسجيل مشرفين جدد أو إزالة صلاحيات الإشراف عن المشرفين الحاليين.\n"
        "اختر أي مشرف من القائمة أدناه لعرض تفاصيل صلاحياته:",
        reply_markup=kb.get_admin_management_keyboard(admins, page=1),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_view:"))
async def handle_admin_view_detail(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        await callback.answer("⚠️ غير مصرح لك.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    admin_id = int(parts[1])
    return_page = int(parts[2]) if len(parts) > 2 else 1
    
    # Fetch admin details from DB
    admins = await db.get_all_admins()
    admin = next((a for a in admins if a["telegram_id"] == admin_id), None)
    
    if not admin:
        # Fallback to local TELEGRAM_ADMIN_IDS if not in DB
        if admin_id in TELEGRAM_ADMIN_IDS:
            admin = {
                "telegram_id": admin_id,
                "role": "super_admin",
                "username": "Config",
                "first_name": "مدير النظام الأساسي",
                "added_at": "تلقائي من الإعدادات"
            }
            
    if not admin:
        await callback.answer("⚠️ المشرف غير موجود أو تم حذفه.", show_alert=True)
        return
        
    role_labels = {
        "super_admin": "👑 مدير عام (super_admin)",
        "backup_admin": "🛡️ مدير احتياطي (backup_admin)",
        "support_admin": "🛠️ مشرف دعم (support_admin)",
        "moderator": "✍️ مشرف تربوي (moderator)",
        "improvement_admin": "🚀 مشرف تطوير (improvement_admin)"
    }
    role_label = role_labels.get(admin["role"], admin["role"])
    username_str = f"@{admin['username']}" if admin['username'] else "لا يوجد"
    
    text = (
        "👤 <b>تفاصيل صلاحيات المشرف:</b>\n\n"
        f"• الاسم: <b>{admin['first_name'] or 'بدون اسم'}</b>\n"
        f"• اسم المستخدم: <b>{username_str}</b>\n"
        f"• المعرف الرقمي: <code>{admin['telegram_id']}</code>\n"
        f"• الرتبة الحالية: <b>{role_label}</b>\n"
        f"• تاريخ الإضافة: <code>{admin.get('added_at', '')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_detail_keyboard(admin_id, return_page=return_page),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_del:"))
async def handle_admin_remove(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    role = await db.get_admin_role(user_id)
    if role != "super_admin":
        await callback.answer("⚠️ غير مصرح لك.", show_alert=True)
        return
        
    admin_id = int(callback.data.split(":")[1])
    
    # Prevent super_admin from removing themselves
    if admin_id == user_id:
        await callback.answer("❌ لا يمكنك إزالة صلاحيات الإشراف عن نفسك !", show_alert=True)
        return
        
    await db.remove_admin_from_db(admin_id)
    await callback.answer("✅ تم إزالة صلاحيات الإشراف بنجاح.", show_alert=True)
    
    # Back to list
    admins = await db.get_all_admins()
    await callback.message.edit_text(
        "👥 <b>إدارة مشرفي البوت وصلاحياتهم:</b>\n\n"
        "يمكنك من هنا تسجيل مشرفين جدد أو إزالة صلاحيات الإشراف عن المشرفين الحاليين.\n"
        "اختر أي مشرف من القائمة أدناه لعرض تفاصيل صلاحياته:",
        reply_markup=kb.get_admin_management_keyboard(admins, page=1),
        parse_mode="HTML"
    )


# ==================================================
# --- Admin Hierarchical Settings Submenus ---
# ==================================================

@router.callback_query(F.data == "admin_dir_buttons")
async def handle_admin_dir_buttons(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    hidden_buttons = await db.get_hidden_items("buttons")
    await callback.message.edit_text(
        "⚙️ <b>إعدادات أزرار الطلاب (Direction des Boutons):</b>\n\n"
        "يمكنك إظهار أو إخفاء أزرار معينة من القائمة الرئيسية للطالب. اضغط على أي زر لتغيير حالته:",
        reply_markup=kb.get_admin_dir_buttons_keyboard(hidden_buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tog_btn:"))
async def handle_admin_tog_btn(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    btn_id = callback.data.split(":")[1]
    hidden_buttons = await db.get_hidden_items("buttons")
    is_hidden = btn_id in hidden_buttons
    await db.set_item_hidden("buttons", btn_id, not is_hidden)
    
    updated_hidden = await db.get_hidden_items("buttons")
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_dir_buttons_keyboard(updated_hidden)
    )
    await callback.answer(f"🔄 تم {'إخفاء' if not is_hidden else 'إظهار'} الزر بنجاح.")


@router.callback_query(F.data == "admin_dir_subjects_lessons")
async def handle_admin_dir_subjects_lessons(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.message.edit_text(
        "📚 <b>إعدادات المواد والدروس والمحاور (Direction des Leçons):</b>\n\n"
        "اختر القسم الذي ترغب في تعديل إعدادات رؤيته للطلاب:",
        reply_markup=kb.get_admin_dir_subjects_lessons_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_dir_subjects")
async def handle_admin_dir_subjects(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    hidden_subjects = await db.get_hidden_items("subjects")
    await callback.message.edit_text(
        "📂 <b>إظهار/إخفاء المواد للطلاب:</b>\n\n"
        "اضغط على المادة للتبديل بين إظهارها أو إخفائها في قائمة المواد لدى الطلاب:",
        reply_markup=kb.get_admin_dir_subjects_keyboard(hidden_subjects),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tog_sub:"))
async def handle_admin_tog_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    sub_id = callback.data.split(":")[1]
    hidden_subjects = await db.get_hidden_items("subjects")
    is_hidden = sub_id in hidden_subjects
    await db.set_item_hidden("subjects", sub_id, not is_hidden)
    
    updated_hidden = await db.get_hidden_items("subjects")
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_dir_subjects_keyboard(updated_hidden)
    )
    await callback.answer(f"🔄 تم {'إخفاء' if not is_hidden else 'إظهار'} المادة بنجاح.")


@router.callback_query(F.data == "admin_dir_lessons_select")
async def handle_admin_dir_lessons_select(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.message.edit_text(
        "📖 <b>إظهار/إخفاء الدروس:</b>\n\n"
        "اختر المادة التي ترغب في إدارة رؤية دروسها لدى الطلاب:",
        reply_markup=kb.get_admin_dir_lessons_subjects_keyboard("lessons"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_dir_themes_select")
async def handle_admin_dir_themes_select(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.message.edit_text(
        "🎯 <b>إظهار/إخفاء المحاور والمستويات:</b>\n\n"
        "اختر المادة التي ترغب في إدارة رؤية محاورها لدى الطلاب:",
        reply_markup=kb.get_admin_dir_lessons_subjects_keyboard("themes"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dir_sel_sub:"))
async def handle_admin_dir_sel_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    parts = callback.data.split(":")
    mode = parts[1]
    subject = parts[2]
    
    sub_labels = {
        "fiqh": "الفقه",
        "sira": "السيرة النبوية",
        "nahw": "النحو",
        "aqeeda": "العقيدة"
    }
    sub_label = sub_labels.get(subject, subject)
    
    if mode == "lessons":
        hidden_lessons = await db.get_hidden_items(f"lessons_{subject}")
        await callback.message.edit_text(
            f"📖 <b>إدارة دروس مادة {sub_label}:</b>\n\n"
            "اضغط على أي درس للتبديل بين إخفائه (🚫) أو إظهاره (👁️) لدى الطلاب:",
            reply_markup=kb.get_admin_dir_lessons_keyboard(subject, hidden_lessons),
            parse_mode="HTML"
        )
    elif mode == "themes":
        hidden_themes = await db.get_hidden_items(f"themes_{subject}")
        await callback.message.edit_text(
            f"🎯 <b>إدارة محاور مادة {sub_label}:</b>\n\n"
            "اضغط على أي محور للتبديل بين إخفائه (🚫) أو إظهاره (👁️) لدى الطلاب:",
            reply_markup=kb.get_admin_dir_themes_keyboard(subject, hidden_themes),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("tog_dir_les:"))
async def handle_admin_tog_dir_les(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = parts[2]
    
    hidden_lessons = await db.get_hidden_items(f"lessons_{subject}")
    is_hidden = lesson in hidden_lessons
    await db.set_item_hidden(f"lessons_{subject}", lesson, not is_hidden)
    
    updated_hidden = await db.get_hidden_items(f"lessons_{subject}")
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_dir_lessons_keyboard(subject, updated_hidden)
    )
    await callback.answer(f"🔄 تم {'إخفاء' if not is_hidden else 'إظهار'} الدرس {lesson} بنجاح.")


@router.callback_query(F.data.startswith("tog_dir_th:"))
async def handle_admin_tog_dir_th(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    parts = callback.data.split(":")
    subject = parts[1]
    theme_key = parts[2]
    
    hidden_themes = await db.get_hidden_items(f"themes_{subject}")
    is_hidden = theme_key in hidden_themes
    await db.set_item_hidden(f"themes_{subject}", theme_key, not is_hidden)
    
    updated_hidden = await db.get_hidden_items(f"themes_{subject}")
    await callback.message.edit_reply_markup(
        reply_markup=kb.get_admin_dir_themes_keyboard(subject, updated_hidden)
    )
    await callback.answer(f"🔄 تم تعديل حالة المحور بنجاح.")


@router.callback_query(F.data == "admin_dir_data")
async def handle_admin_dir_data(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.message.edit_text(
        "📊 <b>إدارة بيانات النظام (Direction des Données):</b>\n\n"
        "من هنا يمكنك مزامنة الأسئلة مع Google Sheets، أو تصدير قاعدة البيانات/الأسئلة كنسخة احتياطية:",
        reply_markup=kb.get_admin_dir_data_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_data_export_csv")
async def handle_admin_data_export_csv(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer("⏳ جاري تحضير ملف الأسئلة...")
    
    try:
        import csv
        import io
        from aiogram.types import BufferedInputFile
        import aiosqlite
        from database.core import DB_PATH
        async with aiosqlite.connect(DB_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT * FROM questions") as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            await callback.message.answer("⚠️ لا توجد أسئلة في قاعدة البيانات حالياً.")
            return
            
        output = io.StringIO()
        writer = csv.writer(output)
        # Headers
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(list(row))
            
        csv_data = output.getvalue().encode('utf-8')
        input_file = BufferedInputFile(csv_data, filename="questions_export.csv")
        
        await callback.message.bot.send_document(
            chat_id=callback.from_user.id,
            document=input_file,
            caption="📥 <b>تصدير الأسئلة:</b>\nتم توليد ملف CSV يحتوي على جميع الأسئلة الحالية بنجاح.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error exporting questions CSV: {e}")
        await callback.message.answer(f"❌ حدث خطأ أثناء تصدير الأسئلة: {e}")


@router.callback_query(F.data == "admin_data_backup_db")
async def handle_admin_data_backup_db(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer("⏳ جاري نسخ قاعدة البيانات...")
    
    try:
        from config import DATABASE_PATH
        from aiogram.types import FSInputFile
        import os
        
        if os.path.exists(DATABASE_PATH):
            input_file = FSInputFile(DATABASE_PATH, filename="backup_bot.db")
            await callback.message.bot.send_document(
                chat_id=callback.from_user.id,
                document=input_file,
                caption="📦 <b>نسخة احتياطية لقاعدة البيانات:</b>\nملف SQLite الخاص بالبوت البديل جاهز للتحميل.",
                parse_mode="HTML"
            )
        else:
            await callback.message.answer("⚠️ قاعدة البيانات غير موجودة في المسار المحدد.")
    except Exception as e:
        logger.error(f"Error sending DB backup: {e}")
        await callback.message.answer(f"❌ حدث خطأ أثناء نسخ قاعدة البيانات: {e}")


@router.callback_query(F.data == "admin_dir_display")
async def handle_admin_dir_display(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    display_pref = await db.get_admin_display_preference(callback.from_user.id)
    ticket_detail_level = await db.get_setting("ticket_detail_level", "compact")
    await callback.message.edit_text(
        "👁️ <b>إعدادات العرض (Direction de l'Affichage):</b>\n\n"
        "من هنا يمكنك التبديل بين طريقة العرض المجدولة (جدول) أو العرض المفصل (قائمة) للبلاغات، وأيضاً تخصيص مستوى تفاصيل البلاغات في المجموعات:",
        reply_markup=kb.get_admin_dir_display_keyboard(display_pref, ticket_detail_level, show_ticket_level=True),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_dir_security")
async def handle_admin_dir_security(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    restrict_val = await db.get_setting("restrict_to_academy_group", "True") == "True"
    ai_disabled = await db.get_setting("disable_ai_for_students", "False") == "True"
    await callback.message.edit_text(
        "🔒 <b>إعدادات الأمان (Direction de la Sécurité):</b>\n\n"
        "من هنا يمكنك تفعيل أو تعطيل حظر الدخول للطلاب خارج المجموعة المحددة، وكذلك تفعيل أو تعطيل أسئلة الذكاء الاصطناعي للطلاب:",
        reply_markup=kb.get_admin_dir_security_keyboard(restrict_val, ai_disabled=ai_disabled),
        parse_mode="HTML"
    )
    await callback.answer()


# --- Admin Question Creation FSM Handlers ---

class AdminQuestionCreateStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_course_number = State()
    waiting_for_course_name = State()
    waiting_for_question_text = State()
    waiting_for_choice_a = State()
    waiting_for_choice_b = State()
    waiting_for_choice_c = State()
    waiting_for_choice_d = State()
    waiting_for_correct = State()
    waiting_for_explanation = State()
    waiting_for_confirmation = State()


class AdminQuestionSearchStates(StatesGroup):
    waiting_for_question_id = State()


class AdminStudentManageStates(StatesGroup):
    waiting_for_search_query = State()


@router.message(Command("cancel"))
@router.message(F.text.lower() == "cancel")
@router.message(F.text == "إلغاء")
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer(
        "❌ تم إلغاء العملية والعودة للوحة الإدارة.",
        reply_markup=await _get_admin_keyboard(message.from_user.id)
    )


@router.callback_query(F.data == "admin_add_question")
async def handle_admin_add_question(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminQuestionCreateStates.waiting_for_subject)
    
    # Show subject buttons
    subjects_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="الفقه (fiqh)", callback_data="admin_q_sub:fiqh")],
        [InlineKeyboardButton(text="السيرة النبوية (sira)", callback_data="admin_q_sub:sira")],
        [InlineKeyboardButton(text="النحو (nahw)", callback_data="admin_q_sub:nahw")],
        [InlineKeyboardButton(text="العقيدة (aqeeda)", callback_data="admin_q_sub:aqeeda")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_create_cancel")]
    ])
    await callback.message.edit_text(
        "➕ <b>إضافة سؤال جديد - الخطوة 1:</b>\n\nاختر مادة السؤال:",
        reply_markup=subjects_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_q_create_cancel")
async def handle_admin_q_create_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ تم إلغاء إضافة السؤال.")
    await cmd_admin(callback, state)


@router.callback_query(F.data.startswith("admin_q_sub:"))
async def handle_admin_q_subject_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    current_state = await state.get_state()
    if current_state != AdminQuestionCreateStates.waiting_for_subject:
        await callback.answer("⚠️ انتهت صلاحية هذه الجلسة.")
        return
    subject = callback.data.split(":")[1]
    await state.update_data(subject=subject)
    await state.set_state(AdminQuestionCreateStates.waiting_for_course_number)
    await callback.message.edit_text(
        "➕ <b>إضافة سؤال جديد - الخطوة 2:</b>\n\nأرسل <b>رقم الدرس</b> (مثلاً: 14):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_create_cancel")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminQuestionCreateStates.waiting_for_course_number)
async def handle_admin_q_course_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("⚠️ يرجى إدخال رقم صحيح للدرس:")
        return
    await state.update_data(course_number=int(txt))
    await state.set_state(AdminQuestionCreateStates.waiting_for_course_name)
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 3:</b>\n\nأرسل <b>اسم الدرس</b> (مثلاً: أحكام الصلاة)، أو أرسل /skip لتخطي اسم الدرس:",
        parse_mode="HTML"
    )


@router.message(AdminQuestionCreateStates.waiting_for_course_name)
async def handle_admin_q_course_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = ""
    if message.text.strip() != "/skip":
        name = message.text.strip()
    await state.update_data(course_name=name)
    await state.set_state(AdminQuestionCreateStates.waiting_for_question_text)
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 4:</b>\n\nأرسل <b>نص السؤال</b>:",
        parse_mode="HTML"
    )


@router.message(AdminQuestionCreateStates.waiting_for_question_text)
async def handle_admin_q_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(question=message.text.strip())
    await state.set_state(AdminQuestionCreateStates.waiting_for_choice_a)
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 5:</b>\n\nأرسل <b>الخيار A</b>:",
        parse_mode="HTML"
    )


@router.message(AdminQuestionCreateStates.waiting_for_choice_a)
async def handle_admin_q_choice_a(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(choice_a=message.text.strip())
    await state.set_state(AdminQuestionCreateStates.waiting_for_choice_b)
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 6:</b>\n\nأرسل <b>الخيار B</b>:",
        parse_mode="HTML"
    )


@router.message(AdminQuestionCreateStates.waiting_for_choice_b)
async def handle_admin_q_choice_b(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(choice_b=message.text.strip())
    await state.set_state(AdminQuestionCreateStates.waiting_for_choice_c)
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 7:</b>\n\nأرسل <b>الخيار C</b>:",
        parse_mode="HTML"
    )


@router.message(AdminQuestionCreateStates.waiting_for_choice_c)
async def handle_admin_q_choice_c(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(choice_c=message.text.strip())
    await state.set_state(AdminQuestionCreateStates.waiting_for_choice_d)
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 8:</b>\n\nأرسل <b>الخيار D</b>:",
        parse_mode="HTML"
    )


@router.message(AdminQuestionCreateStates.waiting_for_choice_d)
async def handle_admin_q_choice_d(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(choice_d=message.text.strip())
    await state.set_state(AdminQuestionCreateStates.waiting_for_correct)
    
    # Select correct answer keyboard
    correct_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="A", callback_data="admin_q_correct:a"),
            InlineKeyboardButton(text="B", callback_data="admin_q_correct:b"),
            InlineKeyboardButton(text="C", callback_data="admin_q_correct:c"),
            InlineKeyboardButton(text="D", callback_data="admin_q_correct:d")
        ],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_create_cancel")]
    ])
    await message.answer(
        "➕ <b>إضافة سؤال جديد - الخطوة 9:</b>\n\nاختر <b>الإجابة الصحيحة</b>:",
        reply_markup=correct_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_q_correct:"))
async def handle_admin_q_correct(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    current_state = await state.get_state()
    if current_state != AdminQuestionCreateStates.waiting_for_correct:
        await callback.answer("⚠️ انتهت صلاحية هذه الجلسة.")
        return
    ans = callback.data.split(":")[1]
    await state.update_data(correct_answer=ans)
    await state.set_state(AdminQuestionCreateStates.waiting_for_explanation)
    await callback.message.edit_text(
        "➕ <b>إضافة سؤال جديد - الخطوة 10:</b>\n\nأرسل <b>شرح الإجابة</b>، أو أرسل /skip لتخطي الشرح:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_create_cancel")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminQuestionCreateStates.waiting_for_explanation)
async def handle_admin_q_explanation(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    exp = ""
    if message.text.strip() != "/skip":
        exp = message.text.strip()
    await state.update_data(explanation=exp)
    
    # Show confirmation
    data = await state.get_data()
    sub_ar = SUBJECT_MAP.get(data['subject'], data['subject'])
    
    text = (
        "🔍 <b>معاينة السؤال قبل الإضافة:</b>\n\n"
        f"📚 <b>المادة:</b> {sub_ar}\n"
        f"📖 <b>الدرس:</b> {data['course_number']} - {data['course_name']}\n\n"
        f"❓ <b>السؤال:</b>\n<blockquote>{data['question']}</blockquote>\n"
        f"🇦 {data['choice_a']}\n"
        f"🇧 {data['choice_b']}\n"
        f"🇨 {data['choice_c']}\n"
        f"🇩 {data['choice_d']}\n\n"
        f"✅ <b>الإجابة الصحيحة:</b> {data['correct_answer'].upper()}\n"
        f"💬 <b>الشرح:</b> {data['explanation'] or '<i>لا يوجد</i>'}\n\n"
        "⚠️ هل أنت متأكد من إضافة هذا السؤال إلى قاعدة البيانات؟"
    )
    await state.set_state(AdminQuestionCreateStates.waiting_for_confirmation)
    await message.answer(text, reply_markup=kb.get_question_confirm_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_q_confirm_save")
@router.callback_query(F.data == "admin_q_confirm_cancel")
async def handle_admin_q_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    action = callback.data
    if action == "admin_q_confirm_save":
        data = await state.get_data()
        # Validate that we have all required fields in data
        if not all(k in data for k in ['subject', 'course_number', 'question', 'choice_a', 'choice_b', 'choice_c', 'choice_d', 'correct_answer']):
            await callback.message.edit_text(
                "❌ <b>حدث خطأ: فقدان بعض البيانات المطلوبة.</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")]
                ]),
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        q_id = await db.add_question_to_db(data)
        await callback.message.edit_text(
            f"✅ <b>تمت إضافة السؤال بنجاح!</b>\n\nمعرّف السؤال الجديد: <code>{q_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")]
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ تم إلغاء إضافة السؤال.")
        await cmd_admin(callback, state)
    await state.clear()
    await callback.answer()


# --- Admin Question Search & View/Delete Handlers ---

@router.callback_query(F.data == "admin_search_question")
async def handle_admin_search_question(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminQuestionSearchStates.waiting_for_question_id)
    await callback.message.edit_text(
        "🔍 <b>البحث عن سؤال:</b>\n\nأرسل <b>معرّف السؤال (ID)</b> الذي ترغب في عرضه وتعديله أو حذفه:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_search_cancel")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_q_search_cancel")
async def handle_admin_q_search_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await cmd_admin(callback, state)


@router.message(AdminQuestionSearchStates.waiting_for_question_id)
async def handle_admin_search_q_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("⚠️ يرجى إدخال معرّف رقمي صحيح:")
        return
    
    q_id = int(txt)
    q = await db.get_question_by_id(q_id)
    if not q:
        await message.answer(
            f"❌ السؤال رقم <code>{q_id}</code> غير موجود في قاعدة البيانات. حاول مرة أخرى أو أرسل /cancel للعودة للوحة الإدارة:",
            parse_mode="HTML"
        )
        return
    
    await state.clear()
    sub_ar = SUBJECT_MAP.get(q['subject'], q['subject'])
    
    text = (
        f"🔍 <b>بيانات السؤال #{q['id']}:</b>\n\n"
        f"📚 <b>المادة:</b> {sub_ar}\n"
        f"📖 <b>الدرس:</b> {q['course_number']} - {q['course_name']}\n\n"
        f"❓ <b>السؤال:</b>\n<blockquote>{q['question']}</blockquote>\n"
        f"🇦 {q['choice_a']}\n"
        f"🇧 {q['choice_b']}\n"
        f"🇨 {q['choice_c']}\n"
        f"🇩 {q['choice_d']}\n\n"
        f"✅ <b>الإجابة الصحيحة:</b> {q['correct_answer'].upper()}\n"
        f"💬 <b>الشرح:</b> {q['explanation'] or '<i>لا يوجد</i>'}"
    )
    await message.answer(text, reply_markup=kb.get_admin_question_view_keyboard(q_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_search_question_by_id:"))
async def handle_admin_search_question_by_id(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    q = await db.get_question_by_id(q_id)
    if not q:
        await callback.message.edit_text("❌ السؤال غير موجود.")
        return
    
    await state.clear()
    sub_ar = SUBJECT_MAP.get(q['subject'], q['subject'])
    
    text = (
        f"🔍 <b>بيانات السؤال #{q['id']}:</b>\n\n"
        f"📚 <b>المادة:</b> {sub_ar}\n"
        f"📖 <b>الدرس:</b> {q['course_number']} - {q['course_name']}\n\n"
        f"❓ <b>السؤال:</b>\n<blockquote>{q['question']}</blockquote>\n"
        f"🇦 {q['choice_a']}\n"
        f"🇧 {q['choice_b']}\n"
        f"🇨 {q['choice_c']}\n"
        f"🇩 {q['choice_d']}\n\n"
        f"✅ <b>الإجابة الصحيحة:</b> {q['correct_answer'].upper()}\n"
        f"💬 <b>الشرح:</b> {q['explanation'] or '<i>لا يوجد</i>'}"
    )
    await callback.message.edit_text(text, reply_markup=kb.get_admin_question_view_keyboard(q_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_question_delete:"))
async def handle_admin_question_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"⚠️ <b>هل أنت متأكد تماماً من حذف السؤال #{q_id} نهائياً؟</b>\n\nلا يمكن التراجع عن هذا الإجراء وسيتم حذفه من جميع تقارير ومفضلة الطلاب.",
        reply_markup=kb.get_admin_question_delete_confirm_keyboard(q_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_question_delete_confirm:"))
async def handle_admin_question_delete_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    q_id = int(callback.data.split(":")[1])
    success = await db.delete_question_from_db(q_id)
    if success:
        await callback.answer("🗑️ تم حذف السؤال بنجاح.")
        await callback.message.edit_text(
            f"✅ تم حذف السؤال #{q_id} بنجاح من قاعدة البيانات.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")]
            ])
        )
    else:
        await callback.answer("❌ فشل حذف السؤال.")
        await callback.message.edit_text(
            "❌ حدث خطأ أثناء محاولة حذف السؤال.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")]
            ])
        )


# --- Admin Student Management Handlers ---

STUDENTS_PER_PAGE = 8

@router.callback_query(F.data == "admin_manage_students")
async def handle_admin_manage_students(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await show_students_page(callback.message, page=1)


async def show_students_page(message: Message, page: int):
    users = await db.get_all_users()
    total_users = len(users)
    
    import math
    total_pages = max(1, math.ceil(total_users / STUDENTS_PER_PAGE))
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
        
    start_idx = (page - 1) * STUDENTS_PER_PAGE
    end_idx = start_idx + STUDENTS_PER_PAGE
    page_users = users[start_idx:end_idx]
    
    text = (
        f"👥 <b>إدارة الطلاب ({total_users} طالب مسجل):</b>\n\n"
        "اختر طالباً من القائمة أدناه لعرض تفاصيله أو تعديل صلاحياته وحظره:"
    )
    
    keyboard = kb.get_admin_students_keyboard(page_users, page=page, total_pages=total_pages)
    
    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_students_page:"))
async def handle_admin_students_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    page = int(callback.data.split(":")[1])
    await show_students_page(callback.message, page)


@router.callback_query(F.data == "admin_students_noop")
async def handle_admin_students_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("admin_student_detail:"))
async def handle_admin_student_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    parts = callback.data.split(":")
    student_id = int(parts[1])
    return_page = int(parts[2])
    
    user = await db.get_user(student_id)
    if not user:
        await callback.message.edit_text(
            "❌ لم يتم العثور على بيانات الطالب.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة للقائمة", callback_data=f"admin_students_page:{return_page}")]
            ])
        )
        return
    
    is_banned = bool(user.get("is_banned"))
    is_admin_user = is_admin(student_id)
    role = await db.get_admin_role(student_id)
    role_str = "طالب"
    if is_admin_user:
        role_str = f"مشرف ({role or 'super_admin'})"
    
    stats = await db.get_user_overall_stats(student_id)
    contributions = await db.get_user_contributions_count(student_id)
    
    preferred_name = user.get("preferred_name")
    first_name = user.get("first_name") or "طالب"
    username = user.get("username")
    gender = user.get("gender")
    gender_str = "ذكر 👦" if gender == "male" else "أنثى 👧" if gender == "female" else "غير محدد"
    
    display_name = preferred_name if preferred_name else first_name
    
    text = (
        f"👤 <b>تفاصيل حساب الطالب:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>الاسم:</b> {display_name}\n"
        f"• <b>اسم المستخدم:</b> @{username or 'لا يوجد'}\n"
        f"• <b>المعرّف الرقمي:</b> <code>{student_id}</code>\n"
        f"• <b>الجنس:</b> {gender_str}\n"
        f"• <b>تاريخ التسجيل:</b> {user.get('created_at') or 'غير معروف'}\n\n"
        f"🔑 <b>الصلاحية:</b> <b>{role_str}</b>\n"
        f"🚫 <b>حالة الحساب:</b> <b>{'محظور 🚫' if is_banned else 'نشط 🟢'}</b>\n\n"
        f"📊 <b>إحصائيات حل الأسئلة:</b>\n"
        f"• الأسئلة الصحيحة: <b>{stats['correct']}</b>\n"
        f"• الأسئلة الخاطئة: <b>{stats['wrong']}</b>\n"
        f"• بلاغات الطلاب المقدمة: <b>{contributions}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"اختر أحد الإجراءات للتحكم بالحساب:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_student_detail_keyboard(student_id, is_banned, is_admin_user, return_page),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_student_toggle_ban:"))
async def handle_admin_student_toggle_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    parts = callback.data.split(":")
    student_id = int(parts[1])
    return_page = int(parts[2])
    
    if student_id == callback.from_user.id:
        await callback.answer("⚠️ لا يمكنك حظر نفسك!", show_alert=True)
        return
        
    user = await db.get_user(student_id)
    if not user:
        await callback.answer("⚠️ الطالب غير موجود.", show_alert=True)
        return
        
    is_currently_banned = bool(user.get("is_banned"))
    new_ban_status = not is_currently_banned
    
    await db.set_user_ban_status(student_id, new_ban_status)
    await callback.answer(f"{'🚫 تم حظر الطالب' if new_ban_status else '🟢 تم إلغاء حظر الطالب'}")
    
    callback.data = f"admin_student_detail:{student_id}:{return_page}"
    await handle_admin_student_detail(callback)


@router.callback_query(F.data.startswith("admin_student_toggle_admin:"))
async def handle_admin_student_toggle_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    parts = callback.data.split(":")
    student_id = int(parts[1])
    return_page = int(parts[2])
    
    if student_id == callback.from_user.id:
        await callback.answer("⚠️ لا يمكنك تعديل صلاحية نفسك!", show_alert=True)
        return
        
    user = await db.get_user(student_id)
    if not user:
        await callback.answer("⚠️ الطالب غير موجود.", show_alert=True)
        return
        
    is_currently_admin = is_admin(student_id)
    
    if is_currently_admin:
        await db.remove_admin_from_db(student_id)
        await callback.answer("🎓 تم تنزيل رتبة الحساب إلى طالب.")
    else:
        username = user.get("username") or ""
        first_name = user.get("first_name") or ""
        await db.add_admin_to_db(student_id, "moderator", username, first_name, added_by=callback.from_user.id)
        await callback.answer("👑 تم ترقية الطالب إلى مشرف.")
        
    callback.data = f"admin_student_detail:{student_id}:{return_page}"
    await handle_admin_student_detail(callback)


@router.callback_query(F.data == "admin_student_search")
async def handle_admin_student_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStudentManageStates.waiting_for_search_query)
    await callback.message.edit_text(
        "🔍 <b>البحث عن طالب:</b>\n\nأرسل جزءاً من الاسم أو اسم المستخدم للبحث عنه:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_manage_students")]
        ]),
        parse_mode="HTML"
    )


@router.message(AdminStudentManageStates.waiting_for_search_query)
async def handle_admin_student_search_query(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    query = message.text.strip().lower()
    await state.clear()
    
    users = await db.get_all_users()
    matches = []
    for u in users:
        first_name = (u.get("first_name") or "").lower()
        preferred_name = (u.get("preferred_name") or "").lower()
        username = (u.get("username") or "").lower()
        telegram_id_str = str(u.get("telegram_id"))
        if (query in first_name or 
            query in preferred_name or 
            query in username or 
            query == telegram_id_str):
            matches.append(u)
            
    if not matches:
        await message.answer(
            "❌ لم يتم العثور على أي نتائج مطابقة. حاول مرة أخرى أو أرسل /cancel للعودة:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة لإدارة الطلاب", callback_data="admin_manage_students")]
            ])
        )
        return
        
    text = f"🔍 <b>نتائج البحث ({len(matches)} مطابقة):</b>\n\nاختر طالباً لمشاهدة تفاصيله:"
    keyboard = kb.get_admin_students_keyboard(matches[:15], page=1, total_pages=1)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def get_main_db_course_name(subject: str, lesson_num: int) -> str:
    import aiosqlite
    from config import MAIN_DATABASE_PATH
    try:
        async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
            async with db.execute(
                "SELECT DISTINCT course_name FROM transcript_segments WHERE subject = ? AND course_number = ? AND course_name != '' LIMIT 1",
                (subject, lesson_num)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
    except Exception as e:
        logger.error(f"Error fetching course name: {e}")
    return f"الدرس {lesson_num}"


async def get_course_video_url(subject: str, lesson_num: int) -> str:
    import aiosqlite
    import os
    import re
    from config import MAIN_DATABASE_PATH
    try:
        async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
            async with db.execute(
                "SELECT video_url FROM course_videos WHERE subject = ? AND course_number = ? LIMIT 1",
                (subject, lesson_num)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return row[0]
    except Exception as e:
        logger.error(f"Error fetching course video URL from database: {e}")

    # Fallback: check raw transcription file for YouTube link
    try:
        base_dir = os.path.dirname(os.path.dirname(MAIN_DATABASE_PATH))
        transcript_path = os.path.join(base_dir, "lessons", "transcripts", subject, f"{subject}_{lesson_num}.txt")
        if os.path.exists(transcript_path):
            with open(transcript_path, "r", encoding="utf-8") as f:
                # Read first few lines (usually line 3 or so has the link)
                lines = [f.readline() for _ in range(10)]
                for line in lines:
                    if "youtube.com" in line or "youtu.be" in line:
                        # Extract URL from line: check if it has markdown format [text](url) or is plain url
                        match = re.search(r'(https?://[^\s\)]+)', line)
                        if match:
                            return match.group(1)
    except Exception as e:
        logger.error(f"Error reading video url fallback from transcript file: {e}")
    return ""


async def get_transcript_segment_count(subject: str, lesson_num: int) -> int:
    import aiosqlite
    from config import MAIN_DATABASE_PATH
    try:
        async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM transcript_segments WHERE subject = ? AND course_number = ?",
                (subject, lesson_num)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
    except Exception as e:
        logger.error(f"Error counting transcript segments: {e}")
    return 0


async def get_full_transcript(subject: str, lesson_num: int) -> str:
    import aiosqlite
    from config import MAIN_DATABASE_PATH
    try:
        async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
            async with db.execute(
                "SELECT timestamp, content FROM transcript_segments WHERE subject = ? AND course_number = ? ORDER BY seconds ASC, id ASC",
                (subject, lesson_num)
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    return "\n".join([f"[{r[0]}] {r[1]}" for r in rows if r[1]])
    except Exception as e:
        logger.error(f"Error loading transcript segments: {e}")
    return ""


def normalize_theme(theme_val: str, subject: str) -> str:
    if not theme_val:
        return ""
    theme_lower = theme_val.lower().strip()
    
    if subject == "fiqh":
        # Map variations to 'عبادات' or 'معاملات'
        if any(w in theme_lower for w in ["adoration", "عبادات", "ibadat", "ibadah", "worship"]):
            return "عبادات"
        if any(w in theme_lower for w in ["transaction", "معاملات", "muamalat", "commerce"]):
            return "معاملات"
            
    elif subject == "aqeeda":
        if any(w in theme_lower for w in ["tawhid", "توحيد", "عقيدة", "aqeeda"]):
            return "tawhid"
        if any(w in theme_lower for w in ["firaq", "فرق", "ولاء", "براء"]):
            return "firaq"
            
    elif subject == "nahw":
        if any(w in theme_lower for w in ["marfouat", "مرفوعات", "منصوبات", "nominatif"]):
            return "marfouat"
        if any(w in theme_lower for w in ["tawabi", "توابع", "أساليب"]):
            return "tawabi"
            
    elif subject == "sira":
        # Battles/Campaigns
        if any(w in theme_lower for w in ["bataille", "expedition", "غزوة", "غزوات", "سرية", "سرايا"]):
            return "الغزوات والسرايا"
        # Household/Life
        if any(w in theme_lower for w in ["vie personnelle", "maison", "famille", "بيت النبوة", "زوجات"]):
            return "بيت النبوة والحياة الشخصية"
        # Worship/Legislation
        if any(w in theme_lower for w in ["adoration", "legislation", "عبادات", "معاملات", "تشريع"]):
            return "العبادات والمعاملات والتشريعات"
        # Companions
        if any(w in theme_lower for w in ["compagnons", "sahaba", "صحابة", "مجتمع"]):
            return "الصحابة والمجتمع المدني"
        # Treaties/Delegations
        if any(w in theme_lower for w in ["traité", "delegation", "delegations", "عهود", "وفود", "علاقات"]):
            return "العهود والوفود والعلاقات الخارجية"
        # Prophet qualities
        if any(w in theme_lower for w in ["qualités", "ethique", "description", "شمائل", "أخلاق"]):
            return "الشمائل والأخلاق النبوية"

    return theme_val


async def generate_questions_from_text(prompt_text: str, subject: str, course_number: int = None, model_name: str = 'gemini-flash-latest', count: int = 5, custom_instruction: str = '') -> list[dict] | None:
    """
    Call Gemini API using google-generativeai SDK to generate structured MCQs.
    Returns a list of question dicts, or None if failed.
    """
    import google.generativeai as genai
    from config import GEMINI_API_KEYS, GEMINI_API_KEY
    import json
    import re
    
    api_keys = GEMINI_API_KEYS if GEMINI_API_KEYS else ([GEMINI_API_KEY] if GEMINI_API_KEY else [])
    if not api_keys:
        logger.error("No Gemini API keys are configured.")
        return None
        
    # Use provided model or default to gemini-flash-latest
    actual_model_name = model_name or 'gemini-flash-latest'
    
    try:
        # Query existing chapters/axes of the course from database to force classification
        existing_chapters = []
        if course_number:
            try:
                chaps = await db.get_course_chapters(subject, course_number)
                existing_chapters = [c["title"].strip() for c in chaps if c.get("title")]
            except Exception as e:
                logger.error(f"Error fetching course chapters for MCQ factory: {e}")

        # Build subject-specific instruction for classification
        if existing_chapters:
            allowed_themes_str = "\n".join([f"  * \"{title}\"" for title in existing_chapters])
            subject_classification = (
                f"- theme: Must be one of these exact Arabic axes/categories representing the chapters of this course:\n"
                f"{allowed_themes_str}\n"
                f"If the question does not match any specific axis, use the most relevant one from this list.\n"
                f"- hijra_year: An integer representing the year of the Hijrah (from 2 to 10) if the question refers to an event from a specific year. If not associated with a specific year or not Sira, use null."
            )
        elif subject == "sira":
            subject_classification = (
                "- theme: Must be one of these exact Arabic categories representing Sira families:\n"
                "  * \"الغزوات والسرايا\" (battles, campaigns, military expeditions)\n"
                "  * \"بيت النبوة والحياة الشخصية\" (the Prophet's ﷺ life, his family, wives, children, and personal household)\n"
                "  * \"العبادات والمعاملات والتشريعات\" (worship rulings, transactions, and legislations revealed during the Sira)\n"
                "  * \"الصحابة والمجتمع المدني\" (Companions, Medinan society, and social environment)\n"
                "  * \"العهود والوفود والعلاقات الخارجية\" (treaties, delegations, external relations, and agreements)\n"
                "  * \"الشمائل والأخلاق النبوية\" (Prophet's ﷺ moral character, physical attributes, ethics, and descriptions)\n"
                "- hijra_year: An integer representing the year of the Hijrah (from 2 to 10) if the question refers to an event from a specific year. If not associated with a specific year, use null."
            )
        elif subject == "fiqh":
            subject_classification = (
                "- theme: Must be either \"عبادات\" or \"معاملات\".\n"
                "- hijra_year: Always null."
            )
        elif subject == "nahw":
            subject_classification = (
                "- theme: Must be either \"marfouat\" or \"tawabi\".\n"
                "- hijra_year: Always null."
            )
        elif subject == "tajweed":
            subject_classification = (
                "- theme: Must be the main Tajweed rule being tested (e.g. \"أحكام النون الساكنة\", \"المدود\").\n"
                "- IMPORTANT: Create practical questions where you provide a short Quranic verse (Ayah) or word mentioned in the lesson, and ask the student to identify the Tajweed rule applied. Ensure you ONLY use verses that are explicitly written in the provided text to avoid any errors in the Quranic text.\n"
                "- Prefix the question with \"🟣 \" so the admin knows this is a new Tajweed question to verify.\n"
                "- hijra_year: Always null."
            )
        elif subject == "aqeeda":
            subject_classification = (
                "- theme: Must be either \"tawhid\" or \"firaq\".\n"
                "- hijra_year: Always null."
            )
        else:
            subject_classification = (
                "- theme: A general category name.\n"
                "- hijra_year: Always null."
            )

        custom_prompt_addon = ""
        if custom_instruction:
            custom_prompt_addon = f"\nSpecific focus/instruction from the user: {custom_instruction}\n"

        system_instruction = (
            f"You are an expert Islamic studies teacher. Your task is to generate exactly {count} multiple choice questions (MCQs) in Arabic based ONLY on the lesson transcript provided by the user. "
            "Each segment in the transcript is prefixed with its timestamp in square brackets like [MM:SS] or [H:MM:SS].\n"
            f"Return the output as a valid JSON array of exactly {count} objects. Each object MUST have the following keys:\n"
            "- question: The question text in Arabic (clear, grammatically correct, and challenging, in bold style without HTML tags).\n"
            "- choice_a: Option A in Arabic.\n"
            "- choice_b: Option B in Arabic.\n"
            "- choice_c: Option C in Arabic.\n"
            "- choice_d: Option D in Arabic.\n"
            "- correct_answer: The correct option letter, which must be exactly 'a', 'b', 'c', or 'd'.\n"
            "- pedagogical_explanation: A brief, clear, and structured explanation of the correct answer in Arabic (3-4 sentences). Use <b>...</b> HTML tags around key terms or concepts to emphasize them in bold.\n"
            "- prof_quote: The exact, verbatim Arabic sentence(s) spoken by the professor in the transcript that directly answers or supports this question. Do not include the timestamp inside this field. You can also wrap key terms in <b>...</b> HTML tags.\n"
            "- quote_timestamp: The exact timestamp prefix (e.g. '12:34' or '1:02:15') of the transcript segment that contains the prof_quote.\n"
            f"{subject_classification}\n"
            f"{custom_prompt_addon}\n"
            f"Do not include any Markdown formatting like ```json or ```. Return raw JSON text only."
        )
        
        prompt = f"System Instructions: {system_instruction}\n\nHere is the transcript text:\n{prompt_text}"
        
        response_text = None
        last_error = None
        for current_key in api_keys:
            try:
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(actual_model_name)
                response = await model.generate_content_async(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                response_text = response.text.strip()
                if response_text:
                    break
            except Exception as ex:
                logger.warning(f"Failed admin generation with key {current_key[:10]}...: {ex}")
                last_error = ex
                continue

        if not response_text:
            raise last_error or Exception("Toutes les clés API ont échoué lors de la génération admin.")
            
        match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = response_text
            
        questions = json.loads(json_str)
        if isinstance(questions, list):
            return questions
        elif isinstance(questions, dict) and "questions" in questions:
            return questions["questions"]
        return None
    except Exception as e:
        logger.error(f"Error calling Gemini API in admin: {e}", exc_info=True)
        return None

@router.callback_query(F.data.startswith("adm_fac_course:"))
async def handle_adm_fac_course_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await state.update_data(subject=subject, course_number=lesson)
    
    # Fetch course name
    course_name = await get_main_db_course_name(subject, lesson)
    await state.update_data(course_name=course_name)
    
    # Fetch segments count
    count = await get_transcript_segment_count(subject, lesson)
    
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    text = (
        f"⚙️ <b>تفاصيل الدرس المختار للإنتاج (IA):</b>\n\n"
        f"• <b>المادة:</b> {sub_ar}\n"
        f"• <b>الدرس:</b> {lesson} - {course_name}\n"
        f"• <b>عدد مقاطع التفريغ المتوفرة:</b> {count} مقطع\n\n"
    )
    
    buttons = []
    if count > 0:
        text += "اختر أحد الخيارات أدناه لتوليد الأسئلة بالذكاء الاصطناعي :\n\n" \
                "⚙️ <b>تهيئة معايير التوليد:</b> اختيار النموذج، عدد الأسئلة، وإدخال تعليمات خاصة.\n" \
                "⚡ <b>توليد سريع:</b> البدء فوراً بإنتاج 5 أسئلة بالنموذج الافتراضي وبدون تعليمات."
        buttons.append([InlineKeyboardButton(text="⚙️ تهيئة معايير التوليد", callback_data=f"adm_fac_config_start:{subject}:{lesson}")])
        buttons.append([InlineKeyboardButton(text="⚡ توليد 5 أسئلة مباشرة (سريع)", callback_data=f"adm_fac_gen:{subject}:{lesson}")])
    else:
        text += "⚠️ لا يمكن توليد الأسئلة لعدم توفر تفريغ نصي لهذا الدرس في قاعدة البيانات."
        
    buttons.append([InlineKeyboardButton(text="↩️ العودة لقائمة الدروس", callback_data=f"adm_fac_sub:{subject}")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_fac_config_start:"))
async def handle_adm_fac_config_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await state.set_state(AdminQuestionFactoryStates.waiting_for_model)
    await callback.message.edit_text(
        "🤖 <b>الخطوة 1: اختيار نموذج الذكاء الاصطناعي</b>\n\n"
        "يرجى تحديد النموذج المناسب لتوليد الأسئلة (الموصى به هو Gemini Flash Latest) :",
        reply_markup=kb.get_admin_model_selection_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(AdminQuestionFactoryStates.waiting_for_model, F.data.startswith("adm_fac_model:"))
async def handle_adm_fac_model_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    model_name = callback.data.split(":")[1]
    await state.update_data(model_name=model_name)
    
    await state.set_state(AdminQuestionFactoryStates.waiting_for_count)
    await callback.message.edit_text(
        "📊 <b>الخطوة 2: اختيار عدد الأسئلة المطلوبة</b>\n\n"
        "يرجى اختيار عدد الأسئلة التي ترغب في توليدها من تفريغ الدرس :",
        reply_markup=kb.get_admin_count_selection_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(AdminQuestionFactoryStates.waiting_for_count, F.data.startswith("adm_fac_count:"))
async def handle_adm_fac_count_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    count = int(callback.data.split(":")[1])
    await state.update_data(count=count)
    
    await state.set_state(AdminQuestionFactoryStates.waiting_for_instruction)
    await callback.message.edit_text(
        "✍️ <b>الخطوة 3: تعليمات خاصة أو تركيز ثنائي (اختياري)</b>\n\n"
        "إذا كنت ترغب في أن يركز الذكاء الاصطناعي على جزئية معينة من الدرس أو يتبع أسلوباً خاصاً، "
        "يرجى كتابة وإرسال التعليمات كرسالة نصية الآن.\n\n"
        "أو اضغط على الزر أدناه لتخطي هذه الخطوة والبدء بالتوليد فوراً :",
        reply_markup=kb.get_admin_skip_instruction_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(AdminQuestionFactoryStates.waiting_for_instruction, F.data == "adm_fac_inst:skip")
async def handle_adm_fac_inst_skip(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.update_data(custom_instruction="")
    await start_ai_question_generation(callback.message, state)


@router.message(AdminQuestionFactoryStates.waiting_for_instruction)
async def handle_adm_fac_inst_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    instruction = message.text.strip()
    await state.update_data(custom_instruction=instruction)
    await start_ai_question_generation(message, state)


async def start_ai_question_generation(message: Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject")
    lesson = data.get("course_number")
    model_name = data.get("model_name", "gemini-flash-latest")
    count = data.get("count", 5)
    custom_instruction = data.get("custom_instruction", "")
    
    # Send / Edit loading message
    loading_msg = await message.answer(
        f"⏳ <b>جاري التحضير والتوليد...</b>\n\n"
        f"• النموذج المستخدم: <code>{model_name}</code>\n"
        f"• عدد الأسئلة المطلوبة: <b>{count}</b>\n"
        f"• التعليمات المخصصة: <i>{custom_instruction or 'لا يوجد'}</i>\n\n"
        f"يرجى الانتظار، قد يستغرق ذلك حوالي 10-30 ثانية.",
        parse_mode="HTML"
    )
    
    # Load transcript text
    transcript_text = await get_full_transcript(subject, lesson)
    if not transcript_text:
        await loading_msg.edit_text(
            "❌ <b>فشل التوليد:</b> لم يتم العثور على أي تفريغ نصي لهذا الدرس في قاعدة البيانات الرئيسية.\n\n"
            "تأكد من وجود تفريغات في جدول <code>transcript_segments</code>.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة لقائمة الدروس", callback_data=f"adm_fac_sub:{subject}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    # Generate via Gemini
    questions = await generate_questions_from_text(
        transcript_text, 
        subject, 
        course_number=lesson, 
        model_name=model_name, 
        count=count, 
        custom_instruction=custom_instruction
    )
    
    if not questions:
        await loading_msg.edit_text(
            "❌ <b>فشل توليد الأسئلة:</b> حدث خطأ أثناء الاتصال بخدمة Gemini أو تعذر معالجة النص.\n\n"
            "يرجى المحاولة مجدداً لاحقاً.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة لقائمة الدروس", callback_data=f"adm_fac_sub:{subject}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    # Get course name
    course_name = await get_main_db_course_name(subject, lesson)
    video_url = await get_course_video_url(subject, lesson)
    
    def timestamp_to_seconds(ts: str) -> int:
        try:
            parts = list(map(int, ts.split(":")))
            if len(parts) == 2:  # MM:SS
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:  # H:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except Exception:
            pass
        return 0
        
    import re
    # Clean youtube URL
    cleaned_video_url = ""
    if video_url:
        cleaned_video_url = re.sub(r'[&?](t|start)=\d+\w*', '', video_url)
        
    # Process explanations with standard formatting markers (💡, 📖, 📍)
    formatted_questions = []
    for idx, q in enumerate(questions):
        ped = q.get("pedagogical_explanation", "").strip()
        quote = q.get("prof_quote", "").strip()
        tstamp = q.get("quote_timestamp", "").strip()
        
        # Build YouTube Link with timestamp
        youtube_link = ""
        if cleaned_video_url and tstamp:
            secs = timestamp_to_seconds(tstamp)
            if secs > 0:
                connector = "&" if "?" in cleaned_video_url else "?"
                youtube_link = f"{cleaned_video_url}{connector}t={secs}s"
            else:
                youtube_link = cleaned_video_url
                
        # Build raw HTML structure for source block
        sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
        course_name_clean = course_name.strip() if course_name else ""
        if not course_name_clean or course_name_clean == f"الدرس {lesson}":
            source_text = f"<b>{sub_ar} - الدرس {lesson}</b>"
        else:
            source_text = f"<b>{sub_ar} - الدرس {lesson} ({course_name_clean})</b>"
 
        if youtube_link and tstamp:
            source_text += f"، الدقيقة <a href=\"{youtube_link}\"><b>[{tstamp}]</b></a>\n<i>(اضغط على التوقيت للانتقال لشرح الفيديو 🎥)</i>"
        elif youtube_link:
            source_text += f"، <a href=\"{youtube_link}\"><b>[مشاهدة الفيديو]</b></a>\n<i>(اضغط على الرابط لمشاهدة الفيديو 🎥)</i>"
        else:
            source_text += f"، تفريغ الدرس (الدقيقة {tstamp})"
            
        teacher = SUBJECT_TEACHERS.get(subject, "الشيخ")
        expl_text = (
            f"💡 <b>التفسير التربوي :</b>\n"
            f"<blockquote>{ped}</blockquote>\n\n"
            f"📖 <b>{teacher} يقول :</b>\n"
            f"<blockquote>{quote}</blockquote>\n\n"
            f"📍 <b>المصدر :</b>\n"
            f"<blockquote>{source_text}</blockquote>"
        )
        
        theme_val = normalize_theme(q.get("theme", "").strip() if q.get("theme") else "", subject)
        hijra_val = q.get("hijra_year")
        if hijra_val is not None:
            try:
                hijra_val = int(hijra_val)
            except Exception:
                hijra_val = None
 
        formatted_questions.append({
            "question": q.get("question", "").strip(),
            "choice_a": q.get("choice_a", "").strip(),
            "choice_b": q.get("choice_b", "").strip(),
            "choice_c": q.get("choice_c", "").strip(),
            "choice_d": q.get("choice_d", "").strip(),
            "correct_answer": q.get("correct_answer", "a").strip().lower(),
            "explanation": expl_text,
            "theme": theme_val,
            "hijra_year": hijra_val
        })
        
    await state.update_data(
        subject=subject,
        course_number=lesson,
        course_name=course_name,
        generated_questions=formatted_questions,
        current_index=0,
        accepted_count=0
    )
    
    try:
        await loading_msg.delete()
    except Exception:
        pass
        
    await state.set_state(AdminQuestionFactoryStates.reviewing_questions)
    await show_factory_question_review(message, state)



async def show_factory_question_review(message: Message, state: FSMContext):
    data = await state.get_data()
    questions = data['generated_questions']
    idx = data['current_index']
    
    if idx >= len(questions):
        accepted_cnt = data.get('accepted_count', 0)
        try:
            await message.edit_text(
                f"🏁 <b>اكتملت مراجعة جميع الأسئلة المقترحة!</b>\n\n"
                f"• الأسئلة التي تم قبولها وحفظها: <b>{accepted_cnt}</b> من {len(questions)} أسئلة.\n\n"
                f"تم تحديث قاعدة البيانات بنجاح.",
                reply_markup=await _get_admin_keyboard(message.chat.id),
                parse_mode="HTML"
            )
        except Exception:
            await message.answer(
                f"🏁 <b>اكتملت مراجعة جميع الأسئلة المقترحة!</b>\n\n"
                f"• الأسئلة التي تم قبولها وحفظها: <b>{accepted_cnt}</b> من {len(questions)} أسئلة.\n\n"
                f"تم تحديث قاعدة البيانات بنجاح.",
                reply_markup=await _get_admin_keyboard(message.chat.id),
                parse_mode="HTML"
            )
        await state.clear()
        return
        
    q = questions[idx]
    
    theme_text = q.get('theme') or 'غير مصنف'
    
    hijra_line = ""
    if data.get('subject') == 'sira':
        hijra_year_val = q.get('hijra_year')
        hijra_text = f"{hijra_year_val} هـ" if hijra_year_val else "غير محدد"
        hijra_line = f"📅 <b>السنة الهجرية (Hijri Year):</b> {hijra_text}\n"

    text = (
        f"📝 <b>السؤال المقترح {idx + 1} من {len(questions)}:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ <b>السؤال:</b>\n<blockquote>{q.get('question')}</blockquote>\n"
        f"🇦 {q.get('choice_a')}\n"
        f"🇧 {q.get('choice_b')}\n"
        f"🇨 {q.get('choice_c')}\n"
        f"🇩 {q.get('choice_d')}\n\n"
        f"✅ <b>الإجابة الصحيحة:</b> {q.get('correct_answer', '').upper()}\n"
        f"🎯 <b>المحور (Thématique):</b> {theme_text}\n"
        f"{hijra_line}\n"
        f"💬 <b>الشرح والتفسير:</b> {q.get('explanation') or 'لا يوجد'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"اختر الإجراء المطلوب لهذا السؤال:"
    )
    
    try:
        await message.edit_text(
            text,
            reply_markup=kb.get_admin_q_factory_review_keyboard(),
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception:
        await message.answer(
            text,
            reply_markup=kb.get_admin_q_factory_review_keyboard(),
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )


@router.callback_query(F.data == "admin_q_fac_accept")
async def handle_admin_q_fac_accept(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    data = await state.get_data()
    questions = data['generated_questions']
    idx = data['current_index']
    q = questions[idx]
    
    # Save to database
    q_data = {
        "subject": data["subject"],
        "course_number": data["course_number"],
        "course_name": data["course_name"],
        "question": q["question"],
        "choice_a": q["choice_a"],
        "choice_b": q["choice_b"],
        "choice_c": q["choice_c"],
        "choice_d": q["choice_d"],
        "correct_answer": q["correct_answer"].lower(),
        "explanation": q.get("explanation", ""),
        "source": "generated_by_gemini",
        "hijra_year": q.get("hijra_year"),
        "theme": q.get("theme", "")
    }
    await db.add_question_to_db(q_data)

    await state.update_data(
        accepted_count=data.get('accepted_count', 0) + 1,
        current_index=idx + 1
    )
    await show_factory_question_review(callback.message, state)


@router.callback_query(F.data == "admin_q_factory_menu")
async def handle_admin_q_factory_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminQuestionFactoryStates.waiting_for_subject)
    
    # Get global AI generated stats
    coverage = await db.get_ai_coverage_stats()
    def get_subj_count(subj: str) -> int:
        return sum(coverage.get(subj, {}).values())

    subjects_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"الفقه ({get_subj_count('fiqh')})", callback_data="adm_fac_sub:fiqh")],
        [InlineKeyboardButton(text=f"السيرة النبوية ({get_subj_count('sira')})", callback_data="adm_fac_sub:sira")],
        [InlineKeyboardButton(text=f"النحو ({get_subj_count('nahw')})", callback_data="adm_fac_sub:nahw")],
        [InlineKeyboardButton(text=f"العقيدة ({get_subj_count('aqeeda')})", callback_data="adm_fac_sub:aqeeda")],
        [InlineKeyboardButton(text="📊 لوحة تغطية الأسئلة (Missing IA Dashboard)", callback_data="admin_ai_coverage_dashboard")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_factory_cancel")]
    ])
    await callback.message.edit_text(
        "⚙️ <b>مصنع الأسئلة بالذكاء الاصطناعي (IA) - الخطوة 1:</b>\n\nاختر المادة الدراسية لتوليد الأسئلة لها أو استعرض لوحة التغطية :",
        reply_markup=subjects_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_ai_coverage_dashboard")
async def handle_admin_ai_coverage_dashboard(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    kb_dashboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="الفقه (fiqh)", callback_data="adm_cov_sub:fiqh")],
        [InlineKeyboardButton(text="السيرة النبوية (sira)", callback_data="adm_cov_sub:sira")],
        [InlineKeyboardButton(text="النحو (nahw)", callback_data="adm_cov_sub:nahw")],
        [InlineKeyboardButton(text="العقيدة (aqeeda)", callback_data="adm_cov_sub:aqeeda")],
        [InlineKeyboardButton(text="↩️ العودة لمصنع الأسئلة", callback_data="admin_q_factory_menu")]
    ])
    await callback.message.edit_text(
        "📊 <b>لوحة تغطية الأسئلة الذكية (IA Coverage Dashboard):</b>\n\n"
        "اختر المادة الدراسية لعرض تقرير التغطية وتحديد الدروس التي تحتاج لتوليد أسئلة :",
        reply_markup=kb_dashboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_cov_sub:"))
async def handle_adm_cov_sub_selected(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    subject = callback.data.split(":")[1]
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    # Get stats
    coverage = await db.get_ai_coverage_stats()
    transcripts = await db.get_transcript_availability()
    
    subject_cov = coverage.get(subject, {})
    subject_trans = transcripts.get(subject, set())
    
    text = f"📊 <b>حالة تغطية الأسئلة الذكية (IA) - مادة {sub_ar}:</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    buttons = []
    row = []
    
    for lesson in range(14, 25):
        cnt = subject_cov.get(lesson, 0)
        has_trans = lesson in subject_trans
        
        if cnt >= 5:
            status = f"🟢 <b>{cnt} أسئلة</b>"
        elif cnt > 0:
            status = f"🟡 <b>{cnt} أسئلة</b> (تغطية جزئية)"
        else:
            if has_trans:
                status = "❌ <b>بدون أسئلة</b> (التفريغ متوفر جاهز ⚡)"
            else:
                status = "⚠️ <b>بدون أسئلة</b> (لا يوجد تفريغ نصي 🚫)"
                
        text += f"• <b>الدرس {lesson}:</b> {status}\n"
        
        # If it has transcripts, add a button to generate questions directly
        if has_trans:
            btn_text = f"⚙️ توليد للدرس {lesson}"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=f"adm_fac_course:{subject}:{lesson}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
                
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="↩️ تغيير المادة", callback_data="admin_ai_coverage_dashboard")])
    buttons.append([InlineKeyboardButton(text="↩️ العودة لمصنع الأسئلة", callback_data="admin_q_factory_menu")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )



@router.callback_query(F.data == "admin_q_factory_cancel")
async def handle_admin_q_factory_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ تم إلغاء توليد الأسئلة.")
    await cmd_admin(callback, state)


@router.callback_query(F.data.startswith("adm_fac_sub:"))
async def handle_adm_fac_sub_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    subject = callback.data.split(":")[1]
    await state.update_data(subject=subject)
    await state.set_state(AdminQuestionFactoryStates.waiting_for_course)
    await callback.answer()
    
    # Generate lessons grid 14 to 24
    coverage = await db.get_ai_coverage_stats()
    subj_coverage = coverage.get(subject, {})

    buttons = []
    row = []
    for lesson in range(14, 25):
        count = await get_transcript_segment_count(subject, lesson)
        ai_count = subj_coverage.get(lesson, 0)

        if count > 0:
            btn_text = f"الدرس {lesson} ({ai_count} أسئلة ذكية)"
        else:
            btn_text = f"الدرس {lesson} (غير متوفر ⚠️)"
        
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"adm_fac_course:{subject}:{lesson}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_q_factory_cancel")])
    
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    await callback.message.edit_text(
        f"⚙️ <b>مصنع الأسئلة (IA) - مادة {sub_ar}:</b>\n\n"
        f"اختر الدرس لتوليد الأسئلة له (النطاق 14-24):\n"
        f"✅ = تفريغ الدرس متوفر في قاعدة البيانات الرئيسية.\n"
        f"⚠️ = لا يوجد تفريغ لهذا الدرس.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )






@router.callback_query(F.data.startswith("adm_fac_gen:"))
async def handle_adm_fac_generate(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await callback.answer("⏳ جاري التحضير والتوليد...")
    
    # Loading message
    loading_msg = await callback.message.edit_text(
        "⏳ <b>جاري تحميل تفريغ الدرس وتوليد 5 أسئلة ذكية عبر الذكاء الاصطناعي...</b>\n\n"
        "يرجى الانتظار، قد يستغرق ذلك حوالي 10-20 ثانية.",
        reply_markup=None,
        parse_mode="HTML"
    )
    
    # Load transcript text
    transcript_text = await get_full_transcript(subject, lesson)
    if not transcript_text:
        await loading_msg.edit_text(
            "❌ <b>فشل التوليد:</b> لم يتم العثور على أي تفريغ نصي لهذا الدرس في قاعدة البيانات الرئيسية.\n\n"
            "تأكد من وجود تفريغات في جدول <code>transcript_segments</code>.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة لقائمة الدروس", callback_data=f"adm_fac_sub:{subject}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    # Generate via Gemini
    questions = await generate_questions_from_text(transcript_text, subject)
    
    if not questions:
        await loading_msg.edit_text(
            "❌ <b>فشل توليد الأسئلة:</b> حدث خطأ أثناء الاتصال بخدمة Gemini أو تعذر معالجة النص.\n\n"
            "يرجى المحاولة مجدداً لاحقاً.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة لقائمة الدروس", callback_data=f"adm_fac_sub:{subject}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    # Get course name
    course_name = await get_main_db_course_name(subject, lesson)
    video_url = await get_course_video_url(subject, lesson)
    
    def timestamp_to_seconds(ts: str) -> int:
        try:
            parts = list(map(int, ts.split(":")))
            if len(parts) == 2:  # MM:SS
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:  # H:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except Exception:
            pass
        return 0
        
    import re
    # Clean youtube URL
    cleaned_video_url = ""
    if video_url:
        cleaned_video_url = re.sub(r'[&?](t|start)=\d+\w*', '', video_url)
        
    # Process explanations with standard formatting markers (💡, 📖, 📍)
    formatted_questions = []
    for idx, q in enumerate(questions):
        ped = q.get("pedagogical_explanation", "").strip()
        quote = q.get("prof_quote", "").strip()
        tstamp = q.get("quote_timestamp", "").strip()
        
        # Build YouTube Link with timestamp
        youtube_link = ""
        if cleaned_video_url and tstamp:
            secs = timestamp_to_seconds(tstamp)
            if secs > 0:
                connector = "&" if "?" in cleaned_video_url else "?"
                youtube_link = f"{cleaned_video_url}{connector}t={secs}s"
            else:
                youtube_link = cleaned_video_url
                
        # Build raw HTML structure for source block
        sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
        course_name_clean = course_name.strip() if course_name else ""
        if not course_name_clean or course_name_clean == f"الدرس {lesson}":
            source_text = f"<b>{sub_ar} - الدرس {lesson}</b>"
        else:
            source_text = f"<b>{sub_ar} - الدرس {lesson} ({course_name_clean})</b>"

        if youtube_link and tstamp:
            source_text += f"، الدقيقة <a href=\"{youtube_link}\"><b>[{tstamp}]</b></a>\n<i>(اضغط على التوقيت للانتقال لشرح الفيديو 🎥)</i>"
        elif youtube_link:
            source_text += f"، <a href=\"{youtube_link}\"><b>[مشاهدة الفيديو]</b></a>\n<i>(اضغط على الرابط لمشاهدة الفيديو 🎥)</i>"
        else:
            source_text += f"، تفريغ الدرس (الدقيقة {tstamp})"
            
        teacher = SUBJECT_TEACHERS.get(subject, "الشيخ")
        expl_text = (
            f"💡 <b>التفسير التربوي :</b>\n"
            f"<blockquote>{ped}</blockquote>\n\n"
            f"📖 <b>{teacher} يقول :</b>\n"
            f"<blockquote>{quote}</blockquote>\n\n"
            f"📍 <b>المصدر :</b>\n"
            f"<blockquote>{source_text}</blockquote>"
        )
        
        theme_val = normalize_theme(q.get("theme", "").strip() if q.get("theme") else "", subject)
        hijra_val = q.get("hijra_year")
        if hijra_val is not None:
            try:
                hijra_val = int(hijra_val)
            except Exception:
                hijra_val = None

        formatted_questions.append({
            "question": q.get("question", "").strip(),
            "choice_a": q.get("choice_a", "").strip(),
            "choice_b": q.get("choice_b", "").strip(),
            "choice_c": q.get("choice_c", "").strip(),
            "choice_d": q.get("choice_d", "").strip(),
            "correct_answer": q.get("correct_answer", "a").strip().lower(),
            "explanation": expl_text,
            "theme": theme_val,
            "hijra_year": hijra_val
        })
        
    await state.update_data(
        subject=subject,
        course_number=lesson,
        course_name=course_name,
        generated_questions=formatted_questions,
        current_index=0,
        accepted_count=0
    )
    
    await loading_msg.delete()
    await state.set_state(AdminQuestionFactoryStates.reviewing_questions)
    await show_factory_question_review(callback.message, state)


@router.callback_query(F.data == "admin_q_fac_reject")
async def handle_admin_q_fac_reject(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    data = await state.get_data()
    idx = data['current_index']
    
    await state.update_data(current_index=idx + 1)
    await show_factory_question_review(callback.message, state)


@router.callback_query(F.data == "admin_q_fac_cancel")
async def handle_admin_q_fac_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("❌ تم إلغاء العملية والعودة للوحة الإدارة.")
    await cmd_admin(callback, state)


@router.callback_query(F.data == "admin_q_fac_edit")
async def handle_admin_q_fac_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.set_state(AdminQuestionFactoryStates.editing_question)
    
    await callback.message.reply(
        "✏️ <b>تعديل السؤال المقترح:</b>\n\n"
        "أرسل الصيغة المعدلة كاملة في رسالة واحدة بالتنسيق التالي:\n\n"
        "<code>السؤال | خيار A | خيار B | خيار C | خيار D | حرف الإجابة (a/b/c/d) | الشرح</code>\n\n"
        "تأكد من فصل الحقول الـ 7 باستخدام الرمز <code>|</code>",
        parse_mode="HTML"
    )


@router.message(AdminQuestionFactoryStates.editing_question)
async def handle_adm_fac_edited_msg(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) < 6:
        await message.answer("⚠️ الصيغة غير صحيحة. يجب إدخال 6 حقول على الأقل مفصولة بـ | (السؤال | A | B | C | D | الإجابة | الشرح اختيارياً):")
        return
        
    correct_ans = parts[5].lower()
    if correct_ans not in ['a', 'b', 'c', 'd']:
        await message.answer("⚠️ حرف الإجابة الصحيحة يجب أن يكون a أو b أو c أو d:")
        return
        
    explanation = parts[6] if len(parts) > 6 else ""
    
    data = await state.get_data()
    questions = data['generated_questions']
    idx = data['current_index']
    
    # Update question in FSM memory
    questions[idx] = {
        "question": parts[0],
        "choice_a": parts[1],
        "choice_b": parts[2],
        "choice_c": parts[3],
        "choice_d": parts[4],
        "correct_answer": correct_ans,
        "explanation": explanation
    }
    
    await state.update_data(generated_questions=questions)
    await state.set_state(AdminQuestionFactoryStates.reviewing_questions)
    await message.answer("✅ تم تحديث السؤال المقترح. يرجى مراجعته مجدداً:")
    await show_factory_question_review(message, state)



# --- Admin Revision Resources Management ---

class AdminResourcesStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_trans_page = State()
    waiting_for_map_page = State()


@router.callback_query(F.data == "admin_manage_resources")
async def handle_admin_manage_resources(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📂 <b>إدارة ملفات المراجعة للطلاب:</b>\n\nاختر المادة الدراسية لرفع أو تحديث ملخصاتها وخرائطها الذهنية:",
        reply_markup=kb.get_admin_resources_subject_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_res_sub:"))
async def handle_adm_res_sub(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    subject = callback.data.split(":")[1]
    
    lessons_status = await db.get_all_lessons_with_resources(subject)
    sub_ar = SUBJECT_MAP.get(subject, subject)
    
    await callback.message.edit_text(
        f"📂 <b>إدارة ملفات المراجعة (مادة {sub_ar}):</b>\n\n"
        f"علامات الملفات الرافقة:\n"
        f"🗺️ = خريطة ذهنية متوفرة | 📄 = ملخص PDF متوفر\n\n"
        f"اختر رقم الدرس المطلوب لإدارته:",
        reply_markup=kb.get_admin_resources_lessons_keyboard(subject, lessons_status),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_res_les:"))
async def handle_adm_res_les(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    resources = await db.get_lesson_resources(subject, lesson)
    has_map = bool(resources and resources.get("mind_map_file_id"))
    has_sum = bool(resources and resources.get("summary_file_id"))
    
    trans_pages = await db.get_transcription_pages(subject, lesson)
    trans_count = len(trans_pages)
    has_trans = trans_count > 0
    
    sub_ar = SUBJECT_MAP.get(subject, subject)
    text = (
        f"📁 <b>ملفات الدرس {lesson} (مادة {sub_ar}):</b>\n\n"
        f"• الخريطة الذهنية (PNG): <b>{'متوفرة ✅' if has_map else 'غير متوفرة ❌'}</b>\n"
        f"• الملخص الدراسي (PDF): <b>{'متوفرة ✅' if has_sum else 'غير متوفرة ❌'}</b>\n"
        f"• صفحات التفريغ (PNG): <b>{f'{trans_count} صفحة ✅' if has_trans else 'غير متوفرة ❌'}</b>\n\n"
        f"اختر الإجراء المطلوب للرفع أو التحديث:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_admin_resources_manage_keyboard(subject, lesson, has_map, has_sum, has_trans),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_upl_map:"))
async def handle_adm_upl_map(callback: CallbackQuery, state: FSMContext):
    """Admin taps 'upload/update mind map'. If pages already exist, show replace-vs-add choice."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    existing_pages = await db.get_mind_map_pages(subject, lesson)
    if existing_pages:
        # Let admin choose whether to replace or add a page
        count = len(existing_pages)
        sub_ar = SUBJECT_MAP.get(subject, subject)
        await callback.message.edit_text(
            f"📌 <b>الخريطة الذهنية للدرس {lesson} ({sub_ar}):</b>\n\n"
            f"يوجد حالياً <b>{count}</b> صفحة خريطة لهذا الدرس.\n\n"
            f"ماذا تريد أن تفعل؟",
            reply_markup=kb.get_admin_map_action_keyboard(subject, lesson, count),
            parse_mode="HTML"
        )
    else:
        # No existing pages — go straight to file upload
        await state.update_data(upload_type="mind_map", subject=subject, lesson=lesson, map_mode="replace")
        await state.set_state(AdminResourcesStates.waiting_for_map_page)
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_res_les:{subject}:{lesson}")]
        ])
        await callback.message.edit_text(
            "📸 <b>رفع الخريطة الذهنية (PNG):</b>\n\n"
            "يرجى إرسال ملف الصورة (PNG) أو إرسالها كصورة عادية في الخاص:",
            reply_markup=cancel_kb,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("adm_upl_sum:"))
async def handle_adm_upl_trigger(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    await state.update_data(
        upload_type="summary",
        subject=subject,
        lesson=lesson
    )
    await state.set_state(AdminResourcesStates.waiting_for_file)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_res_les:{subject}:{lesson}")]
    ])
    await callback.message.edit_text(
        "📄 <b>رفع ملخص الدرس (PDF):</b>\n\n"
        "يرجى إرسال ملف ملخص الدرس بصيغة PDF (مستند) في الخاص:",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_map_replace:"))
async def handle_adm_map_replace(callback: CallbackQuery, state: FSMContext):
    """Admin chose to replace all mind map pages."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    await state.update_data(subject=subject, lesson=lesson, map_mode="replace")
    await state.set_state(AdminResourcesStates.waiting_for_map_page)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_res_les:{subject}:{lesson}")]
    ])
    await callback.message.edit_text(
        "🔄 <b>استبدال الخريطة الذهنية (PNG):</b>\n\n"
        "سيتم حذف جميع الصفحات الحالية واستبدالها بهذه الصورة.\n"
        "يرجى إرسال ملف الصورة (PNG) أو إرسالها كصورة:",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_map_add_page:"))
async def handle_adm_map_add_page(callback: CallbackQuery, state: FSMContext):
    """Admin chose to add a new mind map page."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])

    existing_pages = await db.get_mind_map_pages(subject, lesson)
    next_page = len(existing_pages) + 1

    await state.update_data(subject=subject, lesson=lesson, map_mode="add")
    await state.set_state(AdminResourcesStates.waiting_for_map_page)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_res_les:{subject}:{lesson}")]
    ])
    await callback.message.edit_text(
        f"➕ <b>إضافة صفحة {next_page} للخريطة الذهنية (PNG):</b>\n\n"
        "يرجى إرسال ملف الصورة (PNG) أو إرسالها كصورة:",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(AdminResourcesStates.waiting_for_map_page)
async def handle_adm_map_page_received(message: Message, state: FSMContext):
    """Receive a mind map image and save it (replace all or add page)."""
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    subject = data['subject']
    lesson = data['lesson']
    map_mode = data.get('map_mode', 'replace')

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await message.answer("⚠️ يرجى إرسال صورة صالحة (PNG أو صورة عادية) أو أرسل /cancel للإلغاء:")
        return

    if map_mode == "replace":
        await db.delete_all_mind_map_pages(subject, lesson)
        await db.add_mind_map_page(subject, lesson, 1, file_id)
        # Also update legacy column for compatibility
        await db.save_lesson_resources(subject, lesson, "mind_map", file_id)
        page_num = 1
        action_ar = "تم استبدال"
    else:
        existing_pages = await db.get_mind_map_pages(subject, lesson)
        page_num = len(existing_pages) + 1
        await db.add_mind_map_page(subject, lesson, page_num, file_id)
        action_ar = f"تمت إضافة الصفحة {page_num} من"

    await state.clear()
    sub_ar = SUBJECT_MAP.get(subject, subject)
    await message.answer(
        f"✅ <b>{action_ar} خريطة الدرس {lesson} (مادة {sub_ar}) بنجاح!</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة لقائمة الملفات", callback_data=f"adm_res_les:{subject}:{lesson}")]
        ]),
        parse_mode="HTML"
    )


async def show_admin_trans_pages_mgmt(target, subject: str, lesson: int):
    trans_pages = await db.get_transcription_pages(subject, lesson)
    pages_count = len(trans_pages)
    
    sub_ar = SUBJECT_MAP.get(subject, subject)
    text = (
        f"📝 <b>صفحات تفريغ الدرس {lesson} (مادة {sub_ar}) :</b>\n\n"
    )
    if pages_count > 0:
        text += f"تم رفع <b>{pages_count}</b> صفحة تفريغ للدرس حتى الآن :\n"
        for p in trans_pages:
            text += f"• الصفحة {p['page_number']} : ✅ متوفرة\n"
    else:
        text += "⚠️ لا توجد أي صفحات تفريغ حالياً لهذا الدرس."
        
    text += "\n\nيمكنك إضافة صفحة جديدة أو مسح كل الصفحات الحالية :"
    
    reply_markup = kb.get_admin_trans_pages_keyboard(subject, lesson, pages_count)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=reply_markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_manage_trans_pages:"))
async def handle_adm_manage_trans_pages(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    await show_admin_trans_pages_mgmt(callback, subject, lesson)


@router.callback_query(F.data.startswith("adm_add_trans_page:"))
async def handle_adm_add_trans_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await state.update_data(subject=subject, lesson=lesson)
    await state.set_state(AdminResourcesStates.waiting_for_trans_page)
    
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_manage_trans_pages:{subject}:{lesson}")]
    ])
    await callback.message.edit_text(
        "📸 <b>إضافة صفحة تفريغ جديدة (PNG):</b>\n\n"
        "يرجى إرسال صورة الصفحة (PNG) أو إرسالها كصورة عادية في الخاص.\n"
        "سيتم إضافتها تلقائياً كصفحة تالية.",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(AdminResourcesStates.waiting_for_trans_page)
async def handle_adm_trans_page_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    subject = data['subject']
    lesson = data['lesson']
    
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await message.answer("⚠️ يرجى إرسال صورة صالحة (الصفحة بصيغة PNG أو صورة عادية) أو أرسل /cancel للإلغاء:")
        return
        
    # Get current pages count to compute the next page number
    existing_pages = await db.get_transcription_pages(subject, lesson)
    next_page_num = len(existing_pages) + 1
    
    # Save page
    await db.add_transcription_page(subject, lesson, next_page_num, file_id)
    await state.clear()
    
    sub_ar = SUBJECT_MAP.get(subject, subject)
    await message.answer(
        f"✅ <b>تم إضافة الصفحة {next_page_num} بنجاح للدرس {lesson} (مادة {sub_ar})!</b>"
    )
    # Redirect back to pages management
    await show_admin_trans_pages_mgmt(message, subject, lesson)


@router.callback_query(F.data.startswith("adm_clear_trans_pages:"))
async def handle_adm_clear_trans_pages(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await db.delete_all_transcription_pages(subject, lesson)
    await callback.answer("🗑️ تم مسح جميع صفحات تفriغ هذا الدرس.", show_alert=True)
    await show_admin_trans_pages_mgmt(callback, subject, lesson)


@router.callback_query(F.data == "admin_test_ai_questions")
async def handle_admin_test_ai_questions(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
        
    await callback.answer("⏳ جاري تحميل أسئلة الذكاء الاصطناعي...")
    
    # Retrieve AI questions from DB
    questions = await db.get_ai_questions()
    
    if not questions:
        await callback.message.answer(
            "⚠️ لا توجد أسئلة تم إنشاؤها بواسطة الذكاء الاصطناعي في قاعدة البيانات حالياً.\n\n"
            "يمكنك توليد بعض الأسئلة أولاً عبر قسم « مصنع الأسئلة (IA) »."
        )
        return
        
    # We will launch the quiz using the exact same flow as quiz.py
    # Limit to 20 questions, randomize them
    import random
    random.shuffle(questions)
    questions = questions[:20]
    
    from handlers.quiz import QuizStates, DEFAULT_SETTINGS, show_question
    
    await state.set_state(QuizStates.answering)
    await state.update_data(
        subject="AI_Test",
        mode="ai_test",
        questions=questions,
        current_index=0,
        answers={},
        times={},
        results={},
        settings={
            "timer": "unlimited",
            "correction": "immediate",
            "order": "random",
            "source": "all",
            "origin": "ai"
        },
        continue_mode=False
    )
    
    # Render the first question to the admin using show_question from quiz.py
    await show_question(callback, state)


# --- Study Path Active Reading Generation (Admin) ---

class AdminStudyPathStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_course = State()
    waiting_for_paste = State()
    waiting_for_model = State()
    waiting_for_instruction = State()
    generating = State()



@router.callback_query(F.data == "admin_study_path_mgmt")
async def handle_admin_study_path_mgmt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⚠️ لست مشرفاً.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStudyPathStates.waiting_for_subject)
    
    subjects_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="الفقه (fiqh)", callback_data="adm_path_sub:fiqh")],
        [InlineKeyboardButton(text="السيرة النبوية (sira)", callback_data="adm_path_sub:sira")],
        [InlineKeyboardButton(text="النحو (nahw)", callback_data="adm_path_sub:nahw")],
        [InlineKeyboardButton(text="العقيدة (aqeeda)", callback_data="adm_path_sub:aqeeda")],
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_close")]
    ])
    await callback.message.edit_text(
        "📖 <b>توليد مسارات القراءة التفاعلية (Active Study) - الخطوة 1:</b>\n\nاختر المادة الدراسية لتوليد مسار القراءة لها:",
        reply_markup=subjects_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_path_sub:"))
async def handle_adm_path_sub_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    subject = callback.data.split(":")[1]
    await state.update_data(subject=subject)
    await state.set_state(AdminStudyPathStates.waiting_for_course)
    await callback.answer()
    
    # Generate lessons grid 14 to 24
    buttons = []
    row = []
    for lesson in range(14, 25):
        # We can check if chapters already exist for this lesson
        existing_chaps = await db.get_course_chapters(subject, lesson)
        if existing_chaps:
            btn_text = f"الدرس {lesson} (مفعّل ✅)"
        else:
            count = await get_transcript_segment_count(subject, lesson)
            if count > 0:
                btn_text = f"الدرس {lesson} (جاهز للتوليد ⚡)"
            else:
                btn_text = f"الدرس {lesson} (بدون تفريغ ⚠️)"
        
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"adm_path_course:{subject}:{lesson}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_study_path_mgmt")])
    
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    await callback.message.edit_text(
        f"📖 <b>مسارات القراءة (Active Study) - مادة {sub_ar}:</b>\n\n"
        f"اختر الدرس لتوليد أو مراجعة مسار القراءة له (النطاق 14-24):\n"
        f"✅ = مسار القراءة مفعّل ومخزن بالكامل.\n"
        f"⚡ = تفريغ الدرس متوفر وجاهز للتحويل بواسطة الذكاء الاصطناعي.\n"
        f"⚠️ = لا يوجد تفريغ نصي متوفر للدرس.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_path_course:"))
async def handle_adm_path_course_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await state.update_data(subject=subject, course_number=lesson)
    course_name = await get_main_db_course_name(subject, lesson)
    
    # Check if chapters already exist
    existing_chaps = await db.get_course_chapters(subject, lesson)
    sub_ar = kb.SUBJECT_LABELS.get(subject, subject)
    
    text = (
        f"📖 <b>تفاصيل مسار القراءة - {sub_ar}:</b>\n\n"
        f"• <b>الدرس:</b> {lesson} - {course_name}\n"
    )
    
    buttons = []
    if existing_chaps:
        text += f"• <b>الحالة:</b> مفعّل ومقسم إلى <b>{len(existing_chaps)} فصول</b> ✅\n\n"
        # Option to overwrite or delete
        buttons.append([InlineKeyboardButton(text="🔄 إعادة توليد المسار بالكامل (IA)", callback_data=f"adm_path_gen:{subject}:{lesson}")])
        buttons.append([InlineKeyboardButton(text="🗑️ مسح المسار الحالي", callback_data=f"adm_path_clear:{subject}:{lesson}")])
    else:
        text += "• <b>الحالة:</b> ⚠️ غير مفعّل بعد (لا توجد فصول مخزنة).\n\n"
        count = await get_transcript_segment_count(subject, lesson)
        if count > 0:
            text += "التفريغ متوفر. اضغط على الزر أدناه ليقوم الذكاء الاصطناعي بقراءته وتقسيمه إلى فصول منطقية متسلسلة حسب المعنى وتوليد الأسئلة المصاحبة."
            buttons.append([InlineKeyboardButton(text="✨ توليد مسار القراءة الآن", callback_data=f"adm_path_gen:{subject}:{lesson}")])
        else:
            text += "⚠️ لا يمكن توليد مسار القراءة لعدم توفر تفريغ نصي لهذا الدرس."
            
    buttons.append([InlineKeyboardButton(text="↩️ العودة لقائمة الدروس", callback_data=f"adm_path_sub:{subject}")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_path_clear:"))
async def handle_adm_path_clear(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    # We delete by deleting the course chapters, cascade takes care of questions
    async with db.aiosqlite.connect(db.DATABASE_PATH) as conn:
        await conn.execute("DELETE FROM course_chapters WHERE subject = ? AND course_number = ?", (subject, lesson))
        await conn.commit()
        
    await callback.answer("🗑️ تم مسح مسار القراءة بنجاح.", show_alert=True)
    await handle_adm_path_course_selected(callback, state)


@router.callback_query(F.data.startswith("adm_path_gen:"))
async def handle_adm_path_generate(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    subject = parts[1]
    lesson = int(parts[2])
    
    await state.update_data(subject=subject, course_number=lesson)
    
    # Check if we have a transcript in database
    db_count = await get_transcript_segment_count(subject, lesson)
    
    buttons = []
    if db_count > 0:
        buttons.append([InlineKeyboardButton(text="📄 استخدام تفريغ الدرس المتوفر في قاعدة البيانات", callback_data=f"adm_path_gen_src:db:{subject}:{lesson}")])
    buttons.append([InlineKeyboardButton(text="✍️ لصق نص الدرس يدوياً الآن", callback_data=f"adm_path_gen_src:paste:{subject}:{lesson}")])
    buttons.append([InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_path_course:{subject}:{lesson}")])
    
    await callback.message.edit_text(
        "📖 <b>توليد مسار القراءة (Axes) - تحديد مصدر النص:</b>\n\n"
        "يرجى تحديد الطريقة التي ترغب من خلالها في تزويد الذكاء الاصطناعي بنص الدرس لتجزئته وإنتاج المحاور :",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_path_gen_src:"))
async def handle_adm_path_gen_src(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    parts = callback.data.split(":")
    source_type = parts[1]
    subject = parts[2]
    lesson = int(parts[3])
    
    if source_type == "db":
        await state.update_data(source_type="db", custom_text=None)
        await state.set_state(AdminStudyPathStates.waiting_for_model)
        await callback.message.edit_text(
            "🤖 <b>توليد مسار القراءة - الخطوة 1: اختيار نموذج الذكاء الاصطناعي</b>\n\n"
            "يرجى تحديد النموذج المناسب لتوليد مسار القراءة والأسئلة (الموصى به هو Gemini Flash Latest) :",
            reply_markup=kb.get_admin_model_selection_keyboard(),
            parse_mode="HTML"
        )
    elif source_type == "paste":
        await state.set_state(AdminStudyPathStates.waiting_for_paste)
        await callback.message.edit_text(
            "✍️ <b>يرجى لصق وإرسال نص الدرس كاملاً الآن :</b>\n\n"
            "سيقوم البوت بقراءة هذا النص كاملاً وتجزئته إلى محاور تفاعلية للطلاب.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ إلغاء", callback_data=f"adm_path_course:{subject}:{lesson}")]
            ]),
            parse_mode="HTML"
        )


@router.message(AdminStudyPathStates.waiting_for_paste)
async def handle_adm_path_paste_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    subject = data.get("subject")
    lesson = data.get("course_number")
    
    pasted_text = message.text.strip()
    if len(pasted_text) < 100:
        await message.answer("⚠️ النص قصير جداً! يرجى لصق نص الدرس بالكامل (على الأقل 100 حرف).")
        return
        
    await state.update_data(source_type="paste", custom_text=pasted_text)
    await state.set_state(AdminStudyPathStates.waiting_for_model)
    await message.answer(
        "🤖 <b>توليد مسار القراءة - الخطوة 1: اختيار نموذج الذكاء الاصطناعي</b>\n\n"
        "يرجى تحديد النموذج المناسب لتوليد مسار القراءة والأسئلة (الموصى به هو Gemini Flash Latest) :",
        reply_markup=kb.get_admin_model_selection_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(AdminStudyPathStates.waiting_for_model, F.data.startswith("adm_fac_model:"))
async def handle_adm_path_model_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    model_name = callback.data.split(":")[1]
    await state.update_data(model_name=model_name)
    
    await state.set_state(AdminStudyPathStates.waiting_for_instruction)
    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ تخطي والبدء بالتوليد فوراً", callback_data="adm_path_inst:skip")]
    ])
    
    await callback.message.edit_text(
        "✍️ <b>الخطوة 2: تعليمات خاصة أو تركيز ثنائي (اختياري)</b>\n\n"
        "إذا كنت ترغب في أن يركز الذكاء الاصطناعي على جزئية معينة من الدرس أثناء التقسيم والتلخيص، "
        "يرجى كتابة وإرسال التعليمات كرسالة نصية الآن.\n\n"
        "أو اضغط على الزر أدناه لتخطي هذه الخطوة والبدء بالتوليد فوراً :",
        reply_markup=skip_kb,
        parse_mode="HTML"
    )


@router.callback_query(AdminStudyPathStates.waiting_for_instruction, F.data == "adm_path_inst:skip")
async def handle_adm_path_inst_skip(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.update_data(custom_instruction="")
    
    data = await state.get_data()
    subject = data.get("subject")
    lesson = data.get("course_number")
    source_type = data.get("source_type")
    custom_text = data.get("custom_text")
    
    await run_study_path_generation(callback.message, state, subject, lesson, source_type=source_type, custom_text=custom_text)


@router.message(AdminStudyPathStates.waiting_for_instruction)
async def handle_adm_path_inst_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    instruction = message.text.strip()
    await state.update_data(custom_instruction=instruction)
    
    data = await state.get_data()
    subject = data.get("subject")
    lesson = data.get("course_number")
    source_type = data.get("source_type")
    custom_text = data.get("custom_text")
    
    await run_study_path_generation(message, state, subject, lesson, source_type=source_type, custom_text=custom_text)


async def run_study_path_generation(message: Message, state: FSMContext, subject: str, lesson: int, source_type: str, custom_text: str = None):
    # Loading message
    loading_msg = await message.answer(
        "⏳ <b>جاري قراءة نص الدرس وتحليله بواسطة الذكاء الاصطناعي...</b>\n\n"
        "سيقوم المعالج بتقسيم النص إلى محاور وأجزاء منطقية مترابطة، وتوليد سؤال قراءة نشطة لكل محور.\n\n"
        "يرجى الانتظار، قد يستغرق هذا من 15 إلى 30 ثانية.",
        parse_mode="HTML"
    )
    
    # Retrieve model and custom instruction from state
    data = await state.get_data()
    model_name = data.get("model_name", "gemini-flash-latest")
    custom_instruction = data.get("custom_instruction", "")

    # Load transcript text based on source type
    if source_type == "db":
        transcript_text = await get_full_transcript(subject, lesson)
    else:
        transcript_text = custom_text
        
    if not transcript_text:
        await loading_msg.edit_text(
            "❌ <b>فشل التوليد:</b> لم يتم العثور على أي نص للدرس.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة لإدارة الدرس", callback_data=f"adm_path_course:{subject}:{lesson}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    # Call Gemini to partition the text and generate study path
    chapters = await generate_study_path_from_text(transcript_text, subject, lesson, model_name=model_name, custom_instruction=custom_instruction)
    
    if not chapters:
        await loading_msg.edit_text(
            "❌ <b>فشل توليد مسار القراءة:</b> تعذر معالجة النص أو حدث خطأ في استجابة Gemini.\n\n"
            "يرجى المحاولة مجدداً.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ العودة", callback_data=f"adm_path_course:{subject}:{lesson}")]
            ]),
            parse_mode="HTML"
        )
        return
        
    # Overwrite database entries (clean up first)
    async with db.aiosqlite.connect(db.DATABASE_PATH) as conn:
        await conn.execute("DELETE FROM course_chapters WHERE subject = ? AND course_number = ?", (subject, lesson))
        await conn.commit()
        
    video_url = await get_course_video_url(subject, lesson)
    
    def timestamp_to_seconds(ts: str) -> int:
        try:
            parts = list(map(int, ts.split(":")))
            if len(parts) == 2:  # MM:SS
                return parts[0] * 60 + parts[1]
            elif len(parts) == 3:  # H:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except Exception:
            pass
        return 0
        
    import re
    cleaned_video_url = ""
    if video_url:
        cleaned_video_url = re.sub(r'[&?](t|start)=\d+\w*', '', video_url)
        
    # Insert new chapters and their questions
    for idx, ch in enumerate(chapters):
        title = ch.get("title", f"المحور {idx + 1}")
        content = ch.get("content", "").strip()
        ts_str = ch.get("timestamp", "").strip()
        
        ts_seconds = timestamp_to_seconds(ts_str)
        yt_link = None
        if cleaned_video_url and ts_str:
            connector = "&" if "?" in cleaned_video_url else "?"
            yt_link = f"{cleaned_video_url}{connector}t={ts_seconds}"
            
        # Add chapter
        chap_id = await db.add_course_chapter(
            subject=subject,
            course_number=lesson,
            chapter_index=idx + 1,
            title=title,
            content=content,
            youtube_link=yt_link,
            timestamp_seconds=ts_seconds,
            vocabulary_spoilers=ch.get("vocabulary_spoilers", "").strip() or None
        )
        
        # Add question
        q_data = ch.get("question_data", {})
        if q_data:
            # 1. Add as chapter validation question (Active Study)
            await db.add_course_chapter_question(
                chapter_id=chap_id,
                question=q_data.get("question", "").strip(),
                choice_a=q_data.get("choice_a", "").strip(),
                choice_b=q_data.get("choice_b", "").strip(),
                choice_c=q_data.get("choice_c", "").strip() or None,
                choice_d=q_data.get("choice_d", "").strip() or None,
                correct_answer=q_data.get("correct_answer", "a").strip().lower(),
                explanation=q_data.get("explanation", "").strip(),
                hint=q_data.get("hint", "").strip() or None
            )
            
            # 2. Also duplicate into the general questions bank (so it counts as AI questions!)
            teacher = SUBJECT_TEACHERS.get(subject, "الشيخ")
            expl_text = (
                f"💡 <b>التفسير التربوي :</b>\n"
                f"<blockquote>{q_data.get('explanation', '').strip()}</blockquote>\n\n"
                f"📖 <b>{teacher} يقول :</b>\n"
                f"<blockquote>مقتطف من المحور : {title}</blockquote>\n\n"
                f"📍 <b>المصدر :</b>\n"
                f"<blockquote>{kb.SUBJECT_LABELS.get(subject, subject)} - الدرس {lesson} ({title})</blockquote>"
            )
            
            q_general = {
                "subject": subject,
                "course_number": lesson,
                "course_name": course_name,
                "question": q_data.get("question", "").strip(),
                "choice_a": q_data.get("choice_a", "").strip(),
                "choice_b": q_data.get("choice_b", "").strip(),
                "choice_c": q_data.get("choice_c", "").strip() or None,
                "choice_d": q_data.get("choice_d", "").strip() or None,
                "correct_answer": q_data.get("correct_answer", "a").strip().lower(),
                "explanation": expl_text,
                "source": "generated_by_gemini",
                "hijra_year": None,
                "theme": title  # Set theme to chapter title
            }
            await db.add_question_to_db(q_general)
            
    # Propagate axes update to questions theme (synchronization & Option A recategorization)
    try:
        new_axes_titles = [ch.get("title", f"المحور {idx + 1}").strip() for idx, ch in enumerate(chapters) if ch.get("title")]
        if new_axes_titles:
            await recategorize_course_questions_under_new_axes(subject, lesson, new_axes_titles)
    except Exception as e:
        logger.error(f"Error propagating axes update to questions: {e}")

            
    await loading_msg.edit_text(
        f"🏁 <b>اكتمل توليد مسار القراءة بنجاح!</b>\n\n"
        f"• المادة: {kb.SUBJECT_LABELS.get(subject, subject)}\n"
        f"• الدرس: {lesson}\n"
        f"• عدد الفصول/المحاور المنشأة: <b>{len(chapters)} محاور</b>\n\n"
        f"تم حفظ المسار في قاعدة البيانات وأصبح متاحاً للطلاب الآن 🎉",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👁️ معاينة مسار القراءة (وضع الطالب)", callback_data=f"rev_study_path_start:{subject}:{lesson}")],
            [InlineKeyboardButton(text="↩️ العودة لإدارة الدرس", callback_data=f"adm_path_course:{subject}:{lesson}")]
        ]),
        parse_mode="HTML"
    )



async def generate_study_path_from_text(prompt_text: str, subject: str, lesson_num: int, model_name: str = 'gemini-flash-latest', custom_instruction: str = '') -> list[dict] | None:
    """Use Gemini to segment a transcript dynamically into 3-10 logically themed chapters based on meaning transitions, with a QCM question each."""
    import google.generativeai as genai
    from config import GEMINI_API_KEY
    import json
    import re
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured.")
        return None
        
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        actual_model_name = model_name or 'gemini-flash-latest'
        model = genai.GenerativeModel(actual_model_name)

        
        system_instruction = (
            "You are an expert Islamic educator specialized in structured pedagogy. "
            "Your mission is to analyze the following lesson transcript and segment it into thematic chapters, following these STRICT rules:\n\n"

            "## RULE 1 — PEDAGOGICAL COHERENCE & MODERATION (most important rule)\n"
            "Segment the transcript into logical and balanced chapters (axes). Do NOT over-segment into tiny sub-parts. "
            "If two subtopics or concepts are strongly connected and have a logical transition or flow together, KEEP them in the same chapter/axis to maintain continuity.\n"
            "Target calibration: Vise un format standard de 4 à 6 axes majeurs par cours (maximum 7 axes).\n\n"


            "## RULE 2 — VERBATIM CONTENT (mandatory)\n"
            "For each chapter, the 'content' field MUST contain the professor's EXACT original words from the transcript, without any summarization or paraphrasing.\n"
            "- Copy the speech faithfully, word for word.\n"
            "- If there are transcription gaps marked '(...)' in the source, smoothly bridge the gap by reconstructing the logical connection. Do NOT leave '(...)' in your output.\n"
            "- Use '<b>...</b>' strictly to bold key people (e.g. companions, scholars, historical figures), key places (e.g. Mecca, Medina, Uhud), technical vocabulary (e.g. Fard, Sunnah, Mubtada'), or references/citations of Quranic verses or Hadiths. Do not bold other words.\n"
            "- Always use the calligraphic abbreviation symbol 'ﷺ' instead of writing 'صلى الله عليه وسلم' or other long blessing formulas in full (for all fields: content, title, questions, explanations, etc.).\n"
            "- Do NOT use spoiler tags or any other HTML inside the content field.\n\n"

            "## RULE 3 — PAGINATION-FRIENDLY FORMATTING\n"
            "Within each chapter's 'content', separate distinct sub-ideas, examples, or paragraphs using double newlines '\\n\\n'.\n"
            "This is critical: the system will automatically split long chapters into mobile-sized reading pages using '\\n\\n' as breakpoints (~500 characters per page).\n"
            "Write the content as natural paragraphs separated by '\\n\\n', NOT as one single continuous block of text.\n\n"

            "## RULE 4 — VOCABULARY SPOILERS\n"
            "For each chapter, provide 2–5 key terms, vocabulary words, proper nouns, or important dates specific to that chapter.\n"
            "Return them as a plain dash-separated Arabic string (e.g., 'كلمة 1 - كلمة 2 - كلمة 3'). No HTML, no spoiler tags.\n\n"

            "## RULE 5 — TIMESTAMP\n"
            "Provide the exact starting timestamp from the transcript (e.g. '5:23' or '1:02:15') for each chapter.\n\n"

            "## RULE 6 — COMPREHENSION QUESTION\n"
            "For each chapter, generate one MCQ question (question_data) that tests genuine comprehension of that chapter's specific content.\n"
            "  - question: Clear Arabic question.\n"
            "  - choice_a, choice_b: mandatory.\n"
            "  - choice_c, choice_d: optional — include if it makes the question richer.\n"
            "  - correct_answer: the letter of the correct answer ('a', 'b', 'c', or 'd').\n"
            "  - explanation: A short, friendly Arabic explanation of why this answer is correct. PLAIN TEXT ONLY — no HTML tags.\n"
            "  - hint: A helpful Arabic clue pointing to a key word or concept in the chapter. PLAIN TEXT ONLY — no HTML tags.\n\n"

            "## OUTPUT FORMAT\n"
            "Return a valid raw JSON array only (no markdown, no triple backticks). "
            "Each element is an object with exactly these fields: title, content, vocabulary_spoilers, timestamp, question_data."
            f"\nSpecific focus/instruction from the user: {custom_instruction}\n" if custom_instruction else ""
        )
        
        prompt = f"System Instructions: {system_instruction}\n\nHere is the transcript text:\n{prompt_text}"
        
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        response_text = response.text.strip()
        
        match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = response_text
            
        chapters = json.loads(json_str)
        if isinstance(chapters, list):
            return chapters
        return None
    except Exception as e:
        logger.error(f"Error calling Gemini in generate_study_path: {e}", exc_info=True)
        return None


# ─── Admin Question Proposals Management ─────────────────────────────────────

@router.callback_query(F.data == "admin_view_proposals")
async def admin_view_proposals(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    if not is_admin(user_id):
        return
        
    proposals = await db.get_pending_proposals()
    
    text = (
        "📥 <b>إدارة مقترحات الأسئلة المقدمة من الطلاب</b>\n\n"
        f"عدد المقترحات المعلقة: <b>{len(proposals)} اقتراح</b>\n\n"
        "اختر أحد المقترحات أدناه لمراجعته واعتماده أو رفضه:"
    )
    
    SUBJECT_LABELS_LOCAL = {
        "fiqh": "الفقه",
        "sira": "السيرة",
        "nahw": "النحو",
        "aqeeda": "العقيدة"
    }
    
    rows = []
    for p in proposals:
        sub_lbl = SUBJECT_LABELS_LOCAL.get(p["subject"].lower(), p["subject"])
        q_preview = p["question"][:25] + "..." if len(p["question"]) > 25 else p["question"]
        btn_text = f"📚 {sub_lbl} (د {p['course_number']}): {q_preview}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_prop_det:{p['id']}")])
        
    rows.append([InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prop_det:"))
async def admin_proposal_details(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        return
        
    proposal_id = int(callback.data.split(":")[1])
    prop = await db.get_proposal_by_id(proposal_id)
    if not prop:
        await callback.answer("⚠️ لم يتم العثور على هذا الاقتراح.", show_alert=True)
        return
        
    SUBJECT_LABELS_LOCAL = {
        "fiqh": "الفقه",
        "sira": "السيرة النبوية",
        "nahw": "النحو",
        "aqeeda": "العقيدة"
    }
    sub_lbl = SUBJECT_LABELS_LOCAL.get(prop["subject"].lower(), prop["subject"])
    
    choices_text = (
        f"🅰️ <b>أ:</b> {prop['choice_a']}\n"
        f"🅱️ <b>ب:</b> {prop['choice_b']}\n"
    )
    if prop.get("choice_c"):
        choices_text += f"🆃 <b>ج:</b> {prop['choice_c']}\n"
    if prop.get("choice_d"):
        choices_text += f"🆳 <b>د:</b> {prop['choice_d']}\n"
        
    text = (
        f"📝 <b>تفاصيل الاقتراح #{prop['id']}</b>\n"
        f"👤 <b>الطالب:</b> {prop['first_name']} (@{prop['username'] if prop['username'] else '-'})\n"
        f"📚 <b>المادة:</b> {sub_lbl} (الدرس {prop['course_number']})\n"
        f"📅 <b>تاريخ التقديم:</b> {prop['created_at']}\n\n"
        f"❓ <b>السؤال المقترح:</b>\n{prop['question']}\n\n"
        f"📋 <b>الخيارات المتوفرة:</b>\n{choices_text}\n"
        f"✅ <b>الإجابة الصحيحة المحددة:</b> {prop['correct_answer'].upper()}\n"
        f"💡 <b>التوضيح والشرح:</b> {prop['explanation'] or 'لا يوجد'}"
    )
    
    rows = [
        [
            InlineKeyboardButton(text="✅ قبول واعتماد السؤال", callback_data=f"admin_prop_acc:{prop['id']}"),
            InlineKeyboardButton(text="❌ رفض الاقتراح", callback_data=f"admin_prop_rej:{prop['id']}")
        ],
        [InlineKeyboardButton(text="↩️ عودة للقائمة", callback_data="admin_view_proposals")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_prop_acc:"))
async def admin_proposal_accept(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        return
        
    proposal_id = int(callback.data.split(":")[1])
    prop = await db.get_proposal_by_id(proposal_id)
    if not prop:
        await callback.answer("⚠️ الاقتراح غير متوفر.", show_alert=True)
        return
        
    success = await db.accept_proposal(proposal_id)
    if success:
        student_id = prop["user_id"]
        SUBJECT_LABELS_LOCAL = {
            "fiqh": "الفقه",
            "sira": "السيرة النبوية",
            "nahw": "النحو",
            "aqeeda": "العقيدة"
        }
        sub_lbl = SUBJECT_LABELS_LOCAL.get(prop["subject"].lower(), prop["subject"])
        
        student_notify_text = (
            "✨ <b>تم قبول اقتراحك المتميز!</b>\n\n"
            f"لقد اعتمدت الإدارة سؤالك المقترح في مادة <b>{sub_lbl}</b> (الدرس {prop['course_number']}) وتمت إضافته للأسئلة المعتمدة للجميع.\n\n"
            "بارك الله فيك ونفع بك وجزاك الله خيراً على مساهمتك القيمة! 🌹"
        )
        try:
            await callback.bot.send_message(chat_id=student_id, text=student_notify_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Could not notify student {student_id} of proposal acceptance: {e}")
            
        await callback.answer("✅ تم قبول واعتماد السؤال بنجاح وتم إخطار الطالب.", show_alert=True)
    else:
        await callback.answer("⚠️ حدث خطأ أثناء قبول الاقتراح.", show_alert=True)
        
    await admin_view_proposals(callback, state)


@router.callback_query(F.data.startswith("admin_prop_rej:"))
async def admin_proposal_reject_prompt(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        return
        
    proposal_id = int(callback.data.split(":")[1])
    await state.set_state(AdminStates.waiting_for_proposal_rejection_reason)
    await state.update_data(rej_proposal_id=proposal_id, admin_msg_id=callback.message.message_id)
    
    text = (
        f"❌ <b>رفض الاقتراح #{proposal_id}</b>\n\n"
        "يرجى كتابة سبب الرفض بالتفصيل لإرساله في رسالة إخطار للطالب (مثال: السؤال مكرر، أو الخيارات غير دقيقة):\n\n"
        "<i>سيتم إرسال هذا السبب للطالب وتغيير حالة الاقتراح إلى مرفوض.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ إلغاء والعودة للتفاصيل", callback_data=f"admin_prop_det:{proposal_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.waiting_for_proposal_rejection_reason)
async def admin_proposal_reject_reason(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
        
    reason = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
        
    if not reason:
        return
        
    data = await state.get_data()
    proposal_id = data.get("rej_proposal_id")
    
    prop = await db.get_proposal_by_id(proposal_id)
    if not prop:
        await message.answer("⚠️ لم يتم العثور على الاقتراح.")
        await state.clear()
        return
        
    success = await db.reject_proposal(proposal_id, reason)
    if success:
        student_id = prop["user_id"]
        SUBJECT_LABELS_LOCAL = {
            "fiqh": "الفقه",
            "sira": "السيرة النبوية",
            "nahw": "النحو",
            "aqeeda": "العقيدة"
        }
        sub_lbl = SUBJECT_LABELS_LOCAL.get(prop["subject"].lower(), prop["subject"])
        
        student_notify_text = (
            "⚠️ <b>بخصوص سؤالك المقترح:</b>\n\n"
            f"نشكر لك مبادرتك الطيبة في اقتراح سؤال لمادة <b>{sub_lbl}</b> (الدرس {prop['course_number']}).\n"
            "نعتذر منك، لم تتمكن الإدارة من اعتماد هذا السؤال للسبب التالي:\n\n"
            f"📝 <b>سبب الإدارة:</b> {reason}\n\n"
            "نسعد جداً بمشاركاتك واقتراحاتك القادمة! وجزاك الله خيراً."
        )
        try:
            await message.bot.send_message(chat_id=student_id, text=student_notify_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Could not notify student {student_id} of proposal rejection: {e}")
            
        await message.bot.send_message(
            chat_id=user_id,
            text=f"✅ تم رفض الاقتراح #{proposal_id} بنجاح وإرسال السبب للطالب."
        )
    else:
        await message.bot.send_message(chat_id=user_id, text="⚠️ حدث خطأ أثناء رفض الاقتراح.")
        
    await state.clear()
    
    proposals = await db.get_pending_proposals()
    text = (
        "📥 <b>إدارة مقترحات الأسئلة المقدمة من الطلاب</b>\n\n"
        f"عدد المقترحات المعلقة: <b>{len(proposals)} اقتراح</b>\n\n"
        "اختر أحد المقترحات أدناه لمراجعته واعتماده أو رفضه:"
    )
    rows = []
    for p in proposals:
        sub_lbl = SUBJECT_LABELS_LOCAL.get(p["subject"].lower(), p["subject"])
        q_preview = p["question"][:25] + "..." if len(p["question"]) > 25 else p["question"]
        btn_text = f"📚 {sub_lbl} (د {p['course_number']}): {q_preview}"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_prop_det:{p['id']}")])
        
    rows.append([InlineKeyboardButton(text="↩️ العودة للوحة الإدارة", callback_data="admin_back_panel")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await message.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode="HTML")


async def recategorize_course_questions_under_new_axes(subject: str, lesson_num: int, axes_titles: list[str]):
    """
    Recategorize all questions in general bank for this course under the newly generated axes titles.
    """
    import google.generativeai as genai
    from config import GEMINI_API_KEY
    import json
    import re
    
    if not GEMINI_API_KEY or not axes_titles:
        return
        
    # Fetch all questions for this subject and course
    # (both official and generated_by_gemini)
    async with db.aiosqlite.connect(db.DATABASE_PATH) as conn:
        conn.row_factory = db.aiosqlite.Row
        async with conn.execute(
            "SELECT id, question FROM questions WHERE subject = ? AND course_number = ?",
            (subject, lesson_num)
        ) as cursor:
            rows = await cursor.fetchall()
            questions = [dict(r) for r in rows]
            
    if not questions:
        return
        
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # Prepare the prompt
        axes_list_str = "\n".join([f"- {title}" for title in axes_titles])
        questions_list_str = "\n".join([f"ID {q['id']}: {q['question']}" for q in questions])
        
        system_instruction = (
            "You are an expert pedagogical assistant. Your task is to classify a list of Arabic questions into one of the newly defined course axes/themes.\n\n"
            "Here are the newly defined axes/themes:\n"
            f"{axes_list_str}\n\n"
            "Return a valid JSON object where the keys are the question IDs (as strings) and the values are the EXACT theme/axis title chosen from the list above.\n"
            "If a question does not fit perfectly, choose the closest logical axis title from the list. Do not create new titles.\n"
            "Return raw JSON text only."
        )
        
        prompt = f"System Instructions: {system_instruction}\n\nQuestions to classify:\n{questions_list_str}"
        
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        response_text = response.text.strip()
        
        match = re.search(r'\{\s*".*"\s*:\s*".*"\s*\}', response_text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = response_text
            
        mapping = json.loads(json_str)
        if isinstance(mapping, dict):
            async with db.aiosqlite.connect(db.DATABASE_PATH) as conn:
                for q_id, theme_title in mapping.items():
                    if theme_title in axes_titles:
                        await conn.execute(
                            "UPDATE questions SET theme = ? WHERE id = ?",
                            (theme_title.strip(), int(q_id))
                        )
                await conn.commit()
    except Exception as e:
        logger.error(f"Error in automatic recategorization of questions: {e}", exc_info=True)






