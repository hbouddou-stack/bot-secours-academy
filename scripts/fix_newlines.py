import re

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace actual literal newlines inside the f-strings we just added with "\\n"
# The string replacement script above had actual newlines generated inside the text
content = re.sub(r'f"📚 <b>خطة الدرس \{lesson\} - \{sub_ar\}</b>\n"', r'f"📚 <b>خطة الدرس {lesson} - {sub_ar}</b>\\n"', content)
content = re.sub(r'f"المسار التفاعلي مقسم إلى المحاور التالية:\n\n"', r'f"المسار التفاعلي مقسم إلى المحاور التالية:\\n\\n"', content)

content = re.sub(r'text \+= f"\{status\} \{i\+1\}\. \{ch\[\'title\'\]\}\n"', r'text += f"{status} {i+1}. {ch[\'title\']}\\n"', content)

content = re.sub(r'f"\n💡 <i>أنت حالياً عند المحور \{idx \+ 1\}\. يمكنك استئناف التعلم من حيث توقفت\.</i>"', r'f"\\n💡 <i>أنت حالياً عند المحور {idx + 1}. يمكنك استئناف التعلم من حيث توقفت.</i>"', content)

content = re.sub(r'f"\n🎉 <i>لقد أتممت جميع محاور هذا الدرس بنجاح!</i>"', r'f"\\n🎉 <i>لقد أتممت جميع محاور هذا الدرس بنجاح!</i>"', content)

content = re.sub(r'text = f"📖 <b>المحور \{idx\+1\}: \{chapter\[\'title\'\]\}</b>\n\n\{content_html\}"', r'text = f"📖 <b>المحور {idx+1}: {chapter[\'title\']}</b>\\n\\n{content_html}"', content)

content = re.sub(r'text = f"❓ <b>سؤال المحور:</b>\n\n\{q_data\[0\]\}"', r'text = f"❓ <b>سؤال المحور:</b>\\n\\n{q_data[0]}"', content)

content = re.sub(r'text = f"🎉 <b>ممتاز يا \{callback\.from_user\.first_name\}! لقد أتممت المحور بنجاح\.</b>\n"', r'text = f"🎉 <b>ممتاز يا {callback.from_user.first_name}! لقد أتممت المحور بنجاح.</b>\\n"', content)

content = re.sub(r'text \+= f"\n💡 <b>توضيح:</b> \{explanation\}\n"', r'text += f"\\n💡 <b>توضيح:</b> {explanation}\\n"', content)

content = re.sub(r'caption = f"🗺️ <b>الخريطة الذهنية - الدرس \{lesson\} \(\{sub_ar\}\)</b>\n\nأنت الآن جاهز للملخص الشامل والاختبار!"', r'caption = f"🗺️ <b>الخريطة الذهنية - الدرس {lesson} ({sub_ar})</b>\\n\\nأنت الآن جاهز للملخص الشامل والاختبار!"', content)

with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'w', encoding='utf-8') as f:
    f.write(content)
