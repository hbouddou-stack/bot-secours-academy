import logging
import os
import re
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
import keyboards as kb
from config import TELEGRAM_SUPPORT_GROUP_ID

def format_date_to_long_arabic(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        date_str_clean = date_str.replace('T', ' ').split('.')[0]
        dt = datetime.strptime(date_str_clean, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            dt = datetime.fromisoformat(date_str)
        except Exception:
            return date_str
            
    arabic_days = {
        0: "الإثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد"
    }
    
    arabic_months = {
        1: "يناير",
        2: "فبراير",
        3: "مارس",
        4: "أبريل",
        5: "مايو",
        6: "يونيو",
        7: "يوليو",
        8: "أغسطس",
        9: "سبتمبر",
        10: "أكتوبر",
        11: "نوفمبر",
        12: "ديسمبر"
    }
    
    day_name = arabic_days.get(dt.weekday(), "")
    month_name = arabic_months.get(dt.month, "")
    return f"{day_name} {dt.day} {month_name} {dt.year} الساعة {dt.strftime('%H:%M')}"

def map_correct_answer_to_arabic(answer: str) -> str:
    if not answer:
        return ""
    val = str(answer).strip().upper()
    mapping = {
        "1": "أ",
        "2": "ب",
        "3": "ج",
        "4": "د",
        "A": "أ",
        "B": "ب",
        "C": "ج",
        "D": "د"
    }
    return mapping.get(val, val)

logger = logging.getLogger(__name__)
router = Router(name="support")

SUBJECT_MAP = {
    "fiqh": "الفقه",
    "sira": "السيرة النبوية",
    "nahw": "النحو",
    "aqeeda": "العقيدة",
    "tajweed": "علم التجويد"
}

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

GUIDE_TEXT = (
    "📖 <b>دليل الاستخدام السريع للبوت:</b>\n\n"
    "• 📝 <b>تمرين جديد:</b> للبدء بتمرين جديد. يمكنك اختيار الأسئلة حسب الدروس أو حسب المحاور والمواضيع للتدرب على المادة بالكامل.\n"
    "• ▶️ <b>مواصلة التمرين:</b> لمواصلة مسارك التعليمي. يختبرك البوت فقط في الأسئلة التي لم تجب عليها أو التي أخطأت فيها سابقاً لتصل لنسبة إتقان 100%.\n"
    "• ⭐ <b>المفضلة:</b> لمراجعة وتصفح الأسئلة التي قمت بحفظها كمفضلة أثناء التمارين.\n"
    "• ❌ <b>أخطائي:</b> مراجعة وحل جميع الأسئلة التي أخطأت فيها سابقاً. عند حلها بشكل صحيح، تُحذف تلقائياً من قائمة الأخطاء.\n"
    "• 📊 <b>تقدّمي:</b> للاطلاع على لوحة إنجازاتك ونسب الإتقان الخاصة بك لكل مادة ولكل درس بالتفصيل.\n"
    "• 📞 <b>الدعم:</b> للتواصل المباشر مع مشرفي الأكاديمية للإجابة عن استفساراتك أو التبليغ عن الأخطاء."
)

ARABIC_CHARS = {"a": "أ", "b": "ب", "c": "ج", "d": "د"}

class SupportStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_tech_report = State()
    waiting_for_schooling_report = State()
    waiting_for_course_question = State()
    waiting_for_content_error = State()
    waiting_for_suggestion = State()
    waiting_for_review = State()
    browsing_questions = State()
    waiting_for_reply = State()
    waiting_for_triage_decision = State()


class ProposeQuestionStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_course_number = State()
    waiting_for_question_text = State()
    waiting_for_choice_a = State()
    waiting_for_choice_b = State()
    waiting_for_choice_c = State()
    waiting_for_choice_d = State()
    waiting_for_correct_answer = State()
    waiting_for_explanation = State()

async def show_browser_question(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    browser_ids = data.get("browser_ids", [])
    idx = data.get("browser_idx", 0)
    
    if not browser_ids or idx >= len(browser_ids):
        user_id = callback.from_user.id
        unread_count = await db.get_unread_reports_count(user_id)
        await callback.message.edit_text(
            "⚠️ لا توجد أسئلة متوفرة للتصفح حالياً.",
            reply_markup=kb.get_support_menu_keyboard(unread_count)
        )
        return
        
    q_id = browser_ids[idx]
    q = await db.get_question_by_id(q_id)
    if not q:
        # Question deleted or missing, remove from list and recurse
        browser_ids.pop(idx)
        await state.update_data(browser_ids=browser_ids)
        await show_browser_question(callback, state)
        return
        
    choices = {
        "a": q.get("choice_a"),
        "b": q.get("choice_b"),
        "c": q.get("choice_c"),
        "d": q.get("choice_d")
    }
    active_choices = {k: v for k, v in choices.items() if v and v.strip()}
    
    subject_ar = SUBJECT_MAP.get(q.get("subject", "").lower(), q.get("subject"))
    text = (
        f"📝 <b>تصفح الأسئلة | السؤال {idx + 1} من {len(browser_ids)}</b>\n"
        f"• المادة: {subject_ar} | الدرس: {q.get('course_number')}\n"
        f"• معرف السؤال: <code>{q_id}</code>\n\n"
        f"<b>{(q.get('question') or '').strip()}</b>\n\n"
    )
    
    for k, v in active_choices.items():
        text += f"<blockquote><b>{ARABIC_CHARS[k]})</b> {v.strip()}</blockquote>\n"
        
    has_prev = idx > 0
    has_next = idx < len(browser_ids) - 1
    
    from handlers.start import is_admin
    reply_markup = kb.get_question_browser_nav_keyboard(q_id, has_prev, has_next, is_admin=is_admin(callback.from_user.id))
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def detect_and_update_student_year(bot, user_id: int) -> int | None:
    groups = await db.get_all_telegram_groups()
    if not groups:
        return None
        
    highest_year = None
    for group in groups:
        chat_id = group['chat_id']
        year = group['academic_year']
        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user_id)
            if member.status in ['member', 'creator', 'administrator', 'restricted']:
                if highest_year is None or year > highest_year:
                    highest_year = year
        except Exception:
            pass
            
    if highest_year:
        await db.update_user_academic_year(user_id, highest_year)
        logger.info(f"Student {user_id} automatically detected in Year {highest_year}")
        
    return highest_year

@router.message(F.new_chat_title)
async def handle_new_chat_title(message: Message):
    chat_id = str(message.chat.id)
    new_title = message.new_chat_title
    logger.info(f"Group {chat_id} renamed to {new_title}")
    
    year = None
    title_lower = new_title.lower()
    if any(x in title_lower for x in ["1ère", "1ere", "première", "premiere", "annee 1", "année 1", "year 1", "y1", "1/4", "1-4"]):
        year = 1
    elif any(x in title_lower for x in ["2ème", "2eme", "deuxième", "deuxieme", "annee 2", "année 2", "year 2", "y2", "2/4", "2-4"]):
        year = 2
    elif any(x in title_lower for x in ["3ème", "3eme", "troisième", "troisieme", "annee 3", "année 3", "year 3", "y3", "3/4", "3-4"]):
        year = 3
    elif any(x in title_lower for x in ["4ème", "4eme", "quatrième", "quatrieme", "annee 4", "année 4", "year 4", "y4", "4/4", "4-4"]):
        year = 4
        
    if year:
        await db.register_telegram_group(chat_id, year, new_title)
        logger.info(f"Automatically registered persistent group {chat_id} for academic year {year}")

@router.message(Command("register_group"))
async def cmd_register_group(message: Message):
    user_id = message.from_user.id
    user_admin = await db.get_user(user_id)
    is_admin = False
    if user_admin and user_admin.get("admin_role"):
        is_admin = True
    else:
        import aiosqlite
        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            async with conn.execute("SELECT role FROM admins WHERE telegram_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    is_admin = True
                    
    if not is_admin:
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("⚠️ Utilisation : `/register_group <1-4>` dans le groupe concerné.")
        return
        
    try:
        year = int(parts[1])
        if year not in [1, 2, 3, 4]:
            raise ValueError()
    except ValueError:
        await message.reply("⚠️ L'année doit être un entier entre 1 et 4.")
        return
        
    chat_id = str(message.chat.id)
    group_title = message.chat.title or "Groupe Inconnu"
    await db.register_telegram_group(chat_id, year, group_title)
    await message.reply(f"✅ Groupe enregistré : `{group_title}` (ID: `{chat_id}`) est maintenant officiellement associé à l'**Année {year}**.")

@router.callback_query(F.data.startswith("set_gender_"))
async def handle_set_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[2] # 'homme' or 'femme'
    user_id = callback.from_user.id
    
    await db.update_user_gender(user_id, gender)
    await callback.answer("✅ تم حفظ الاختيار بنجاح.", show_alert=False)
    
    # Run the dynamic year detection
    await detect_and_update_student_year(callback.bot, user_id)
    
    # Redirect to support main menu
    await cmd_support(callback, state)

@router.message(F.text == "📞 الدعم")
async def cmd_support(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    
    user_id = event.from_user.id
    
    # Check gender first
    user = await db.get_user(user_id)
    if not user or not user.get('gender') or user.get('gender') == 'indetermine':
        text = (
            "🙋‍♂️ <b>مرحباً بك في مركز الدعم الأكاديمي!</b>\n\n"
            "يرجى تحديد جنسك لتوجيه استفساراتك بشكل صحيح ومناسب شرعاً:\n\n"
            "<i>(هذا الاختيار يتم لمرة واحدة فقط)</i>"
        )
        gender_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 أنا طالب (ذكر)", callback_data="set_gender_homme"),
                InlineKeyboardButton(text="👩 أنا طالبة (أنثى)", callback_data="set_gender_femme")
            ]
        ])
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=gender_kb, parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=gender_kb, parse_mode="HTML")
        return

    # Trigger silent student year detection
    bot = event.bot if hasattr(event, 'bot') else None
    if bot:
        await detect_and_update_student_year(bot, user_id)
        
    unread_count = await db.get_unread_reports_count(user_id)

    
    # Check if the support group ID is configured
    if not TELEGRAM_SUPPORT_GROUP_ID:
        text = (
            "⚠️ خدمة الدعم الفني غير متوفرة حالياً.\n"
            "يرجى مراجعة إدارة الأكاديمية أو المحاولة لاحقاً."
        )
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text)
        else:
            await event.answer(text)
        return

    text = (
        "📞 <b>بوابة الدعم الفني والتواصل مع الإدارة:</b>\n\n"
        "أهلاً بك في مركز الدعم والمساهمة! يرجى اختيار القسم المطلوب من الخيارات أدناه:\n"
        "• 🚨 <b>أبلغ عن مشكلة:</b> للإبلاغ عن مشكلة تقنية أو خطأ علمي في الأسئلة.\n"
        "• 💡 <b>أشارك في التطوير:</b> لتقديم اقتراحات أو كتابة تقييم ورأي عام."
    )
    reply_markup = kb.get_support_menu_keyboard(unread_count)
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=reply_markup, parse_mode="HTML")

