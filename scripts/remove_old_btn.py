import re
with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\[InlineKeyboardButton\(text=".*?", callback_data="guided_path_start"\)\],\n\s*', '', content)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\keyboards.py', 'w', encoding='utf-8') as f:
    f.write(content)
