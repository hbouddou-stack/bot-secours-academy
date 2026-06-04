with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'if "revision" not in hidden_buttons:' in line and 'get_revision_lessons_keyboard' in "".join(lines[max(0, i-40):i]):
        lines[i] = '    rows.append([InlineKeyboardButton(text="◀️ العودة للخلف", callback_data="main_revision")])\n'
        lines[i+1] = '' # Remove the inner append since we replaced the condition with the append

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