@router.callback_query(F.data == "support_report_menu")
@router.callback_query(F.data == "support_contribute_menu")
async def redirect_to_main_support(callback: CallbackQuery, state: FSMContext):
    await handle_support_guide_back(callback, state)

@router.callback_query(F.data == "support_tech")
async def handle_support_tech(callback: CallbackQuery, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await callback.answer("⚠️ خدمة الدعم الفني غير متوفرة حالياً.", show_alert=True)
        return
        
    await state.set_state(SupportStates.waiting_for_tech_report)
    await state.update_data(support_msg_id=callback.message.message_id)
    
    text = (
        "🛠️ <b>الإبلاغ عن مشكلة تقنية أو استفسار:</b>\n\n"
        "يرجى كتابة تفاصيل المشكلة التقنية التي تواجهها هنا وإرسالها في رسالة نصية.\n\n"
        "<i>سيتم تسجيل البلاغ وإرساله مباشرة للإدارة لمراجعته والرد عليه.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "support_schooling")
async def handle_support_schooling(callback: CallbackQuery, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await callback.answer("⚠️ خدمة الدعم الفني غير متوفرة حالياً.", show_alert=True)
        return
        
    await state.set_state(SupportStates.waiting_for_schooling_report)
    await state.update_data(support_msg_id=callback.message.message_id)
    
    text = (
        "🎓 <b>استفسار أكاديمي أو إداري:</b>\n\n"
        "يرجى كتابة استفسارك بخصوص الدراسة، الامتحانات، التسجيل أو أي أمور إدارية أخرى وإرسالها في رسالة نصية.\n\n"
        "<i>سيتم إرسال الاستفسار لإدارة الأكاديمية للإجابة عليه.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "support_course_question")
async def handle_support_course_question(callback: CallbackQuery, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await callback.answer("⚠️ خدمة الدعم غير متوفرة حالياً.", show_alert=True)
        return
        
    await state.update_data(support_msg_id=callback.message.message_id)
    
    text = (
        "❓ <b>سؤال في المقرر الدراسي:</b>\n\n"
        "يرجى تحديد المادة أو التخصص الخاص بسؤالك لتوجيهه للمشرف/التربوي المختص:\n\n"
        "<i>سيتم إرسال السؤال مباشرة للمشرف المسؤول عن المادة.</i>"
    )
    subject_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📖 اللغة العربية", callback_data="support_subj_arabe"),
            InlineKeyboardButton(text="🕌 التجويد والقراءات", callback_data="support_subj_tajwid")
        ],
        [
            InlineKeyboardButton(text="⚖️ الفقه وأصوله", callback_data="support_subj_fiqh"),
            InlineKeyboardButton(text="💭 العقيدة والتوحيد", callback_data="support_subj_aqeeda")
        ],
        [
            InlineKeyboardButton(text="📚 السيرة النبوية", callback_data="support_subj_sira"),
            InlineKeyboardButton(text="✏️ مادة أخرى", callback_data="support_subj_autre")
        ],
        [
            InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")
        ]
    ])
    await callback.message.edit_text(text, reply_markup=subject_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("support_subj_"))
async def handle_support_subject_selected(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split("_")[2] # 'arabe', 'tajwid', etc.
    await state.update_data(support_category=subject)
    await state.set_state(SupportStates.waiting_for_course_question)
    
    text = (
        "❓ <b>كتابة السؤال:</b>\n\n"
        "يرجى كتابة سؤالك العلمي أو الشرعي هنا بوضوح وإرساله في رسالة نصية.\n\n"
        "<i>ستقوم الإدارة والأشخاص المختصون بالإجابة عليه فور مراجعته.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ عودة", callback_data="support_course_question")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "support_content_error")
async def handle_support_content_error(callback: CallbackQuery, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await callback.answer("⚠️ خدمة الدعم غير متوفرة حالياً.", show_alert=True)
        return
        
    await state.set_state(SupportStates.waiting_for_content_error)
    await state.update_data(support_msg_id=callback.message.message_id)
    
    text = (
        "⚠️ <b>إبلاغ عن خطأ في المحتوى:</b>\n\n"
        "يرجى كتابة تفاصيل الخطأ (رقم السؤال، اسم الدرس، أو الملاحظة) في رسالة نصية وإرسالها.\n\n"
        "<i>سيقوم الفريق المختص بمطابقة البلاغ وتصحيح الخطأ.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "support_suggest")
async def handle_support_suggest(callback: CallbackQuery, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await callback.answer("⚠️ خدمة الدعم غير متوفرة حالياً.", show_alert=True)
        return
        
    await state.set_state(SupportStates.waiting_for_suggestion)
    await state.update_data(support_msg_id=callback.message.message_id)
    
    text = (
        "🚀 <b>تقديم اقتراح تحسين أو فكرة:</b>\n\n"
        "يسعدنا جداً سماع أفكارك لتطوير البوت والأكاديمية! يرجى كتابة اقتراحك هنا وإرساله في رسالة نصية."
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "support_review")
async def handle_support_review(callback: CallbackQuery, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await callback.answer("⚠️ خدمة الدعم غير متوفرة حالياً.", show_alert=True)
        return

    await state.set_state(SupportStates.waiting_for_review)
    await state.update_data(support_msg_id=callback.message.message_id)

    text = (
        "⭐ <b>إرسال تقييم أو رأي:</b>\n\n"
        "يسعدنا سماع رأيك حول تجربة استعمال البوت أو الأكاديمية. "
        "اكتب تقييمك أو ملاحظتك في رسالة نصية واحدة، ويمكنك إرفاق صورة أو ملف إذا كان ذلك مفيداً."
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()

async def process_ticket_creation(bot, user_id, username, first_name, r_type, notes, urgency, media_file_id, media_type, category=None):
    report_id = await db.add_question_report(
        user_id=user_id,
        username=username,
        first_name=first_name,
        q_id=0,
        r_type=r_type,
        notes=notes,
        urgency=urgency,
        media_file_id=media_file_id,
        media_type=media_type,
        category=category
    )
    await send_rich_support_ticket(bot, report_id)
    return report_id

async def handle_triage_submission(message: Message, state: FSMContext, text_content: str, r_type: str, urgency: str, media_file_id: str, media_type: str, msg_id: int):
    data = await state.get_data()
    category = data.get("support_category")
    
    if text_content and len(text_content.strip()) > 3:

        matches = await db.search_similar_triage(text_content)
        if matches:
            best_matches = matches[:2]
            await state.update_data(
                triage_text=text_content,
                triage_type=r_type,
                triage_urgency=urgency,
                triage_media_id=media_file_id,
                triage_media_type=media_type,
                triage_msg_id=msg_id
            )
            await state.set_state(SupportStates.waiting_for_triage_decision)
            
            match_texts = []
            for idx, m in enumerate(best_matches):
                match_texts.append(
                    f"❓ <b>سؤال مشابه:</b> {m['question']}\n"
                    f"💡 <b>الإجابة المقترحة:</b>\n"
                    f"<blockquote>{m['answer']}</blockquote>"
                )
            
            suggestions_block = "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n".join(match_texts)
            triage_prompt = (
                f"💡 <b>لقد وجدنا إجابات قد تفيدك في قاعدة البيانات:</b>\n\n"
                f"{suggestions_block}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>هل أجابت هذه المعلومات على استفسارك؟</b>"
            )
            triage_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ نعم، شكراً لك", callback_data="triage_resolve"),
                    InlineKeyboardButton(text="❌ لا، أود إرسال الطلب", callback_data="triage_submit")
                ]
            ])
            await message.bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=msg_id,
                text=triage_prompt,
                reply_markup=triage_kb,
                parse_mode="HTML"
            )
            return True
            
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    report_id = await process_ticket_creation(
        bot=message.bot,
        user_id=user_id,
        username=username,
        first_name=first_name,
        r_type=r_type,
        notes=text_content,
        urgency=urgency,
        media_file_id=media_file_id,
        media_type=media_type,
        category=category
    )
    return report_id

@router.callback_query(F.data == "triage_resolve")
async def handle_triage_resolve(callback: CallbackQuery, state: FSMContext):
    await callback.answer("تم حل الاستفسار، شكراً لك!")
    await state.clear()
    success_text = (
        "🌸 <b>الحمد لله الذي بنعمته تتم الصالحات!</b>\n\n"
        "يسعدنا جداً أن الإجابات المقترحة قد أجابت على استفسارك بنجاح. إذا كان لديك أي سؤال آخر، نحن دائماً في الخدمة."
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(success_text, reply_markup=back_kb, parse_mode="HTML")

@router.callback_query(F.data == "triage_submit")
async def handle_triage_submit(callback: CallbackQuery, state: FSMContext):
    await callback.answer("يتم إرسال بلاغك...")
    data = await state.get_data()
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    
    r_type = data.get("triage_type")
    notes = data.get("triage_text")
    urgency = data.get("triage_urgency", "Moyen")
    media_file_id = data.get("triage_media_id")
    media_type = data.get("triage_media_type")
    
    category = data.get("support_category")
    
    report_id = await process_ticket_creation(
        bot=callback.bot,
        user_id=user_id,
        username=username,
        first_name=first_name,
        r_type=r_type,
        notes=notes,
        urgency=urgency,
        media_file_id=media_file_id,
        media_type=media_type,
        category=category
    )
    await state.clear()
    
    type_success_labels = {
        "tech": "بلاغك التقني",
        "schooling": "استفسارك",
        "course_question": "سؤالك",
        "content_error": "بلاغك عن الخطأ",
        "suggestion": "اقتراحك"
    }
    label = type_success_labels.get(r_type, "طلبك")
    success_text = (
        f"✅ <b>تم إرسال {label} رقم #{report_id} بنجاح!</b>\n\n"
        f"يقوم فريق الدعم بمراجعته حالياً، وسنرد عليك قريباً عبر صندوق الرسائل الخاص بك."
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
    ])
    await callback.message.edit_text(success_text, reply_markup=back_kb, parse_mode="HTML")


@router.message(SupportStates.waiting_for_tech_report)
async def handle_tech_report_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("support_msg_id")
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
        
    text_content = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
        
    if not text_content and not media_file_id:
        return
        
    res = await handle_triage_submission(
        message=message,
        state=state,
        text_content=text_content,
        r_type="tech",
        urgency="Critique",
        media_file_id=media_file_id,
        media_type=media_type,
        msg_id=msg_id
    )
    
    if res is not True and res:
        await state.clear()
        success_text = (
            f"✅ <b>تم إرسال بلاغك التقني رقم #{res} بنجاح!</b>\n\n"
            f"يقوم فريق الدعم الفني بمراجعته حالياً، وسنرد عليك قريباً عبر صندوق الرسائل الخاص بك."
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
        ])
        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=msg_id,
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.message(SupportStates.waiting_for_schooling_report)
async def handle_schooling_report_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("support_msg_id")
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
        
    text_content = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
        
    if not text_content and not media_file_id:
        return
        
    res = await handle_triage_submission(
        message=message,
        state=state,
        text_content=text_content,
        r_type="schooling",
        urgency="Moyen",
        media_file_id=media_file_id,
        media_type=media_type,
        msg_id=msg_id
    )
    
    if res is not True and res:
        await state.clear()
        success_text = (
            f"✅ <b>تم إرسال استفسارك رقم #{res} بنجاح!</b>\n\n"
            f"تقوم إدارة الأكاديمية بمراجعته حالياً، وسنرد عليك قريباً عبر صندوق الرسائل الخاص بك."
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
        ])
        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=msg_id,
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.message(SupportStates.waiting_for_course_question)
async def handle_course_question_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("support_msg_id")
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
        
    text_content = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
        
    if not text_content and not media_file_id:
        return
        
    res = await handle_triage_submission(
        message=message,
        state=state,
        text_content=text_content,
        r_type="course_question",
        urgency="Moyen",
        media_file_id=media_file_id,
        media_type=media_type,
        msg_id=msg_id
    )
    
    if res is not True and res:
        await state.clear()
        success_text = (
            f"✅ <b>تم إرسال سؤالك رقم #{res} بنجاح!</b>\n\n"
            f"ستقوم الإدارة بالإجابة عليه فور مراجعته والرد عبر صندوق الرسائل الخاص بك."
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
        ])
        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=msg_id,
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.message(SupportStates.waiting_for_content_error)
async def handle_content_error_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("support_msg_id")
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
        
    text_content = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
        
    if not text_content and not media_file_id:
        return
        
    res = await handle_triage_submission(
        message=message,
        state=state,
        text_content=text_content,
        r_type="content_error",
        urgency="Moyen",
        media_file_id=media_file_id,
        media_type=media_type,
        msg_id=msg_id
    )
    
    if res is not True and res:
        await state.clear()
        success_text = (
            f"✅ <b>تم تسجيل بلاغك عن الخطأ رقم #{res} بنجاح!</b>\n\n"
            f"سيقوم الفريق بمراجعته وتحديث المحتوى في أقرب وقت."
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
        ])
        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=msg_id,
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.message(SupportStates.waiting_for_suggestion)
async def handle_suggestion_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("support_msg_id")
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
        
    text_content = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass
        
    if not text_content and not media_file_id:
        return
        
    res = await handle_triage_submission(
        message=message,
        state=state,
        text_content=text_content,
        r_type="suggestion",
        urgency="Faible",
        media_file_id=media_file_id,
        media_type=media_type,
        msg_id=msg_id
    )
    
    if res is not True and res:
        await state.clear()
        success_text = (
            f"✅ <b>تم تسجيل اقتراحك رقم #{res} بنجاح!</b>\n\n"
            f"نشكرك على مساهمتك القيمة لتطوير الأكاديمية!"
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
        ])
        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=msg_id,
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.message(SupportStates.waiting_for_review)
async def handle_review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data.get("support_msg_id")
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

    text_content = (message.text or message.caption or "").strip()
    try:
        await message.delete()
    except Exception:
        pass

    if not text_content and not media_file_id:
        return

    res = await handle_triage_submission(
        message=message,
        state=state,
        text_content=text_content,
        r_type="review",
        urgency="Faible",
        media_file_id=media_file_id,
        media_type=media_type,
        msg_id=msg_id
    )

    if res is not True and res:
        await state.clear()
        success_text = (
            f"✅ <b>تم تسجيل رأيك رقم #{res} بنجاح!</b>\n\n"
            f"شكراً لك، ملاحظتك تساعدنا على تحسين التجربة."
        )
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ العودة للدعم", callback_data="support_guide_back")]
        ])
        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=msg_id,
            text=success_text,
            reply_markup=back_kb,
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("student_inbox"))
async def handle_student_inbox(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    parts = callback.data.split(":")
    
    show_archive = False
    page = 1
    if len(parts) > 1:
        if parts[1] == "archive":
            show_archive = True
            page = int(parts[2]) if len(parts) > 2 else 1
        elif parts[1] == "active":
            show_archive = False
            page = int(parts[2]) if len(parts) > 2 else 1
        else:
            if parts[1].isdigit():
                page = int(parts[1])
                
    user_id = callback.from_user.id
    reports = await db.get_user_reports(user_id)
    
    if not reports:
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ عودة للدعم", callback_data="support_guide_back")]
        ])
        await callback.message.edit_text(
            "📬 <b>صندوق الرسائل الخاص بك:</b>\n\n"
            "ليس لديك أي بلاغات أو اقتراحات مسجلة حالياً.",
            reply_markup=back_kb,
            parse_mode="HTML"
        )
        return
        
    if show_archive:
        text = (
            "📁 <b>أرشيف الرسائل المغلقة والمحلولة:</b>\n\n"
            "اضغط على أي بلاغ لمراجعة التفاصيل وردود الإدارة السابقة:"
        )
    else:
        text = (
            "📬 <b>صندوق الرسائل والطلبات النشطة:</b>\n\n"
            "اضغط على أي بلاغ لمراجعة التفاصيل وردود الإدارة:"
        )
        
    layout = await db.get_user_inbox_layout(user_id)
    reply_markup = kb.get_student_inbox_keyboard(reports, page=page, show_archive=show_archive, layout=layout)
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("st_rep_view:"))
async def handle_student_report_view(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    report_id = int(parts[1])
    
    if len(parts) > 3:
        return_page = f"{parts[2]}:{parts[3]}"
    elif len(parts) > 2:
        return_page = parts[2]
    else:
        return_page = "1"
    
    await db.mark_report_as_read(report_id)
    report = await db.get_question_report_by_id(report_id)
    
    if not report:
        await callback.message.edit_text(
            "⚠️ هذا البلاغ لم يعد موجوداً.",
            reply_markup=kb.get_student_report_detail_keyboard(report_id, can_reply=False, return_page=return_page)
        )
        return
        
    status_icons = {
        "pending": "⏳ غير معالجة",
        "in_progress": "🟡 قيد المعالجة",
        "resolved": "🟢 تم الحل / معالجته",
        "rejected": "❌ تم الرفض"
    }
    type_labels = {
        "tech": "🛠️ مشكلة تقنية",
        "suggestion": "🚀 اقتراح تحسين",
        "improvement": "🚀 اقتراح تحسين",
        "review": "⭐ تقييم / رأي",
        "question_error": "📚 خطأ في سؤال",
        "content": "📚 خطأ في سؤال",
        "أخرى / سبب آخر": "أخرى",
        "خطأ في الإجابة الصحيحة": "إجابة",
        "خطأ في نص السؤال": "نص",
        "خطأ في أحد الخيارات": "خيارات",
        "سبب آخر / مشكلة أخرى": "أخرى"
    }
    
    status_str = status_icons.get(report.get("status"), report.get("status"))
    raw_type = report.get("report_type")
    type_str = type_labels.get(raw_type, raw_type if raw_type else "بلاغ")
    
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
        notes_display += f"📝 <b>ملاحظاتك:</b>\n<blockquote>{comment_extracted}</blockquote>"
    else:
        notes_display += "📝 <b>ملاحظاتك:</b> <i>(لا توجد تفاصيل إضافية)</i>"
        
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>تفاصيل البلاغ رقم #{report['id']}</b>\n"
        f"📂 <b>القسم:</b> {type_str}\n"
        f"⚖️ <b>الحالة:</b> {status_str}\n"
        f"📅 <b>التاريخ:</b> {format_date_to_long_arabic(report.get('created_at', ''))}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{notes_display}\n\n"
    )
    
    if report.get("question_id"):
        text += (
            f"❓ <b>السؤال المرتبط:</b>\n"
            f"<blockquote>{(report.get('question') or '').strip()}</blockquote>\n\n"
        )
        
    if report.get("admin_reply"):
        text += (
            f"💬 <b>رد الإدارة والمشرفين:</b>\n"
            f"<blockquote><b>{report.get('admin_reply')}</b></blockquote>\n"
        )
    else:
        text += "💬 <b>رد الإدارة:</b> <i>لم يتم الرد بعد. سيصلك إشعار فور مراجعته.</i>\n"
        
    text += "\n━━━━━━━━━━━━━━━━━━━━━━"
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_student_report_detail_keyboard(report_id, can_reply=True, return_page=return_page),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("student_rep_reply:"))
async def handle_student_reply_init(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    report_id = int(callback.data.split(":")[1])
    
    await state.set_state(SupportStates.waiting_for_reply)
    await state.update_data(reply_report_id=report_id, reply_msg_id=callback.message.message_id)
    
    text = (
        f"✏️ <b>إضافة رد / تعليق إضافي للبلاغ رقم #{report_id}:</b>\n\n"
        "يرجى كتابة ردك هنا وإرساله في رسالة نصية.\n\n"
        "<i>سيتم إرسال ردك فوراً للمشرفين وإعادة فتح البلاغ لمراجعته.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء والتراجع", callback_data=f"st_rep_view:{report_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")

@router.message(SupportStates.waiting_for_reply)
async def handle_student_reply_submit(message: Message, state: FSMContext):
    data = await state.get_data()
    report_id = data.get("reply_report_id")
    msg_id = data.get("reply_msg_id")
    reply_content = message.text.strip() if message.text else ""
    
    try:
        await message.delete()
    except Exception:
        pass
        
    if not reply_content:
        return
        
    report = await db.get_question_report_by_id(report_id)
    if not report:
        await message.answer("⚠️ البلاغ غير موجود.")
        await state.clear()
        return
        
    old_notes = report.get("notes") or ""
    old_reply = report.get("admin_reply") or ""
    
    formatted_reply = f"💬 [رد الطالب]: {reply_content}"
    if old_reply:
        new_notes = f"{old_notes}\n\n🛡️ [رد الإدارة السابق]: {old_reply}\n\n{formatted_reply}"
    else:
        new_notes = f"{old_notes}\n\n{formatted_reply}"
        
    await db.reopen_question_report(report_id, new_notes)
    
    # Notify support group of reopened ticket
    await send_rich_support_ticket(message.bot, report_id)
    
    await state.clear()
    
    success_text = (
        f"✅ <b>تم إرسال تعليقك بنجاح للمشرفين!</b>\n\n"
        f"تمت إعادة فتح البلاغ رقم #{report_id} وسيقوم الفريق بمراجعته والرد عليك قريباً."
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ العودة للصندوق", callback_data="student_inbox")]
    ])
    await message.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=msg_id,
        text=success_text,
        reply_markup=back_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "support_report_question")
