import re
import html

def format_gemini_markdown_to_html(text):
    if not text:
        return ""
    
    # 1. Escape HTML first to prevent Telegram parsing errors
    text = html.escape(text)
    
    # 2. Blockquotes: Gemini uses `>` which becomes `&gt;`
    text = re.sub(r'^\s*&gt;\s+(.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    
    # 3. Headers: `### Title`
    text = re.sub(r'^#+\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # 4. Bullets: `* item` or `- item`
    text = re.sub(r'^\s*[\*\-]\s+(.+)$', r'• \1', text, flags=re.MULTILINE)
    
    # 5. Bold: `**text**`
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # 6. Italic: `*text*` or `_text_`
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    
    return text

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the old format_gemini_markdown_to_html implementation
old_func_pattern = r'def format_gemini_markdown_to_html\(text\):.*?return text'
new_func_code = '''def format_gemini_markdown_to_html(text):
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

content = re.sub(old_func_pattern, new_func_code, content, flags=re.DOTALL)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(content)
