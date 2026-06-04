with open(r'c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\handlers\revision.py', 'a', encoding='utf-8') as f:
    f.write('''
@router.callback_query(F.data == "exam_blanc_start")
async def handle_exam_blanc_start(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🎓 <b>الامتحان التجريبي الشامل:</b>\\n\\n"
        "يرجى اختيار المادة التي تود اجتياز الامتحان التجريبي فيها (20 سؤالاً):",
        reply_markup=kb.get_exam_blanc_subjects_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "rev_search_start")
async def handle_rev_search_start_main(callback: CallbackQuery):
    # Route to the existing search handler
    await handle_rev_study_search_start(callback)
''')