async def handle_support_report_question(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📝 <b>البحث عن سؤال للإبلاغ عن خطأ:</b>\n\n"
        "يرجى اختيار طريقة إيجاد السؤال الذي تود الإبلاغ عنه:\n"
        "• التصفح حسب أرقام الدروس (14 إلى 24).\n"
        "• التصفح حسب المواد الدراسية (الفقه، العقيدة...).",
        reply_markup=kb.get_browser_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "support_guide")
async def handle_support_guide(callback: CallbackQuery):
    await callback.message.edit_text(
        GUIDE_TEXT,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "support_guide_back")
async def handle_support_guide_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    unread_count = await db.get_unread_reports_count(user_id)
    
    await callback.message.edit_text(
        "📞 <b>بوابة الدعم الفني والتواصل مع الإدارة:</b>\n\n"
        "أهلاً بك! يرجى اختيار نوع الطلب من القائمة أدناه:\n"
        "• للإبلاغ عن مشكلة تقنية، اختر <b>مشكلة تقنية</b>.\n"
        "• للإبلاغ عن اقتراح أو فكرة تحسين، اختر <b>اقتراح تحسين</b>.\n"
        "• للإبلاغ عن خطأ علمي في أحد الأسئلة المنهجية، اختر <b>الإبلاغ عن خطأ في سؤال</b>.",
        reply_markup=kb.get_support_menu_keyboard(unread_count),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "support_cancel")
