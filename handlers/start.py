from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import database as db
import keyboards as kb
from config import TELEGRAM_ADMIN_IDS, ACADEMY_GROUP_ID
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

router = Router(name="start")

class RegistrationStates(StatesGroup):
    waiting_for_name_choice = State()
    waiting_for_custom_name = State()
    waiting_for_academic_year = State()
    waiting_for_preferred_subject = State()
    editing_preferred_subject = State()
    waiting_for_favorite_subjects = State()
    waiting_for_difficult_subjects = State()

def get_user_greeting(user: dict) -> str:
    gender = user.get("gender")
    pref_name = user.get("preferred_name")
    
    if pref_name:
        return f"يا {pref_name}"
    else:
        if gender == "f":
            return "يا طالبتنا"
        else:
            return "يا طالبنا"

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

async def is_academy_member(bot, user_id: int) -> bool:
    """Returns True if the user is currently a member of the academy Telegram group."""
    group_id_str = await db.get_setting("academy_group_id")
    try:
        group_id = int(group_id_str)
    except:
        from config import ACADEMY_GROUP_ID
        group_id = ACADEMY_GROUP_ID
        
    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except (TelegramBadRequest, TelegramForbiddenError):
        # Check test group if main fails
        test_group_id_str = await db.get_setting("test_group_id", "")
        if test_group_id_str:
            try:
                test_group_id = int(test_group_id_str)
                member = await bot.get_chat_member(chat_id=test_group_id, user_id=user_id)
                return member.status not in ("left", "kicked", "banned")
            except:
                pass
        # User not found in group or bot can't check → block access
        return False
    except Exception:
        # Network error etc. → allow access to avoid false lockouts
        return True

GUIDE_TEXT = (
    "📖 <b>دليل الاستخدام السريع للبوت:</b>\n\n"
    "• 📝 <b>البدء (اختبار جديد):</b> للبدء باختبار جديد. يمكنك اختيار الأسئلة حسب الدروس أو حسب المحاور والمواضيع للتدرب على المادة بالكامل.\n"
    "• 🔄 <b>الاستمرار (استئناف):</b> لمواصلة مسارك التعليمي. يختبرك البوت فقط في الأسئلة التي لم تجب عليها أو التي أخطأت فيها سابقاً لتصل لنسبة إتقان 100%.\n"
    "• ⭐ <b>المفضلة:</b> لمراجعة وتصفح الأسئلة التي قمت بحفظها كمفضلة أثناء خوض الاختبارات.\n"
    "• ❌ <b>أخطائي:</b> مراجعة وحل جميع الأسئلة التي أخطأت فيها سابقاً. عند حلها بشكل صحيح، تُحذف تلقائياً من قائمة الأخطاء.\n"
    "• 📊 <b>تقدّمي:</b> للاطلاع على لوحة إنجازاتك ونسب الإتقان الخاصة بك لكل مادة ولكل درس بالتفصيل.\n"
    "• 📬 <b>صندوق الرسائل:</b> لمراجعة ردود الإدارة على بلاغاتك واستفساراتك ومتابعة حالتها.\n"
    "• 📞 <b>الدعم:</b> للتواصل المباشر مع مشرفي الأكاديمية للإجابة عن استفساراتك أو التبليغ عن الأخطاء."
)

