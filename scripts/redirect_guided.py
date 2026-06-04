import re

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'@router\.callback_query\(F\.data\.startswith\("guided_path_les:"\)\)\nasync def handle_guided_path_les\(callback: CallbackQuery, state: FSMContext\):.*?except Exception:\n\s+pass\n\s+await callback\.message\.answer\(\n\s+text=text,\n\s+reply_markup=kb\.get_guided_lesson_hub_keyboard\(subject, lesson_num, prog\),\n\s+parse_mode="HTML"\n\s+\)'

replacement = '''@router.callback_query(F.data.startswith("guided_path_les:"))
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
    await handle_rev_study_path_start(fake_cb, state)'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