async def handle_support_cancel(callback: CallbackQuery, state: FSMContext):
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

@router.callback_query(F.data.startswith("brtype:"))
async def handle_browser_type(callback: CallbackQuery):
    brtype = callback.data.split(":")[1]
    if brtype == "lessons":
        await callback.message.edit_text(
            "📖 <b>اختر الدرس الذي تود تصفح أسئلته:</b>",
            reply_markup=kb.get_browser_lesson_keyboard()
        )
    elif brtype == "subjects":
        await callback.message.edit_text(
            "🗂️ <b>اختر المادة التي تود تصفح أسئلتها:</b>",
            reply_markup=kb.get_browser_subject_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data.startswith("br_les:"))
async def handle_browser_by_lesson(callback: CallbackQuery, state: FSMContext):
    lesson_num = int(callback.data.split(":")[1])
    await callback.answer("⏳ جاري تحميل الأسئلة...")
    
    questions = await db.get_questions_by_course(lesson_num)
    if not questions:
        await callback.message.answer(f"⚠️ لا توجد أسئلة متوفرة للدرس {lesson_num} حالياً.")
        return
        
    q_ids = [q["id"] for q in questions]
    await state.set_state(SupportStates.browsing_questions)
    await state.update_data(browser_ids=q_ids, browser_idx=0)
    await show_browser_question(callback, state)

