import re
with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if line.startswith('def get_guided_subjects_keyboard() -> InlineKeyboardMarkup:'):
        skip = True
        new_lines.append(line)
        new_lines.append('    """Keyboard for selecting subject in guided path."""\n')
        new_lines.append('    rows = []\n')
        new_lines.append('    current_row = []\n')
        new_lines.append('    for sub_id, label in SUBJECT_LABELS.items():\n')
        new_lines.append('        current_row.append(InlineKeyboardButton(text=label, callback_data=f"guided_path_sub:{sub_id}"))\n')
        new_lines.append('        if len(current_row) == 2:\n')
        new_lines.append('            rows.append(current_row)\n')
        new_lines.append('            current_row = []\n')
        new_lines.append('    if current_row:\n')
        new_lines.append('        rows.append(current_row)\n')
        new_lines.append('    rows.append([InlineKeyboardButton(text="◀️ مكتبتي الشاملة", callback_data="main_revision")])\n')
        new_lines.append('    return InlineKeyboardMarkup(inline_keyboard=rows)\n')
    elif skip and line.startswith('def get_guided_lessons_keyboard'):
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
