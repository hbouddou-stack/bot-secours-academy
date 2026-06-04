import sys
import re

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

helper = '''
import html
import re
def format_gemini_markdown_to_html(text):
    if not text:
        return ""
    text = html.escape(text)
    text = re.sub(r'\\*\\*(.+?)\\*\\*', r'<b>\\1</b>', text)
    text = re.sub(r'^#+\\s+(.+)$', r'<b>\\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\\s*[\\*\\-]\\s+(.+)$', r'• \\1', text, flags=re.MULTILINE)
    text = re.sub(r'^\\s*>\\s+(.+)$', r'<blockquote>\\1</blockquote>', text, flags=re.MULTILINE)
    return text

@router.callback_query(F.data.startswith("guided_step:") & F.data.endswith(":summary"))
'''

content = content.replace('@router.callback_query(F.data.startswith("guided_step:") & F.data.endswith(":summary"))\n', helper)

old_logic = '''                fiche_content = row[0]
                
    if fiche_content:'''

new_logic = '''                fiche_content = row[0]
                
    if fiche_content:
        fiche_content = format_gemini_markdown_to_html(fiche_content)'''

content = content.replace(old_logic, new_logic)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(content)