@router.callback_query(F.data.startswith("br_sub:"))
async def handle_browser_by_subject(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":")[1]
    await callback.answer("⏳ جاري تحميل الأسئلة...")
    
    questions = await db.get_questions_by_subject(subject)
    if not questions:
        await callback.message.answer(f"⚠️ لا توجد أسئلة متوفرة لمادة {SUBJECT_MAP.get(subject, subject)} حالياً.")
        return
        
    q_ids = [q["id"] for q in questions]
    await state.set_state(SupportStates.browsing_questions)
    await state.update_data(browser_ids=q_ids, browser_idx=0)
    await show_browser_question(callback, state)

@router.callback_query(SupportStates.browsing_questions, F.data == "qb_next")
async def handle_qb_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("browser_idx", 0)
    browser_ids = data.get("browser_ids", [])
    if idx < len(browser_ids) - 1:
        await state.update_data(browser_idx=idx + 1)
        await show_browser_question(callback, state)
    await callback.answer()

@router.callback_query(SupportStates.browsing_questions, F.data == "qb_prev")
async def handle_qb_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = data.get("browser_idx", 0)
    if idx > 0:
        await state.update_data(browser_idx=idx - 1)
        await show_browser_question(callback, state)
    await callback.answer()

@router.callback_query(SupportStates.browsing_questions, F.data == "qb_close")
async def handle_qb_close(callback: CallbackQuery, state: FSMContext):
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

@router.message(SupportStates.waiting_for_message, F.text == "❌ إنهاء الدعم")
async def handle_exit_support(message: Message, state: FSMContext):
    await state.clear()
    
    user_id = message.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    
    await message.answer(
        "📥 تم إغلاق جلسة الدعم والعودة للقائمة الرئيسية.",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        "🎓 يمكنك الآن استخدام القائمة السريعة للبدء.",
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining)
    )

@router.message(SupportStates.waiting_for_message)
async def handle_student_support_message(message: Message, state: FSMContext):
    if not TELEGRAM_SUPPORT_GROUP_ID:
        await message.answer("⚠️ خدمة الدعم الفني غير متوفرة حالياً.")
        return
        
    try:
        support_group_id = int(TELEGRAM_SUPPORT_GROUP_ID)
        
        # 1. Forward original message
        sent_msg = await message.forward(chat_id=support_group_id)
        
        # 2. Register mapping for the forwarded message ID
        await db.register_support_ticket(sent_msg.message_id, message.from_user.id)
        
        # 3. Send info banner as reply in the support group to assist admins
        username_str = f"@{message.from_user.username}" if message.from_user.username else "لا يوجد"
        info_text = (
            f"👤 <b>رسالة دعم جديدة:</b>\n"
            f"• الاسم: {message.from_user.full_name}\n"
            f"• المعرف: {username_str}\n"
            f"• المعرف الرقمي: <code>{message.from_user.id}</code>"
        )
        info_msg = await message.bot.send_message(
            chat_id=support_group_id,
            text=info_text,
            reply_to_message_id=sent_msg.message_id,
            parse_mode="HTML"
        )
        
        # 4. Register info message ID as well to capture replies to it
        await db.register_support_ticket(info_msg.message_id, message.from_user.id)
        
        await message.answer("✅ تم إرسال رسالتك للدعم بنجاح. سنوافيك بالرد هنا قريباً.")
    except Exception as e:
        logger.error(f"Error forwarding support message: {e}", exc_info=True)
        await message.answer("⚠️ حدث خطأ أثناء إرسال رسالتك. يرجى المحاولة مجدداً.")

# --- Developer / Admin Utilities ---

@router.message(Command("get_group_id"))
async def cmd_get_group_id(message: Message):
    """Developer helper to fetch the Chat ID of any group or chat."""
    await message.answer(
        f"ℹ️ <b>معلومات الدردشة الحالية:</b>\n\n"
        f"• المعرف الرقمي (Chat ID): <code>{message.chat.id}</code>\n"
        f"• النوع: <b>{message.chat.type}</b>\n"
        f"• العنوان/الاسم: {message.chat.title or message.chat.full_name or 'لا يوجد'}",
        parse_mode="HTML"
    )


@router.message(Command("topicid"))
async def cmd_topic_id(message: Message):
    """Developer helper to fetch group and forum topic IDs directly from Telegram."""
    thread_id = getattr(message, "message_thread_id", None)
    await message.answer(
        "<b>Topic diagnostic</b>\n\n"
        f"chat_id = <code>{message.chat.id}</code>\n"
        f"message_thread_id = <code>{thread_id or 'None'}</code>\n"
        f"chat_type = <code>{message.chat.type}</code>\n"
        f"title = <code>{message.chat.title or message.chat.full_name or ''}</code>",
        parse_mode="HTML"
    )

# --- Admin Reply Handler & Helper ---

import re

def parse_minute_to_seconds(text: str) -> int:
    """Converts strings like '12:45', '12.45', '1:30', or plain digits '90' to seconds."""
    if not text:
        return 0
    text = text.strip()
    # Replace common separators with colon
    text = text.replace('.', ':').replace(',', ':').replace('-', ':')
    if ':' in text:
        parts = text.split(':')
        try:
            if len(parts) == 2:
                # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            pass
    # If it is just digits
    if text.isdigit():
        try:
            return int(text)
        except ValueError:
            pass
    return 0


def make_youtube_timestamp_url(base_url: str, seconds: int) -> str:
    """Appends time parameter (e.g. ?t=90s or &t=90s) to a YouTube URL."""
    if not base_url or seconds <= 0:
        return base_url
    base_url = base_url.strip()
    if "t=" in base_url:
        # Remove existing t parameter
        base_url = re.sub(r'[?&]t=[^&]+', '', base_url)
    
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}t={seconds}s"


def extract_timestamp_from_report(report: dict) -> tuple[str | None, str | None]:
    """
    Extracts the YouTube URL and timestamp display from a report dict.
    Returns (timestamp_url, timestamp_display).
    """
    explanation = report.get("explanation") or ""
    youtube_url = None
    yt_match = re.search(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s\)"\'><]+', explanation)
    if yt_match:
        youtube_url = yt_match.group(0).strip()
        
    notes = report.get("notes") or ""
    time_match = re.search(r'\[الدقيقة:\s*([^\]]+)\]', notes)
    if time_match:
        timestamp_display = time_match.group(1).strip()
        if youtube_url:
            seconds = parse_minute_to_seconds(timestamp_display)
            if seconds > 0:
                timestamp_url = make_youtube_timestamp_url(youtube_url, seconds)
                return timestamp_url, timestamp_display
    return None, None


