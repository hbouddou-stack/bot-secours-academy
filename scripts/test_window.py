import sqlite3
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clean_arabic_text(text):
    if not text:
        return []
    # Remove Arabic diacritics (harakat)
    harakat_pattern = re.compile(r'[\u064B-\u0652]')
    text = harakat_pattern.sub('', text)
    # Replace some Arabic characters with standardized ones
    text = re.sub(r'[إأآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    # Convert to lowercase and split into words
    words = text.lower().split()
    # Filter out very short words
    words = [w for w in words if len(w) >= 3]
    return words

def find_best_window(question_text, correct_answer, segments, window_before=5, window_after=5):
    if not segments:
        return ""
    
    q_words = clean_arabic_text(question_text)
    ans_words = clean_arabic_text(correct_answer)
    target_words = set(q_words + ans_words * 2)
    
    best_score = -1
    best_idx = 0
    
    for i, seg in enumerate(segments):
        content = seg[1]
        seg_words = set(clean_arabic_text(content))
        score = len(target_words.intersection(seg_words))
        
        # Check surrounding context score
        local_words = set()
        for offset in [-1, 0, 1]:
            idx = i + offset
            if 0 <= idx < len(segments):
                local_words.update(clean_arabic_text(segments[idx][1]))
        local_score = len(target_words.intersection(local_words))
        
        total_score = score + 0.5 * local_score
        
        if total_score > best_score:
            best_score = total_score
            best_idx = i
            
    start_idx = max(0, best_idx - window_before)
    end_idx = min(len(segments) - 1, best_idx + window_after)
    
    window_segments = segments[start_idx : end_idx + 1]
    window_text = " ".join([seg[1] for seg in window_segments])
    return window_text, best_idx, best_score

def main():
    conn_main = sqlite3.connect('telegram-bot/persistent_storage/academy.db')
    conn_backup = sqlite3.connect('telegram-bot-backup/backup_bot.db')
    cur_main = conn_main.cursor()
    cur_backup = conn_backup.cursor()
    
    # Let's take one question
    q_id = 1045
    cur_backup.execute(
        "SELECT question, choice_a, choice_b, choice_c, choice_d, correct_answer, course_number FROM questions WHERE id = ?",
        (q_id,)
    )
    row = cur_backup.fetchone()
    if not row:
        print("Question not found!")
        return
        
    question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, course_num = row
    mapping = {'A': choice_a, 'B': choice_b, 'C': choice_c, 'D': choice_d}
    correct_text = mapping.get(correct_ans, "")
    
    print(f"Question {q_id}: {question_text}")
    print(f"Correct Answer ({correct_ans}): {correct_text}")
    
    # Fetch segments
    cur_main.execute(
        "SELECT seconds, content FROM transcript_segments WHERE subject='sira' AND course_number=? ORDER BY seconds ASC",
        (course_num,)
    )
    segments = cur_main.fetchall()
    print(f"Total segments fetched: {len(segments)}")
    
    window_text, best_idx, score = find_best_window(question_text, correct_text, segments)
    print(f"\nBest matching segment index: {best_idx} (score: {score})")
    print(f"Segment content: {segments[best_idx][1]}")
    print(f"\nExtracted Window text ({len(window_text)} chars):")
    print(window_text)
    
    conn_main.close()
    conn_backup.close()

if __name__ == "__main__":
    main()