async def process_deep_link(message: Message, param: str, state: FSMContext):
    """Process a deep link parameter, store preselected lesson, and prompt for subject selection (no counts shown)."""
    lesson_num = None
    if param.startswith("course_"):
        parts = param.split("_")
        for p in parts:
            if p.isdigit():
                lesson_num = int(p)
                break

    await state.clear()
    
    from handlers.quiz import QuizStates
    if lesson_num and 14 <= lesson_num <= 24:
        # Set FSM state data
        await state.update_data(preselected_lesson=lesson_num)
        await state.set_state(QuizStates.selecting_subject)
        
        await message.answer(
            f"📥 تم تحديد <b>الدرس {lesson_num}</b> تلقائياً عبر الرابط.\n"
            "يرجى اختيار المادة الدراسية أولاً لإتمام الإعداد:",
            reply_markup=kb.get_subject_list_keyboard(None),
            parse_mode="HTML"
        )
    else:
        await state.set_state(QuizStates.selecting_subject)
        await message.answer(
            "📚 يرجى تحديد المادة الدراسية التي تود الاختبار فيها من القائمة أدناه:",
            reply_markup=kb.get_subject_list_keyboard(None),
            parse_mode="HTML"
        )

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Clear any previous FSM state
    await state.clear()

    # ── Group membership guard ──────────────────────────────────────────────
    user_id = message.from_user.id
    restrict_val = await db.get_setting("restrict_to_academy_group", "True") == "True"
    if restrict_val and not is_admin(user_id) and not await is_academy_member(message.bot, user_id):
        await message.answer(
            "⛔ عذراً، هذا البوت مخصص لطلاب أكاديمية الباجي فقط."
        )
        return
    # ───────────────────────────────────────────────────────────────────────

    # Check if there is a deep link parameter
    args = message.text.split(maxsplit=1)
    deep_link_param = args[1] if len(args) > 1 else None

    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        # Create user profile (gender will be NULL)
        await db.create_user(user_id, message.from_user.first_name, message.from_user.username)
        user = await db.get_user(user_id)

    if not user.get("gender"):
        # Save deep link param to state if present, so we can process it after gender selection
        if deep_link_param:
            await state.update_data(pending_deep_link=deep_link_param)
            
        custom_welcome = await db.get_setting("bot_welcome_message", "")
        welcome_prompt = custom_welcome if custom_welcome else (
            "مرحباً بك! <b>أنا كريم، مساعدك الشخصي للمراجعة</b> في أكاديمية الباجي. 🎓✨\n\n"
            "<blockquote>"
            "سأكون معك خطوة بخطوة لمساعدتك في تثبيت معلوماتك الشرعية ومراجعة دروسك بطريقة ميسرة وممتعة.\n\n"
            "أحيي فيك هذا الحرص على طلب العلم الشرعي! 🌟"
            "</blockquote>\n\n"
            "بما أنها المرة الأولى، أود أن نتعرف سريعًا لتكون تجربتك هنا مخصصة ومثالية لك:"
        )
        await message.answer(
            welcome_prompt,
            reply_markup=kb.get_start_onboarding_keyboard(),
            parse_mode="HTML"
        )
        return

    # User is registered, welcome back
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    
    greeting = get_user_greeting(user)
    pref_sub = await db.get_user_preferred_subject(user_id)
    if pref_sub:
        pref_sub_ar = kb.SUBJECT_LABELS.get(pref_sub, pref_sub)
        subject_block = f"<blockquote>🎯 <b>المادة النشطة:</b> <b>{pref_sub_ar}</b></blockquote>"
    else:
        subject_block = "<blockquote>🎯 <b>المادة النشطة:</b> <b>كافة المواد</b></blockquote>"
        
    welcome_text = (
        f"مرحباً بك مجدداً {greeting}! 🎓\n\n"
        f"{subject_block}\n\n"
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة التمارين والمسار التعليمي:"
    )
    if is_admin(user_id):
        import os
        admin_webapp = os.getenv("ADMIN_WEBAPP_URL") or "http://localhost:8082/admin"
        if not admin_webapp.startswith("https"):
            welcome_text += f"\n\n🖥️ <b>رابط لوحة التحكم للمشرف:</b>\n🔗 <a href='{admin_webapp}'>{admin_webapp}</a>"
    
    await message.answer(
        welcome_text,
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )

    if deep_link_param:
        await process_deep_link(message, deep_link_param, state)

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("gender"):
        await message.answer("يرجى بدء البوت أولاً بالضغط على /start")
        return
        
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    
    greeting = get_user_greeting(user)
    pref_sub = await db.get_user_preferred_subject(user_id)
    if pref_sub:
        pref_sub_ar = kb.SUBJECT_LABELS.get(pref_sub, pref_sub)
        subject_block = f"<blockquote>🎯 <b>المادة النشطة:</b> <b>{pref_sub_ar}</b></blockquote>"
    else:
        subject_block = "<blockquote>🎯 <b>المادة النشطة:</b> <b>كافة المواد</b></blockquote>"
        
    welcome_text = (
        f"مرحباً بك {greeting}! 🎓\n\n"
        f"{subject_block}\n\n"
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة التمارين والمسار التعليمي:"
    )
    if is_admin(user_id):
        import os
        admin_webapp = os.getenv("ADMIN_WEBAPP_URL") or "http://localhost:8082/admin"
        if not admin_webapp.startswith("https"):
            welcome_text += f"\n\n🖥️ <b>رابط لوحة التحكم للمشرف:</b>\n🔗 <a href='{admin_webapp}'>{admin_webapp}</a>"
    
    await message.answer(
        welcome_text,
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )

@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    await db.delete_user_data(user_id)
    
    await message.answer(
        "🔄 <b>تمت إعادة تعيين حسابك وتقدمك بالكامل بنجاح !</b>\n\n"
        "يرجى كتابة أو الضغط على /start للبدء من جديد وتجربة التسجيل كطالب جديد.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "start_onboarding")
async def handle_start_onboarding(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    welcome_prompt = "<blockquote>هل أنت أخ أم أخت؟ 👦👧</blockquote>"
    await callback.message.edit_text(
        welcome_prompt,
        reply_markup=kb.get_gender_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("register_gender:"))
async def handle_register_gender(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    gender_long = callback.data.split(":")[1]
    gender_short = "f" if gender_long == "female" else "m"
    
    user_id = callback.from_user.id
    await db.update_user_gender(user_id, gender_short)
    
    greeting = "يا أختي! 👧" if gender_short == "f" else "يا أخي! 👦"
    text = (
        f"مرحباً بك {greeting} ✨\n\n"
        "<blockquote>"
        "كيف تحب أن أناديك خلال رحلتنا التعليمية؟"
        "</blockquote>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_name_choice_keyboard(
            callback.from_user.first_name,
            callback.from_user.last_name,
            callback.from_user.username
        ),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("name_choice:"))
async def handle_name_choice(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    if choice == "custom":
        await state.set_state(RegistrationStates.waiting_for_custom_name)
        await state.update_data(welcome_msg_id=callback.message.message_id)
        await callback.message.edit_text(
            "<blockquote>✏️ الرجاء كتابة الاسم الذي ترغب فيه وإرساله في رسالة نصية.</blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_custom_name")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return
        
    preferred_name = None
    if choice == "first":
        preferred_name = callback.from_user.first_name
    elif choice == "full":
        preferred_name = f"{callback.from_user.first_name or ''} {callback.from_user.last_name or ''}".strip()
        
    await db.update_user_preferred_name(user_id, preferred_name)
    await callback.answer("✅ تم حفظ الاسم بنجاح.")
    await start_academic_year_selection(callback, state)

@router.callback_query(F.data == "cancel_custom_name")
async def handle_cancel_custom_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    gender_short = user.get("gender") if user else "m"
    greeting = "يا أختي! 👧" if gender_short == "f" else "يا أخي! 👦"
    
    text = (
        f"مرحباً بك {greeting} ✨\n\n"
        "<blockquote>"
        "كيف تحب أن أناديك خلال رحلتنا التعليمية؟"
        "</blockquote>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_name_choice_keyboard(
            callback.from_user.first_name,
            callback.from_user.last_name,
            callback.from_user.username
        ),
        parse_mode="HTML"
    )

@router.message(RegistrationStates.waiting_for_custom_name)
async def handle_custom_name_input(message: Message, state: FSMContext):
    custom_name = message.text.strip()
    if not custom_name:
        await message.answer("⚠️ الرجاء إدخال اسم صحيح:")
        return
        
    user_id = message.from_user.id
    await db.update_user_preferred_name(user_id, custom_name)
    
    data = await state.get_data()
    welcome_msg_id = data.get("welcome_msg_id")
    pending_deep_link = data.get("pending_deep_link")
    
    await state.clear()
    
    # Delete the user's custom name message to keep chat clean
    try:
        await message.delete()
    except Exception:
        pass
        
    if welcome_msg_id:
        class DummyMessage:
            def __init__(self, bot, chat_id, message_id, from_user):
                self.bot = bot
                self.chat = DummyChat(chat_id)
                self.message_id = message_id
                self.from_user = from_user
            async def edit_text(self, text, reply_markup=None, parse_mode=None):
                return await self.bot.edit_message_text(chat_id=self.chat.id, message_id=self.message_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        class DummyChat:
            def __init__(self, chat_id):
                self.id = chat_id
                
        dummy_msg = DummyMessage(message.bot, message.chat.id, welcome_msg_id, message.from_user)
        await start_academic_year_selection(dummy_msg, state)
    else:
        await start_academic_year_selection(message, state)
        
    if pending_deep_link:
        await process_deep_link(message, pending_deep_link, state)

async def get_guide_page_text(user: dict, page: int) -> str:
    if page == 1:
        pref_name = user.get("preferred_name") if user else None
        if pref_name:
            name_str = pref_name
        else:
            gender = user.get("gender") if user else "m"
            name_str = "طالبتنا" if gender == "f" else "طالبنا"
            
        return (
            "<blockquote>"
            f"مرحباً بك يا <b>{name_str}</b>! ✨\n\n"
            "قبل أن نبدأ، سآخذك في جولة تعريفية سريعة لتفهم كيفية عمل البوت وكيفية استخدامه بالشكل الأمثل. 🗺️✨"
            "</blockquote>\n\n"
            "<b>📖 دليل البداية | الاختبارات والتدريب (1/3)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<blockquote>"
            "• 📝 <b>اختبار شامل :</b>\n"
            "يختبرك في كامل المادة التي اخترتها، مع عرض مؤشر بصري بنقاط ملونة (pastilles) لتتبع تقدمك أثناء الحل."
            "</blockquote>\n"
            "<blockquote>"
            "• 🎯 <b>استكمال المذاكرة :</b>\n"
            "يتابع معك من حيث توقفت، ويركز فقط على الأسئلة المتبقية للوصول لإتقان 100%."
            "</blockquote>"
        )
    elif page == 2:
        return (
            "<b>📖 دليل البداية | المراجعة الذكية (2/3)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<blockquote>"
            "• ⭐ <b>المفضلة :</b>\n"
            "لحفظ الأسئلة المهمة للعودة إليها لاحقًا."
            "</blockquote>\n"
            "<blockquote>"
            "• ❌ <b>أخطائي :</b>\n"
            "يجمع تلقائيًا كل سؤال أخطأت فيه لكي تتمكن من إعادة حله وتصحيح معلوماتك."
            "</blockquote>"
        )
    elif page == 3:
        return (
            "<b>📖 دليل البداية | المتابعة والدعم (3/3)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<blockquote>"
            "• 📊 <b>تقدّمي :</b>\n"
            "لمشاهدة نسب تمكنك من الدروس بالألوان والنسب المئوية."
            "</blockquote>\n"
            "<blockquote>"
            "• 📬 <b>صندوق الرسائل :</b>\n"
            "لتلقي إشعارات الإدارة، والإجابات على استفساراتك الفنية أو العلمية."
            "</blockquote>\n"
            "<blockquote>"
            "• ⚙️ <b>الإعدادات :</b>\n"
            "لتخصيص تخطيط لوحة التمرين (كلاسيكي، شبكة، إلخ) وتغيير صيغة المخاطبة وتفضيلات عرض البريد."
            "</blockquote>\n"
            "<blockquote>"
            "• 📞 <b>الدعم :</b>\n"
            "للتواصل المباشر مع الإدارة لطرح أي سؤال أو تقديم استفسار في أي وقت."
            "</blockquote>\n\n"
            "<blockquote>"
            "أتمنى لك مراجعة ممتعة وموفقة! 🌸"
            "</blockquote>"
        )
    return ""

async def start_academic_year_selection(message_or_callback_msg, state: FSMContext):
    await state.set_state(RegistrationStates.waiting_for_academic_year)
    
    text = (
        "<blockquote>"
        "في أي سنة دراسية أنت حالياً في الأكاديمية؟"
        "</blockquote>\n"
        "<i>سيساعدنا هذا في تخصيص الإعلانات والأسئلة لك:</i>"
    )
    keyboard = kb.get_academic_year_keyboard()
    
    if isinstance(message_or_callback_msg, CallbackQuery):
        await message_or_callback_msg.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        if hasattr(message_or_callback_msg, "edit_text"):
            await message_or_callback_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message_or_callback_msg.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(RegistrationStates.waiting_for_academic_year, F.data.startswith("register_year:"))
async def handle_register_year(callback: CallbackQuery, state: FSMContext):
    year_str = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    if year_str != "skip":
        await db.update_user_academic_year(user_id, int(year_str))
        await callback.answer("✅ تم حفظ السنة الدراسية بنجاح.")
        await callback.answer("⏭️ تم تخطي تحديد السنة الدراسية.")
        
    await start_preferred_subject_selection(callback, state, is_editing=False)

async def start_preferred_subject_selection(message_or_callback_msg, state: FSMContext, is_editing: bool = False):
    if is_editing:
        await state.set_state(RegistrationStates.editing_preferred_subject)
    else:
        await state.set_state(RegistrationStates.waiting_for_preferred_subject)
    
    text = (
        "🎯 <b>تحديد المادة التلقائية:</b>\n\n"
        "<blockquote>"
        "هل ترغب في تحديد مادة تلقائية (افتراضية)؟\n"
        "إذا قمت بتحديدها، سيقوم البوت بنقلك <b>مباشرة</b> إلى قائمة دروس هذه المادة عند الضغط على أزرار التمارين أو المراجعة دون الحاجة لاختيار المادة في كل مرة."
        "</blockquote>\n"
        "<i>يمكنك تغيير هذا الاختيار أو تعطيله لاحقاً من الإعدادات:</i>"
    )
    
    user_id = message_or_callback_msg.from_user.id
    current_pref = await db.get_user_preferred_subject(user_id)
    keyboard = kb.get_preferred_subject_keyboard(current_pref)
    
    if isinstance(message_or_callback_msg, CallbackQuery):
        await message_or_callback_msg.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        if hasattr(message_or_callback_msg, "edit_text"):
            await message_or_callback_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message_or_callback_msg.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("pref_sub:select:"))
async def handle_pref_sub_selected(callback: CallbackQuery, state: FSMContext):
    sub = callback.data.split(":")[2]
    user_id = callback.from_user.id
    
    if sub == "none":
        await db.update_user_preferred_subject(user_id, None)
        await callback.answer("⏭️ تم تخطي تحديد المادة التلقائية.")
    else:
        await db.update_user_preferred_subject(user_id, sub)
        sub_ar = kb.SUBJECT_LABELS.get(sub, sub)
        await callback.answer(f"🎯 تم تحديد {sub_ar} كمادة تلقائية.")
        
    current_state = await state.get_state()
    if current_state == RegistrationStates.waiting_for_preferred_subject.state:
        await start_favorite_subjects_selection(callback, state)
    else:
        await handle_main_settings(callback, state)

@router.callback_query(F.data == "edit_preferred_subject")
async def handle_edit_preferred_subject(callback: CallbackQuery, state: FSMContext):
    await start_preferred_subject_selection(callback, state, is_editing=True)
    await callback.answer()

async def start_favorite_subjects_selection(message_or_callback_msg, state: FSMContext):
    await state.set_state(RegistrationStates.waiting_for_favorite_subjects)
    await state.update_data(selected_fav_subjects=[])
    
    user_id = message_or_callback_msg.from_user.id
    user = await db.get_user(user_id)
    pref_name = user.get("preferred_name") if user else None
    name_str = f" <b>{pref_name}</b>" if pref_name else ""
    
    text = (
        f"مرحباً بك يا{name_str}! ✨\n\n"
        "<blockquote>"
        "من أجل مساعدتك وتوجيهك بشكل أفضل في مسيرتك التعليمية، نود أن نعرف ما هي المواد التي تفضلها أو تشعر بارتياح أكبر في مذاكرتها؟"
        "</blockquote>\n"
        "<i>يمكنك اختيار أكثر من مادة من القائمة أدناه:</i>"
    )
    keyboard = kb.get_subjects_selection_keyboard([], "onb_fav")
    
    if isinstance(message_or_callback_msg, CallbackQuery):
        await message_or_callback_msg.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        if hasattr(message_or_callback_msg, "edit_text"):
            await message_or_callback_msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message_or_callback_msg.answer(text, reply_markup=keyboard, parse_mode="HTML")

async def start_difficult_subjects_selection(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RegistrationStates.waiting_for_difficult_subjects)
    await state.update_data(selected_diff_subjects=[])
    
    text = (
        "<blockquote>"
        "وما هي المواد التي تجد فيها بعض الصعوبة أو تشعر بضعف في استيعابها وتود التركيز عليها أكثر؟"
        "</blockquote>\n"
        "<i>يمكنك اختيار أكثر من مادة من القائمة أدناه:</i>"
    )
    keyboard = kb.get_subjects_selection_keyboard([], "onb_diff")
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(RegistrationStates.waiting_for_favorite_subjects, F.data.startswith("onb_fav:"))
async def handle_onb_fav_callback(callback: CallbackQuery, state: FSMContext):
    action_parts = callback.data.split(":")
    action = action_parts[1]
    
    if action == "toggle":
        sub = action_parts[2]
        data = await state.get_data()
        selected = data.get("selected_fav_subjects", [])
        if sub in selected:
            selected.remove(sub)
        else:
            selected.append(sub)
        await state.update_data(selected_fav_subjects=selected)
        
        keyboard = kb.get_subjects_selection_keyboard(selected, "onb_fav")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        
    elif action == "skip":
        user_id = callback.from_user.id
        await db.update_user_favorite_subjects(user_id, [])
        await callback.answer("⏭️ تم تخطي تحديد المواد المفضلة.")
        await start_difficult_subjects_selection(callback, state)
        
    elif action == "done":
        user_id = callback.from_user.id
        data = await state.get_data()
        selected = data.get("selected_fav_subjects", [])
        await db.update_user_favorite_subjects(user_id, selected)
        await callback.answer("✅ تم حفظ المواد المفضلة.")
        await start_difficult_subjects_selection(callback, state)

@router.callback_query(RegistrationStates.waiting_for_difficult_subjects, F.data.startswith("onb_diff:"))
async def handle_onb_diff_callback(callback: CallbackQuery, state: FSMContext):
    action_parts = callback.data.split(":")
    action = action_parts[1]
    
    if action == "toggle":
        sub = action_parts[2]
        data = await state.get_data()
        selected = data.get("selected_diff_subjects", [])
        if sub in selected:
            selected.remove(sub)
        else:
            selected.append(sub)
        await state.update_data(selected_diff_subjects=selected)
        
        keyboard = kb.get_subjects_selection_keyboard(selected, "onb_diff")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        
    elif action == "skip":
        user_id = callback.from_user.id
        await db.update_user_difficult_subjects(user_id, [])
        await callback.answer("⏭️ تم تخطي تحديد المواد الصعبة.")
        await state.clear()
        await show_guide_page(callback, page=1)
        
    elif action == "done":
        user_id = callback.from_user.id
        data = await state.get_data()
        selected = data.get("selected_diff_subjects", [])
        await db.update_user_difficult_subjects(user_id, selected)
        await callback.answer("✅ تم حفظ المواد الصعبة.")
        await state.clear()
        await show_guide_page(callback, page=1)

async def show_guide_page(message_or_callback_msg, page: int):
    user_id = message_or_callback_msg.from_user.id
    user = await db.get_user(user_id)
    text = await get_guide_page_text(user, page)
    reply_markup = kb.get_guide_page_keyboard(page)
    
    if isinstance(message_or_callback_msg, CallbackQuery):
        await message_or_callback_msg.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    elif hasattr(message_or_callback_msg, "edit_text") and (
        not isinstance(message_or_callback_msg, Message) or 
        (message_or_callback_msg.from_user and message_or_callback_msg.from_user.is_bot)
    ):
        try:
            await message_or_callback_msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await message_or_callback_msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await message_or_callback_msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("guide_page:"))
async def handle_guide_page_nav(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.split(":")[1])
    await show_guide_page(callback.message, page=page)

@router.callback_query(F.data == "guide_finish")
async def handle_guide_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    
    greeting = get_user_greeting(user)
    pref_sub = await db.get_user_preferred_subject(user_id)
    if pref_sub:
        pref_sub_ar = kb.SUBJECT_LABELS.get(pref_sub, pref_sub)
        subject_block = f"<blockquote>🎯 <b>المادة النشطة:</b> <b>{pref_sub_ar}</b></blockquote>"
    else:
        subject_block = "<blockquote>🎯 <b>المادة النشطة:</b> <b>كافة المواد</b></blockquote>"
        
    welcome_text = (
        f"أهلاً بك في أكاديمية الباجي للعلوم الشرعية {greeting}! 🎓\n\n"
        f"{subject_block}\n\n"
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة التمارين والمسار التعليمي:"
    )
    if is_admin(user_id):
        import os
        admin_webapp = os.getenv("ADMIN_WEBAPP_URL") or "http://localhost:8082/admin"
        if not admin_webapp.startswith("https"):
            welcome_text += f"\n\n🖥️ <b>رابط لوحة التحكم للمشرف:</b>\n🔗 <a href='{admin_webapp}'>{admin_webapp}</a>"
            
    await callback.message.edit_text(
        welcome_text,
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )
    
    # Process pending deep link if any
    data = await state.get_data()
    pending_deep_link = data.get("pending_deep_link")
    if pending_deep_link:
        await process_deep_link(callback.message, pending_deep_link, state)

# ─── Main Inline Menu Callback Handlers ───────────────────────────────────────────

@router.callback_query(F.data == "main_training_menu")
async def handle_main_training_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📝 <b>أتدرب:</b>\n\nاختر نوع التدريب الذي تريده:",
        reply_markup=kb.get_training_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "main_new_quiz")