def format_admin_group_ticket_text(report: dict, show_full: bool = False) -> str:
    """Formats the rich support ticket card text, hiding or showing question details depending on toggle."""
    report_id = report.get("id")
    report_type = report.get("report_type")
    
    type_labels = {
        "tech": "🛠️ مشكلة تقنية",
        "course_question": "❓ سؤال في المقرر",
        "content_error": "⚠️ خطأ في المحتوى",
        "suggestion": "💡 اقتراح أو غير ذلك",
        "improvement": "💡 اقتراح أو غير ذلك",
        "review": "⭐ تقييم / رأي",
        "question_error": "📚 خطأ في سؤال",
        "expl_error": "⚠️ خطأ في الشرح"
    }
    type_str = type_labels.get(report_type, report_type if report_type else "بلاغ")
    
    username = report.get("username") or ""
    username_display = f"@{username}" if username else "بدون معرف"
    first_name = report.get("first_name") or "طالب"
    
    urgency_raw = report.get("urgency", "Moyen")
    urgency_map = {
        "Critique": "🔴 عاجل جداً",
        "Moyen": "🟡 هام",
        "Faible": "🟢 عادي"
    }
    urgency_display = urgency_map.get(urgency_raw, "🟡 هام")
    
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
        notes_display += f"💬 <b>تعليق الطالب / التفاصيل:</b>\n<blockquote>{comment_extracted}</blockquote>"
    else:
        notes_display += "💬 <b>تعليق الطالب / التفاصيل:</b> <i>(بدون تعليق إضافي)</i>"

    ticket_text = (
        f"🚨 <b>بلاغ جديد: {type_str}</b>\n"
        f"• <b>رقم البلاغ:</b> #{report_id}\n"
        f"• <b>المُبلّغ:</b> {first_name} ({username_display})\n"
        f"• <b>الأولوية:</b> {urgency_display}\n"
        f"• <b>التاريخ:</b> {format_date_to_long_arabic(report.get('created_at', ''))}\n\n"
        f"{notes_display}\n"
    )
    
    q_id = report.get("question_id")
    if q_id and q_id > 0:
        subject_ar = SUBJECT_MAP.get(report.get("subject", "").lower(), report.get("subject"))
        ticket_text += (
            f"\n❓ <b>السؤال المرتبط (ID: #{q_id}):</b>\n"
            f"• <b>المادة:</b> {subject_ar} | <b>الدرس:</b> {report.get('course_number')}\n"
        )
        
        if not show_full:
            ticket_text += "💬 <i>(تفاصيل السؤال مخفية - اضغط على زر تفاصيل السؤال أدناه للعرض)</i>\n"
        else:
            ticket_text += f"<blockquote>{report.get('question', '').strip()}</blockquote>\n"
            
            # Show choices if they exist
            choices_text = []
            if report.get("choice_a"): choices_text.append(f"<b>أ)</b> {report['choice_a'].strip()}")
            if report.get("choice_b"): choices_text.append(f"<b>ب)</b> {report['choice_b'].strip()}")
            if report.get("choice_c"): choices_text.append(f"<b>ج)</b> {report['choice_c'].strip()}")
            if report.get("choice_d"): choices_text.append(f"<b>د)</b> {report['choice_d'].strip()}")
            
            if choices_text:
                ticket_text += "\n" + "\n".join(choices_text) + "\n"
                
            correct_ans_mapped = map_correct_answer_to_arabic(report.get('correct_answer'))
            ticket_text += f"\n🎯 <b>الإجابة الصحيحة:</b> {correct_ans_mapped}\n"
            
            if report.get("explanation"):
                ticket_text += f"\n📖 <b>شرح الشيخ المعتمد:</b>\n<blockquote>{report['explanation'].strip()}</blockquote>\n"
                
    ticket_text += "\n━━━━━━━━━━━━━━━━━━━━━━"
    return ticket_text


def support_topic_key_for_report(report: dict) -> str:
    report_type = (report.get("report_type") or "").strip().lower()
    category = (report.get("category") or "").strip().lower()
    question_id = report.get("question_id") or 0

    if report_type in {"expl_error", "explanation_error"}:
        return "expl_error"
    if question_id and question_id > 0:
        return "question_error"
    if report_type in {"content_error", "question_error"}:
        return "question_error"
    if report_type in {"tech", "technical"}:
        return "tech"
    if report_type in {"schooling", "registration", "payment", "exam", "administrative"}:
        return "academic"
    if report_type in {"course_question"}:
        return f"course_{category}" if category else "course_question"
    if report_type in {"suggestion", "improvement", "review"}:
        return "suggestion"
    return "general"


async def get_support_topic_thread_id(report: dict) -> int | None:
    topic_key = support_topic_key_for_report(report)
    candidates = [
        f"support_topic_{topic_key}",
        f"support_topic_{topic_key}_thread_id",
        "support_topic_general",
        "support_topic_general_thread_id",
    ]

    env_candidates = [
        f"SUPPORT_TOPIC_{topic_key.upper()}",
        f"SUPPORT_TOPIC_{topic_key.upper()}_THREAD_ID",
        "SUPPORT_TOPIC_GENERAL",
        "SUPPORT_TOPIC_GENERAL_THREAD_ID",
    ]

    for key in candidates:
        value = await db.get_setting(key, "")
        if value and str(value).strip().isdigit():
            return int(str(value).strip())

    for key in env_candidates:
        value = os.getenv(key, "").strip()
        if value.isdigit():
            return int(value)

    return None


async def send_rich_support_ticket(bot, report_id: int) -> None:
    """Formats and sends a self-contained rich support ticket card to the support group."""
    report = await db.get_question_report_by_id(report_id)
    if not report:
        logger.error(f"Report #{report_id} not found in database.")
        return
        
    q_id = report.get("question_id")
    has_question = q_id and q_id > 0
    
    detail_pref = await db.get_setting("ticket_detail_level", "compact")
    show_details_initially = (detail_pref == "full")
    
    ticket_text = format_admin_group_ticket_text(report, show_full=show_details_initially)
    timestamp_url, timestamp_display = extract_timestamp_from_report(report)
    
    user_id = report.get("user_id")
    thread_id = await get_support_topic_thread_id(report)
    
    if TELEGRAM_SUPPORT_GROUP_ID:
        try:
            support_group_id = int(TELEGRAM_SUPPORT_GROUP_ID)
            send_kwargs = {
                "chat_id": support_group_id,
                "text": ticket_text,
                "reply_markup": kb.get_admin_group_ticket_keyboard(
                    report_id,
                    has_question=has_question,
                    status=report.get("status", "pending"),
                    claimed_by=report.get("claimed_by") or "",
                    timestamp_url=timestamp_url,
                    timestamp_display=timestamp_display,
                    show_details=show_details_initially
                ),
                "parse_mode": "HTML",
                "link_preview_options": LinkPreviewOptions(is_disabled=True)
            }
            if thread_id:
                send_kwargs["message_thread_id"] = thread_id
            sent_msg = await bot.send_message(**send_kwargs)
            # Register in support_tickets table to map group replies to student ID
            await db.register_support_ticket(sent_msg.message_id, user_id)
        except Exception as e:
            logger.error(f"Error sending rich support ticket #{report_id} to group: {e}", exc_info=True)


def format_student_notification(report: dict, reply_text: str, status: str) -> str:
    status_labels = {
        "resolved": "🟢 تم الحل / معالجته (Résolu)",
        "rejected": "❌ تم الرفض (Rejeté)",
        "in_progress": "🟡 قيد المعالجة (Laisser en cours)"
    }
    status_str = status_labels.get(status, "⏳ قيد المراجعة")
    
    type_labels = {
        "tech": "🛠️ مشكلة تقنية",
        "course_question": "❓ سؤال في المقرر",
        "content_error": "⚠️ خطأ في المحتوى",
        "suggestion": "💡 اقتراح أو غير ذلك",
        "review": "⭐ تقييم / رأي",
        "question_error": "📚 خطأ في سؤال",
        "expl_error": "⚠️ خطأ في الشرح"
    }
    type_str = type_labels.get(report.get("report_type"), report.get("report_type") or "بلاغ")
    
    subject_labels = {
        "fiqh": "الفقه",
        "sira": "السيرة النبوية",
        "nahw": "النحو",
        "aqeeda": "العقيدة",
        "tajweed": "علم التجويد"
    }
    subject_ar = subject_labels.get(report.get("subject", "").lower(), report.get("subject") or "غير محدد")
    course_str = f"الدرس {report.get('course_number')}" if report.get('course_number') else "غير محدد"
    
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

    notes_snippet = comment_extracted or error_type_extracted or "لا توجد تفاصيل"
    if len(notes_snippet) > 100:
        notes_snippet = notes_snippet[:97] + "..."
        
    question_snippet = (report.get("question") or "").strip()
    if question_snippet:
        question_block = f"❓ <b>السؤال المرتبط:</b>\n<blockquote>{question_snippet}</blockquote>\n"
    else:
        question_block = ""
        
    notification_text = (
        f"📢 <b>رسالة من إدارة الأكاديمية</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>بخصوص بلاغك رقم #{report['id']}</b>\n"
        f"📂 <b>القسم:</b> {type_str}\n"
        f"📚 <b>المادة:</b> {subject_ar} | <b>الدرس:</b> {course_str}\n\n"
        f"{question_block}"
        f"📝 <b>ملاحظتك الأصلية:</b>\n"
        f"<blockquote>{notes_snippet}</blockquote>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 <b>رد الإدارة :</b>\n"
        f"<blockquote><b>{reply_text}</b></blockquote>\n\n"
        f"⚖️ <b>حالة البلاغ الحالية:</b> {status_str}"
    )

    return notification_text


