import html
import re

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start and end of the function
start_idx = content.find("def format_gemini_markdown_to_html(text):")
end_idx = content.find("return text", start_idx) + len("return text")

old_func = content[start_idx:end_idx]

new_func = '''def format_gemini_markdown_to_html(text):
    if not text:
        return ""
    text = html.escape(text)
    text = re.sub(r'^\\s*&gt;\\s+(.+)$', r'<blockquote>\\1</blockquote>', text, flags=re.MULTILINE)
    text = re.sub(r'^#+\\s+(.+)$', r'<b>\\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\\s*[\\*\\-]\\s+(.+)$', r'• \\1', text, flags=re.MULTILINE)
    text = re.sub(r'\\*\\*(.+?)\\*\\*', r'<b>\\1</b>', text)
    text = re.sub(r'\\*(.+?)\\*', r'<i>\\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\\1</i>', text)
    return text'''

content = content.replace(old_func, new_func)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(content)