async def handle_main_new_quiz(callback: CallbackQuery, state: FSMContext):
    await callback.answer("📚 جاري فتح قائمة المواد لبدء اختبار جديد...")
    await cmd_new_quiz_text(callback, state, user_id=callback.from_user.id)

@router.callback_query(F.data == "main_resume")
async def handle_main_resume(callback: CallbackQuery, state: FSMContext):
    await callback.answer("🔄 جاري فتح قائمة المواد لمتابعة مسارك...")
    await cmd_continue_quiz(callback, state, user_id=callback.from_user.id)

@router.callback_query(F.data == "main_progress")
async def handle_main_progress(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await render_progress_page(callback, callback.from_user.id, 0)

@router.callback_query(F.data == "main_support")
async def handle_main_support(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.support import cmd_support
    await cmd_support(callback, state)

@router.callback_query(F.data == "main_admin")
async def handle_main_admin(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.admin import cmd_admin
    await cmd_admin(callback, state)

@router.callback_query(F.data == "main_favorites")
async def handle_main_favorites(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.favorites_errors import cmd_favorites
    await cmd_favorites(callback, state)

@router.callback_query(F.data == "main_errors")
async def handle_main_errors(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.favorites_errors import cmd_errors
    await cmd_errors(callback, state)

# ─── Command/Logic Trigger Handlers ──────────────────────────────────────────────

async def render_mode_selection_fallback(message_or_callback, state: FSMContext, subject: str):
    from handlers.quiz import QuizStates, SUBJECT_MAP
    await state.set_state(QuizStates.selecting_mode)
    await state.update_data(subject=subject)
    
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
        
    reply_markup = kb.get_quiz_mode_selection_keyboard(subject)
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=reply_markup, parse_mode="HTML")

async def cmd_new_quiz_text(message_or_callback, state: FSMContext, user_id: int):
    await state.clear()

    # ── Group membership guard ──────────────────────────────────────────────
    bot = message_or_callback.bot if isinstance(message_or_callback, Message) else message_or_callback.message.bot
    restrict_val = await db.get_setting("restrict_to_academy_group", "True") == "True"
    if restrict_val and not is_admin(user_id) and not await is_academy_member(bot, user_id):
        text = "⛔ عذراً، هذا البوت مخصص لطلاب أكاديمية الباجي فقط."
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(text, show_alert=True)
        else:
            await message_or_callback.answer(text)
        return
    # ───────────────────────────────────────────────────────────────────────

    # Bypass subject selection if a preferred subject is defined
    pref_sub = await db.get_user_preferred_subject(user_id)
    if pref_sub:
        await render_mode_selection_fallback(message_or_callback, state, pref_sub)
        return

    from handlers.quiz import QuizStates
    await state.set_state(QuizStates.selecting_subject)

    text = "📚 <b>يرجى تحديد المادة الدراسية لبدء التمرين:</b>"
    reply_markup = kb.get_subject_list_keyboard(None)

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

async def cmd_continue_quiz(message_or_callback, state: FSMContext, user_id: int):
    """Launch a quiz with only unanswered or wrong questions."""
    await state.clear()

    # Check overall remaining questions across all subjects
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']

    if remaining == 0:
        text = (
            "🏆 <b>تهانينا! لقد أتممت جميع الأسئلة بنجاح!</b>\n\n"
            "✅ لقد أجبت على كل الأسئلة المتاحة بشكل صحيح.\n"
            "يمكنك بدء اختبار جديد من القائمة."
        )
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(text, parse_mode="HTML")
        else:
            await message_or_callback.answer(text, parse_mode="HTML")
        return

    # Bypass subject selection if preferred subject is defined
    pref_sub = await db.get_user_preferred_subject(user_id)
    if pref_sub:
        await state.update_data(continue_mode=True)
        await render_mode_selection_fallback(message_or_callback, state, pref_sub)
        return

    # Show subject selection to choose which subject to continue
    from handlers.quiz import QuizStates
    await state.set_state(QuizStates.selecting_subject)
    await state.update_data(continue_mode=True)  # Flag for continue mode
    
    remaining_counts = await db.get_remaining_questions_count_per_subject(user_id)
    text = (
        f"▶️ <b>استئناف التمرين (المسار المتبقي)</b>\n\n"
        f"لديك <b>{remaining}</b> سؤال متبقٍ لم تُجِب عليه بشكل صحيح بعد.\n"
        f"اختر المادة التي تريد الاستمرار فيها:\n\n"
        f"⚠️ <i>الأرقام الظاهرة بين قوسين بجانب أسماء المواد تمثل <b>عدد الأسئلة المتبقية فقط</b> (الأسئلة التي لم تُحل بعد + الأسئلة التي أجبت عليها بشكل خاطئ سابقاً، وليس العدد الإجمالي للأسئلة).</i>"
    )
    reply_markup = kb.get_subject_list_keyboard(remaining_counts)
    
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

# ─── Progress Dashboard ────────────────────────────────────────────────────────

SUBJECT_LABELS = {
    "fiqh": "الفقه",
    "sira": "السيرة النبوية",
    "nahw": "النحو",
    "aqeeda": "العقيدة",
    "tajweed": "علم التجويد"
}

def _build_progress_bar(correct: int, wrong: int, not_done: int, total: int) -> str:
    """Build a visual progress bar using block characters for a modern premium feel."""
    if total == 0:
        return "░░░░░░░░░░ 0%"
    pct = (correct / total)
    filled_blocks = int(pct * 10)
    bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
    return f"`{bar}` {round(pct * 100)}%"

async def render_progress_page(message_or_callback, user_id: int, subject_idx: int):
    """Render a specific subject's progress page with beautiful bars and estimation details."""
    subjects = ["fiqh", "sira", "nahw", "aqeeda", "tajweed"]
    if subject_idx < 0 or subject_idx >= len(subjects):
        return
        
    subject = subjects[subject_idx]
    stats = await db.get_user_overall_stats(user_id)
    dashboard = await db.get_progress_dashboard(user_id)
    
    total = stats['total']
    correct = stats['correct']
    wrong = stats['wrong']
    not_done = stats['not_done']
    overall_pct = round((correct / total) * 100) if total > 0 else 0
    
    # Calculate global remaining questions to master
    global_remaining = not_done + wrong
    
    subj_label = SUBJECT_LABELS.get(subject, subject)
    courses = dashboard.get(subject, {})
    subj_total = sum(c['total'] for c in courses.values())
    subj_correct = sum(c['correct'] for c in courses.values())
    subj_pct = round((subj_correct / subj_total) * 100) if subj_total > 0 else 0
    
    # Create the beautiful header
    text = (
        f"📊 <b>لوحة تقدّمي | {subj_label}</b>\n"
        f"<i>(المادة {subject_idx + 1} من {len(subjects)})</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 الإتقان العام للمقرر: <b>{overall_pct}%</b> ({correct}/{total} سؤال)\n"
        f"📚 إتقان مادة {subj_label}: <b>{subj_pct}%</b> ({subj_correct}/{subj_total})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    if not courses:
        text += "⚠️ لا توجد دروس مسجلة لهذه المادة حالياً.\n"
    else:
        for cn in sorted(courses.keys()):
            c = courses[cn]
            
            # Course status icon
            if c['correct'] == c['total'] and c['total'] > 0:
                icon = "✅"
            elif c['correct'] > 0 or c['wrong'] > 0:
                icon = "🔄"
            else:
                icon = "⬜"
            
            text += f"  {icon} <b>الدرس {cn}</b>:\n"
            text += f"    📖 الأسئلة المنهجية: {_build_progress_bar(c['official_correct'], 0, 0, c['official_total'])} ({c['official_correct']}/{c['official_total']})\n"
            if c['extra_total'] > 0:
                text += f"    ✨ أسئلة إضافية معتمدة: {_build_progress_bar(c['extra_correct'], 0, 0, c['extra_total'])} ({c['extra_correct']}/{c['extra_total']})\n"
            if c['wrong'] > 0:
                text += f"    ❌ أسئلة تحتاج مراجعة: <b>{c['wrong']}</b>\n"
            text += "\n"
            
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    # Add a personalized motivational estimation
    if global_remaining > 0:
        daily_target = 10
        days_needed = int(global_remaining / daily_target)
        if global_remaining % daily_target > 0:
            days_needed += 1
            
        text += (
            f"🎯 <b>الهدف المتبقي للامتحان:</b>\n"
            f"💡 متبقّي لك <b>{global_remaining}</b> سؤالاً للوصول للإتقان الكامل (100%).\n"
            f"⏱️ بمعدل <b>{daily_target} أسئلة يومياً</b>، ستنهي مراجعة المقرر بالكامل في خلال <b>{days_needed} أيام</b> فقط بإذن الله! 🌟\n"
        )
    else:
        text += "🏆 <b>مبارك عليك! لقد حققت نسبة إتقان 100% في جميع المواد!</b>\n"
        
    reply_markup = kb.get_progress_browser_keyboard(subject_idx, len(subjects))
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    elif isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")

@router.callback_query(F.data.startswith("prog_browse:"))
async def handle_prog_browse(callback: CallbackQuery):
    subject_idx = int(callback.data.split(":")[1])
    await render_progress_page(callback, callback.from_user.id, subject_idx)
    await callback.answer()

@router.callback_query(F.data == "prog_close")
@router.callback_query(F.data == "main_cancel")
async def handle_prog_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    from handlers.start import is_admin
    stats = await db.get_user_overall_stats(user_id)
    remaining = stats['not_done'] + stats['wrong']
    unread_count = await db.get_unread_reports_count(user_id)
    
    welcome_text = (
        "🎓 <b>القائمة الرئيسية:</b>\n\n"
        "اختر أحد الخيارات التالية لمتابعة التمارين والمسار التعليمي:"
    )
    if is_admin(user_id):
        import os
        admin_webapp = os.getenv("ADMIN_WEBAPP_URL") or "http://localhost:8082/admin"
        if not admin_webapp.startswith("https"):
            welcome_text += f"\n\n🖥️ <b>رابط لوحة التحكم للمشرف:</b>\n🔗 <a href='{admin_webapp}'>{admin_webapp}</a>"
            
    await callback.message.edit_text(
        welcome_text,
        reply_markup=kb.get_main_inline_keyboard(is_admin=is_admin(user_id), remaining_count=remaining, unread_count=unread_count),
        parse_mode="HTML"
    )
    if callback.data == "prog_close":
        await callback.answer("🚪 تم إغلاق لوحة التقدم.")
    else:
        await callback.answer()

@router.callback_query(F.data == "main_settings")
async def handle_main_settings(callback: CallbackQuery, state: FSMContext = None):
    if callback:
        await callback.answer()
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    # map "f" or "m" gender values from DB to female / male
    gender_raw = user.get("gender") if user else None
    gender = "female" if gender_raw == "f" else "male" if gender_raw == "m" else None
    
    layout = await db.get_user_inbox_layout(user_id)
    settings_layout = await db.get_user_settings_layout(user_id)
    
    # Get favorite/difficult subjects
    fav_subs, diff_subs = await db.get_user_favorites_and_difficult_subjects(user_id)
    pref_sub = await db.get_user_preferred_subject(user_id)
    contributions = await db.get_user_contributions_count(user_id)
    
    # Format subject lists in Arabic
    SUBJECT_AR = {
        "fiqh": "الفقه",
        "sira": "السيرة النبوية",
        "nahw": "النحو",
        "aqeeda": "العقيدة",
        "tajweed": "علم التجويد"
    }
    fav_str = ", ".join(SUBJECT_AR[s] for s in fav_subs if s in SUBJECT_AR) if fav_subs else "لا يوجد"
    diff_str = ", ".join(SUBJECT_AR[s] for s in diff_subs if s in SUBJECT_AR) if diff_subs else "لا يوجد"
    pref_sub_ar = SUBJECT_AR.get(pref_sub, "لا يوجد (تصفح يدوي)") if pref_sub else "لا يوجد (تصفح يدوي)"
    
    gender_str = "أخت (أنثى) 👧" if gender == "female" else "أخ (ذكر) 👦" if gender == "male" else "غير محدد"
    pref_name = user.get("preferred_name") if user else "طالب"
    
    profile_text = (
        "⚙️ <b>الملف الشخصي وإعدادات الطالب:</b>\n\n"
        "<blockquote>"
        f"👤 <b>الاسم:</b> {pref_name}\n"
        f"🎭 <b>صيغة المخاطبة:</b> {gender_str}\n"
        f"🎯 <b>المادة التلقائية:</b> {pref_sub_ar}\n"
        f"🌟 <b>المواد المفضلة:</b> {fav_str}\n"
        f"⚠️ <b>المواد الصعبة:</b> {diff_str}\n"
        f"🏆 <b>مساهماتي في البوت:</b> {contributions} بلاغًا"
        "</blockquote>\n"
        "يمكنك تعديل معلوماتك الشخصية أو خيارات العرض باستخدام الأزرار أدناه:"
    )
    
    await callback.message.edit_text(
        profile_text,
        reply_markup=kb.get_student_settings_keyboard(inbox_layout=layout, gender=gender, settings_layout=settings_layout),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("set_inbox_layout:"))
async def handle_set_inbox_layout(callback: CallbackQuery):
    user_id = callback.from_user.id
    old_layout = callback.data.split(":")[1]
    new_layout = "grid" if old_layout == "chat" else "chat"
    
    await db.set_user_inbox_layout(user_id, new_layout)
    await callback.answer("✅ تم تغيير تخطيط البريد بنجاح!", show_alert=True)
    await handle_main_settings(callback)

@router.callback_query(F.data.startswith("set_settings_layout:"))
async def handle_set_settings_layout(callback: CallbackQuery):
    user_id = callback.from_user.id
    current_layout = callback.data.split(":")[1]
    
    next_layout_map = {
        'classic': 'grid',
        'grid': 'top',
        'top': 'hybrid',
        'hybrid': 'classic'
    }
    new_layout = next_layout_map.get(current_layout, 'classic')
    
    await db.set_user_settings_layout(user_id, new_layout)
    await callback.answer("✅ تم تغيير تخطيط لوحة التمرين بنجاح!", show_alert=True)
    await handle_main_settings(callback)

@router.callback_query(F.data.startswith("set_gender_toggle:"))
async def handle_set_gender_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    new_gender_long = callback.data.split(":")[1]
    new_gender_short = "f" if new_gender_long == "female" else "m"
    
    await db.update_user_gender(user_id, new_gender_short)
    await callback.answer("✅ تم تعديل صيغة المخاطبة بنجاح!", show_alert=True)
    await handle_main_settings(callback)

@router.callback_query(F.data == "edit_fav_subjects")
async def handle_edit_fav_subjects(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    fav_subs, _ = await db.get_user_favorites_and_difficult_subjects(user_id)
    
    await state.set_state(RegistrationStates.waiting_for_favorite_subjects)
    await state.update_data(selected_fav_subjects=fav_subs)
    
    text = (
        "<blockquote>"
        "قم بتعديل المواد التي تفضلها أو تشعر بارتياح أكبر في مذاكرتها:"
        "</blockquote>\n"
        "<i>يمكنك اختيار أكثر من مادة من القائمة أدناه:</i>"
    )
    keyboard = kb.get_subjects_selection_keyboard(fav_subs, "prof_fav")
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "edit_diff_subjects")
async def handle_edit_diff_subjects(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    _, diff_subs = await db.get_user_favorites_and_difficult_subjects(user_id)
    
    await state.set_state(RegistrationStates.waiting_for_difficult_subjects)
    await state.update_data(selected_diff_subjects=diff_subs)
    
    text = (
        "<blockquote>"
        "قم بتعديل المواد التي تجد فيها بعض الصعوبة أو تشعر بضعف في استيعابها:"
        "</blockquote>\n"
        "<i>يمكنك اختيار أكثر من مادة من القائمة أدناه:</i>"
    )
    keyboard = kb.get_subjects_selection_keyboard(diff_subs, "prof_diff")
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("prof_fav:"))
async def handle_prof_fav_callback(callback: CallbackQuery, state: FSMContext):
    action_parts = callback.data.split(":")
    action = action_parts[1]
    user_id = callback.from_user.id
    
    if action == "toggle":
        sub = action_parts[2]
        data = await state.get_data()
        selected = data.get("selected_fav_subjects", [])
        if sub in selected:
            selected.remove(sub)
        else:
            selected.append(sub)
        await state.update_data(selected_fav_subjects=selected)
        
        keyboard = kb.get_subjects_selection_keyboard(selected, "prof_fav")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        
    elif action == "skip":
        await db.update_user_favorite_subjects(user_id, [])
        await callback.answer("✅ تم تفريغ المواد المفضلة.")
        await state.clear()
        await handle_main_settings(callback)
        
    elif action == "done":
        data = await state.get_data()
        selected = data.get("selected_fav_subjects", [])
        await db.update_user_favorite_subjects(user_id, selected)
        await callback.answer("✅ تم حفظ التعديلات.")
        await state.clear()
        await handle_main_settings(callback)

@router.callback_query(F.data.startswith("prof_diff:"))
async def handle_prof_diff_callback(callback: CallbackQuery, state: FSMContext):
    action_parts = callback.data.split(":")
    action = action_parts[1]
    user_id = callback.from_user.id
    
    if action == "toggle":
        sub = action_parts[2]
        data = await state.get_data()
        selected = data.get("selected_diff_subjects", [])
        if sub in selected:
            selected.remove(sub)
        else:
            selected.append(sub)
        await state.update_data(selected_diff_subjects=selected)
        
        keyboard = kb.get_subjects_selection_keyboard(selected, "prof_diff")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
        
    elif action == "skip":
        await db.update_user_difficult_subjects(user_id, [])
        await callback.answer("✅ تم تفريغ المواد الصعبة.")
        await state.clear()
        await handle_main_settings(callback)
        
    elif action == "done":
        data = await state.get_data()
        selected = data.get("selected_diff_subjects", [])
        await db.update_user_difficult_subjects(user_id, selected)
        await callback.answer("✅ تم حفظ التعديلات.")
        await state.clear()
        await handle_main_settings(callback)