@router.message(F.chat.type.in_({"group", "supergroup"}), F.reply_to_message)
async def handle_admin_reply(message: Message, state: FSMContext):
    """Intercept admin replies in the support group and prompt for status decision before copying back to student."""
    if not TELEGRAM_SUPPORT_GROUP_ID:
        return
        
    try:
        support_group_id = int(TELEGRAM_SUPPORT_GROUP_ID)
    except ValueError:
        return
        
    if message.chat.id != support_group_id:
        return
        
    replied_msg_id = message.reply_to_message.message_id
    student_id = await db.get_student_by_ticket(replied_msg_id)
    
    if not student_id:
        return
        
    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r'رقم البلاغ:\s*#(\d+)', replied_text)
    report_id = int(match.group(1)) if match else None
    
    if not report_id:
        return
        
    reply_content = message.text or "[ملف أو رسالة غير نصية]"
    
    try:
        # Save reply content in FSM state of the admin
        await state.update_data(
            group_reply_text=reply_content,
            group_reply_message_id=replied_msg_id,
            group_admin_reply_msg_id=message.message_id
        )
        
        # Ask admin to choose the ticket status
        await message.reply(
            f"✍️ <b>تم استلام ردك للبلاغ #{report_id}.</b>\n"
            f"يرجى تحديد حالة هذا البلاغ لإرسال الرد للطالب :",
            reply_markup=kb.get_admin_status_decision_keyboard(report_id, return_page="group"),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error handling admin reply in group: {e}", exc_info=True)


# ─── Student Question Proposal FSM ────────────────────────────────────────────

async def render_proposal_step(bot, chat_id: int, bot_msg_id: int, state_name: str, data: dict):
    if state_name == "waiting_for_subject":
        text = (
            "✍️ <b>اقتراح سؤال جديد للمقرر:</b>\n\n"
            "يرجى اختيار المادة الدراسية للمحافظة على تنظيم الأسئلة:"
        )
        rows = [
            [
                InlineKeyboardButton(text="📚 الفقه", callback_data="prop_sub:fiqh"),
                InlineKeyboardButton(text="🕌 السيرة النبوية", callback_data="prop_sub:sira")
            ],
            [
                InlineKeyboardButton(text="✍️ النحو", callback_data="prop_sub:nahw"),
                InlineKeyboardButton(text="💭 العقيدة", callback_data="prop_sub:aqeeda")
            ],
            [
                InlineKeyboardButton(text="↩️ عودة", callback_data="support_guide_back")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=rows)
    elif state_name == "waiting_for_course_number":
        subject_ar = SUBJECT_LABELS.get(data.get("subject"), data.get("subject"))
        text = (
            f"✍️ <b>اقتراح سؤال جديد - {subject_ar}</b>\n\n"
            "🔢 <b>تحديد رقم الدرس:</b>\n"
            "يرجى كتابة رقم الدرس (مثال: 3) وإرساله في رسالة نصية.\n\n"
            "<i>تأكد من كتابة الرقم فقط بشكل صحيح.</i>"
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:subject")]
        ])
    elif state_name == "waiting_for_question_text":
        text = (
            "❓ <b>نص السؤال المقترح:</b>\n\n"
            "يرجى كتابة نص السؤال المقترح بوضوح باللغة العربية.\n\n"
            "مثال: <i>ما هي أركان الصلاة؟</i>"
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:course_number")]
        ])
    elif state_name == "waiting_for_choice_a":
        text = (
            "🅰️ <b>الخيار الأول (أ):</b>\n\n"
            "يرجى إرسال نص الخيار الأول (أ) المقابل للإجابة."
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:question_text")]
        ])
    elif state_name == "waiting_for_choice_b":
        text = (
            "🅱️ <b>الخيار الثاني (ب):</b>\n\n"
            "يرجى إرسال نص الخيار الثاني (ب) المقابل للإجابة."
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:choice_a")]
        ])
    elif state_name == "waiting_for_choice_c":
        text = (
            "🆃 <b>الخيار الثالث (ج) [اختياري]:</b>\n\n"
            "يرجى إرسال نص الخيار الثالث (ج)، أو اضغط على الزر أدناه لتخطي هذا الخيار والاكتفاء بخيارين."
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ تخطي الخيار (ج)", callback_data="prop_skip:c")],
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:choice_b")]
        ])
    elif state_name == "waiting_for_choice_d":
        text = (
            "🆳 <b>الخيار الرابع (د) [اختياري]:</b>\n\n"
            "يرجى إرسال نص الخيار الرابع (د)، أو اضغط على الزر أدناه لتخطي هذا الخيار."
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ تخطي الخيار (د)", callback_data="prop_skip:d")],
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:choice_c")]
        ])
    elif state_name == "waiting_for_correct_answer":
        has_c = data.get("choice_c") is not None
        has_d = data.get("choice_d") is not None
        text = (
            "✅ <b>تحديد الإجابة الصحيحة:</b>\n\n"
            "اختر الخيار المقابل للإجابة الصحيحة للسؤال المقترح:\n\n"
            f"🅰️ <b>أ:</b> {data.get('choice_a')}\n"
            f"🅱️ <b>ب:</b> {data.get('choice_b')}\n"
        )
        if has_c:
            text += f"🆃 <b>ج:</b> {data.get('choice_c')}\n"
        if has_d:
            text += f"🆳 <b>د:</b> {data.get('choice_d')}\n"
            
        row = [
            InlineKeyboardButton(text="🅰️ أ", callback_data="prop_ans:a"),
            InlineKeyboardButton(text="🅱️ ب", callback_data="prop_ans:b")
        ]
        if has_c:
            row.append(InlineKeyboardButton(text="🆃 ج", callback_data="prop_ans:c"))
        if has_d:
            row.append(InlineKeyboardButton(text="🆳 د", callback_data="prop_ans:d"))
            
        back_step = "choice_d" if has_d else ("choice_c" if has_c else "choice_b")
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            row,
            [InlineKeyboardButton(text="↩️ عودة", callback_data=f"prop_back:{back_step}")]
        ])
    elif state_name == "waiting_for_explanation":
        text = (
            "💡 <b>شرح وتوضيح الإجابة [اختياري]:</b>\n\n"
            "أرسل تعليقاً أو شرحاً مبسطاً لسبب صحة هذا الخيار، أو اضغط على الزر أدناه لتخطي الشرح وإرسال الاقتراح فوراً."
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ تخطي الشرح وإرسال الاقتراح", callback_data="prop_skip:explanation")],
            [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:correct_answer")]
        ])
    else:
        return
        
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=bot_msg_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error editing message in proposal step {state_name}: {e}")

@router.callback_query(F.data == "support_propose_question")
async def start_propose_question(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProposeQuestionStates.waiting_for_subject)
    await state.update_data(support_msg_id=callback.message.message_id)
    await render_proposal_step(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        bot_msg_id=callback.message.message_id,
        state_name="waiting_for_subject",
        data={}
    )
    await callback.answer()

@router.callback_query(F.data.startswith("prop_sub:"))
async def handle_prop_subject(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":")[1]
    await state.update_data(subject=subject)
    await state.set_state(ProposeQuestionStates.waiting_for_course_number)
    data = await state.get_data()
    await render_proposal_step(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_course_number",
        data=data
    )
    await callback.answer()

@router.message(ProposeQuestionStates.waiting_for_course_number)
async def handle_prop_course_number(message: Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    data = await state.get_data()
    bot_msg_id = data.get("support_msg_id")
    try:
        course_num = int(text)
        if course_num <= 0:
            raise ValueError()
    except ValueError:
        subject_ar = SUBJECT_LABELS.get(data.get("subject"), data.get("subject"))
        err_text = (
            f"⚠️ <b>خطأ: يرجى إدخال رقم صحيح أكبر من الصفر.</b>\n\n"
            f"✍️ <b>اقتراح سؤال جديد - {subject_ar}</b>\n\n"
            "🔢 <b>تحديد رقم الدرس:</b>\n"
            "يرجى كتابة رقم الدرس (مثال: 3) وإرساله في رسالة نصية."
        )
        try:
            await message.bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=bot_msg_id,
                text=err_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="↩️ عودة", callback_data="prop_back:subject")]
                ]),
                parse_mode="HTML"
            )
        except Exception:
            pass
        return
    await state.update_data(course_number=course_num)
    await state.set_state(ProposeQuestionStates.waiting_for_question_text)
    updated_data = await state.get_data()
    await render_proposal_step(
        bot=message.bot,
        chat_id=message.from_user.id,
        bot_msg_id=bot_msg_id,
        state_name="waiting_for_question_text",
        data=updated_data
    )

@router.message(ProposeQuestionStates.waiting_for_question_text)
async def handle_prop_question_text(message: Message, state: FSMContext):
    text_content = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    if not text_content:
        return
    await state.update_data(question_text=text_content)
    await state.set_state(ProposeQuestionStates.waiting_for_choice_a)
    data = await state.get_data()
    await render_proposal_step(
        bot=message.bot,
        chat_id=message.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_choice_a",
        data=data
    )

@router.message(ProposeQuestionStates.waiting_for_choice_a)
async def handle_prop_choice_a(message: Message, state: FSMContext):
    text_content = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    if not text_content:
        return
    await state.update_data(choice_a=text_content)
    await state.set_state(ProposeQuestionStates.waiting_for_choice_b)
    data = await state.get_data()
    await render_proposal_step(
        bot=message.bot,
        chat_id=message.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_choice_b",
        data=data
    )

@router.message(ProposeQuestionStates.waiting_for_choice_b)
async def handle_prop_choice_b(message: Message, state: FSMContext):
    text_content = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    if not text_content:
        return
    await state.update_data(choice_b=text_content)
    await state.set_state(ProposeQuestionStates.waiting_for_choice_c)
    data = await state.get_data()
    await render_proposal_step(
        bot=message.bot,
        chat_id=message.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_choice_c",
        data=data
    )

@router.message(ProposeQuestionStates.waiting_for_choice_c)
async def handle_prop_choice_c(message: Message, state: FSMContext):
    text_content = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    if not text_content:
        return
    await state.update_data(choice_c=text_content)
    await state.set_state(ProposeQuestionStates.waiting_for_choice_d)
    data = await state.get_data()
    await render_proposal_step(
        bot=message.bot,
        chat_id=message.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_choice_d",
        data=data
    )

@router.message(ProposeQuestionStates.waiting_for_choice_d)
async def handle_prop_choice_d(message: Message, state: FSMContext):
    text_content = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    if not text_content:
        return
    await state.update_data(choice_d=text_content)
    await state.set_state(ProposeQuestionStates.waiting_for_correct_answer)
    data = await state.get_data()
    await render_proposal_step(
        bot=message.bot,
        chat_id=message.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_correct_answer",
        data=data
    )

@router.callback_query(F.data.startswith("prop_skip:"))
async def handle_prop_skips(callback: CallbackQuery, state: FSMContext):
    skip_target = callback.data.split(":")[1]
    data = await state.get_data()
    bot_msg_id = data.get("support_msg_id")
    if skip_target == "c":
        await state.update_data(choice_c=None, choice_d=None)
        await state.set_state(ProposeQuestionStates.waiting_for_correct_answer)
        updated_data = await state.get_data()
        await render_proposal_step(
            bot=callback.bot,
            chat_id=callback.from_user.id,
            bot_msg_id=bot_msg_id,
            state_name="waiting_for_correct_answer",
            data=updated_data
        )
    elif skip_target == "d":
        await state.update_data(choice_d=None)
        await state.set_state(ProposeQuestionStates.waiting_for_correct_answer)
        updated_data = await state.get_data()
        await render_proposal_step(
            bot=callback.bot,
            chat_id=callback.from_user.id,
            bot_msg_id=bot_msg_id,
            state_name="waiting_for_correct_answer",
            data=updated_data
        )
    elif skip_target == "explanation":
        await state.update_data(explanation=None)
        await commit_question_proposal(callback.bot, callback.from_user.id, state)
    await callback.answer()

async def commit_question_proposal(bot, user_id: int, state: FSMContext):
    data = await state.get_data()
    bot_msg_id = data.get("support_msg_id")
    try:
        chat = await bot.get_chat(user_id)
        username = chat.username
        first_name = chat.first_name
    except Exception:
        username = ""
        first_name = "طالب"
    proposal_id = await db.create_question_proposal(
        user_id=user_id,
        username=username,
        first_name=first_name,
        subject=data.get("subject"),
        course_number=data.get("course_number"),
        question=data.get("question_text"),
        choice_a=data.get("choice_a"),
        choice_b=data.get("choice_b"),
        choice_c=data.get("choice_c"),
        choice_d=data.get("choice_d"),
        correct_answer=data.get("correct_answer"),
        explanation=data.get("explanation")
    )
    if TELEGRAM_SUPPORT_GROUP_ID:
        subject_ar = SUBJECT_LABELS.get(data.get("subject"), data.get("subject"))
        choices_text = f"أ: {data.get('choice_a')}\nب: {data.get('choice_b')}"
        if data.get("choice_c"):
            choices_text += f"\nج: {data.get('choice_c')}"
        if data.get("choice_d"):
            choices_text += f"\nد: {data.get('choice_d')}"
        admin_text = (
            f"📥 <b>اقتراح سؤال جديد #{proposal_id}</b>\n\n"
            f"👤 <b>الطالب:</b> {first_name} (@{username if username else '-'})\n"
            f"📚 <b>المادة:</b> {subject_ar} (الدرس {data.get('course_number')})\n"
            f"❓ <b>السؤال:</b> {data.get('question_text')}\n\n"
            f"📋 <b>الخيارات:</b>\n{choices_text}\n\n"
            f"✅ <b>الإجابة الصحيحة:</b> {data.get('correct_answer').upper()}\n"
            f"💡 <b>التوضيح:</b> {data.get('explanation') or 'لا يوجد'}\n\n"
            f"<i>يمكنك مراجعة الاقتراح وقبوله أو رفضه من لوحة التحكم في البوت.</i>"
        )
        try:
            await bot.send_message(
                chat_id=int(TELEGRAM_SUPPORT_GROUP_ID),
                text=admin_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending proposal notification to admin group: {e}")
    await state.clear()
    success_text = (
        "✅ <b>تم تسجيل اقتراح السؤال بنجاح!</b>\n\n"
        "شكراً لمساهمتك القيمة في إثراء المحتوى التعليمي للأكاديمية. سيقوم المشرفون بمراجعته واعتماده قريباً."
    )
    kb_back = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ العودة لبوابة الدعم", callback_data="support_guide_back")]
    ])
    try:
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text=success_text,
            reply_markup=kb_back,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing success message: {e}")

@router.callback_query(F.data.startswith("prop_ans:"))
async def handle_prop_answer(callback: CallbackQuery, state: FSMContext):
    ans = callback.data.split(":")[1]
    await state.update_data(correct_answer=ans)
    await state.set_state(ProposeQuestionStates.waiting_for_explanation)
    data = await state.get_data()
    await render_proposal_step(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        bot_msg_id=data.get("support_msg_id"),
        state_name="waiting_for_explanation",
        data=data
    )
    await callback.answer()

@router.message(ProposeQuestionStates.waiting_for_explanation)
async def handle_prop_explanation(message: Message, state: FSMContext):
    text_content = message.text.strip() if message.text else ""
    try:
        await message.delete()
    except Exception:
        pass
    await state.update_data(explanation=text_content)
    await commit_question_proposal(message.bot, message.from_user.id, state)

@router.callback_query(F.data.startswith("prop_back:"))
async def handle_prop_back(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":")[1]
    data = await state.get_data()
    bot_msg_id = data.get("support_msg_id")
    if target == "subject":
        await state.set_state(ProposeQuestionStates.waiting_for_subject)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_subject", data)
    elif target == "course_number":
        await state.set_state(ProposeQuestionStates.waiting_for_course_number)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_course_number", data)
    elif target == "question_text":
        await state.set_state(ProposeQuestionStates.waiting_for_question_text)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_question_text", data)
    elif target == "choice_a":
        await state.set_state(ProposeQuestionStates.waiting_for_choice_a)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_choice_a", data)
    elif target == "choice_b":
        await state.set_state(ProposeQuestionStates.waiting_for_choice_b)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_choice_b", data)
    elif target == "choice_c":
        await state.set_state(ProposeQuestionStates.waiting_for_choice_c)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_choice_c", data)
    elif target == "choice_d":
        await state.set_state(ProposeQuestionStates.waiting_for_choice_d)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_choice_d", data)
    elif target == "correct_answer":
        await state.set_state(ProposeQuestionStates.waiting_for_correct_answer)
        await render_proposal_step(callback.bot, callback.from_user.id, bot_msg_id, "waiting_for_correct_answer", data)
    await callback.answer()
