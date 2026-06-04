import os
import sqlite3
import time
import re
import sys
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Force stdout to use UTF-8 to prevent UnicodeEncodeError on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY or GOOGLE_API_KEY not found in environment!")
    exit(1)

genai.configure(api_key=api_key)

# Database paths
DB_BACKUP_PATH = "telegram-bot-backup/backup_bot.db"
DB_MAIN_PATH = "telegram-bot/persistent_storage/academy.db"

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

def find_best_window(question_text, correct_answer, segments):
    if not segments:
        return ""
    
    # If total segments are few (e.g. less than 50), send the entire thing
    if len(segments) <= 50:
        return " ".join([s[1] for s in segments])
        
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
            
    # Window of 7 segments before and 7 segments after (approx. 15 segments total)
    window_before = 7
    window_after = 7
    
    start_idx = max(0, best_idx - window_before)
    end_idx = min(len(segments) - 1, best_idx + window_after)
    
    window_segments = segments[start_idx : end_idx + 1]
    window_text = " ".join([s[1] for s in window_segments])
    return window_text

def get_transcript_segments(subject, course_number):
    if not os.path.exists(DB_MAIN_PATH):
        return []
    conn = sqlite3.connect(DB_MAIN_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT seconds, content FROM transcript_segments WHERE subject = ? AND course_number = ? ORDER BY seconds ASC",
        (subject, course_number)
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows if r[1]]

def generate_explanation(question, choices, correct_answer, transcript):
    prompt = f"""أنت خبير أكاديمي في العلوم الشرعية والسيرة النبوية.
لديك تفريغ نصي لدرس ألقاه الشيخ:
\"\"\"
{transcript}
\"\"\"

إليك سؤالاً متعدد الخيارات حول هذا الدرس:
السؤال: {question}
الخيارات:
{choices}
الإجابة الصحيحة: {correct_answer}

بناءً على تفريغ الدرس أعلاه فقط، استخرج الشرح أو التعليل الذي ذكره الشيخ لتوضيح لماذا هذه الإجابة هي الصحيحة.
اكتب الشرح باللغة العربية الفصحى بطريقة تعليمية واضحة وموجزة جداً (بين 2 إلى 3 جمل كحد أقصى).
ابدأ الشرح مباشرة دون عبارات تمهيدية مثل "بناء على التفريغ" أو "يقول الشيخ". لا تستخدم التنسيق العريض (bold) إلا للكلمات المفتاحية الهامة جداً.
المخرج يجب أن يكون باللغة العربية الفصحى فقط.
"""
    # Using gemini-2.5-flash which is fast and cost-effective
    model = genai.GenerativeModel("gemini-2.5-flash")
    for attempt in range(5):
        try:
            print(f"Sending request to Gemini (attempt {attempt+1})...")
            response = model.generate_content(prompt)
            print("Received response from Gemini.")
            return response.text.strip()
        except Exception as e:
            err_msg = str(e)
            print(f"Error calling Gemini: {err_msg}")
            if "429" in err_msg or "quota" in err_msg.lower():
                print("Rate limit hit. Sleeping 40 seconds before retry...")
                time.sleep(40)
            else:
                return None
    return None

def main():
    if not os.path.exists(DB_BACKUP_PATH):
        print(f"Backup DB not found at: {DB_BACKUP_PATH}")
        return
        
    conn_backup = sqlite3.connect(DB_BACKUP_PATH)
    cur_backup = conn_backup.cursor()
    
    # Get Sira questions for courses 14 to 22
    cur_backup.execute(
        "SELECT id, course_number, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation FROM questions WHERE subject='sira' AND course_number >= 14 AND course_number <= 22"
    )
    questions = cur_backup.fetchall()
    print(f"Found {len(questions)} Sira questions (courses 14 to 22) in Backup DB.")
    
    conn_main = None
    if os.path.exists(DB_MAIN_PATH):
        conn_main = sqlite3.connect(DB_MAIN_PATH)
        
    updated_count = 0
    for q in questions:
        q_id, course_num, question_text, choice_a, choice_b, choice_c, choice_d, correct_ans, existing_exp = q
        
        # Check if explanation already exists (longer than 15 chars to avoid simple placeholders)
        if existing_exp and len(existing_exp.strip()) > 15:
            print(f"Question {q_id} (Course {course_num}) already has explanation. Skipping.")
            continue
            
        print(f"\n--------------------------------------------------")
        print(f"Processing Question {q_id} (Course {course_num})...")
        
        segments = get_transcript_segments("sira", course_num)
        print(f"Transcript segments fetched: {len(segments)}")
        if not segments:
            print(f"No transcript segments found for Sira Course {course_num}. Skipping.")
            continue
            
        mapping = {'A': choice_a, 'B': choice_b, 'C': choice_c, 'D': choice_d}
        correct_answer_text = mapping.get(correct_ans, "")
        
        transcript_window = find_best_window(question_text, correct_answer_text, segments)
        print(f"Context window length: {len(transcript_window)} chars.")
        if not transcript_window:
            print("Could not find matching window. Skipping.")
            continue
            
        choices_str = f"أ) {choice_a}\nب) {choice_b}\nج) {choice_c}\nد) {choice_d}"
        
        explanation = generate_explanation(question_text, choices_str, correct_ans, transcript_window)
        if explanation:
            # Save to backup DB
            cur_backup.execute(
                "UPDATE questions SET explanation = ? WHERE id = ?",
                (explanation, q_id)
            )
            conn_backup.commit()
            
            # Save to main DB if exists
            if conn_main:
                cur_main = conn_main.cursor()
                cur_main.execute(
                    "UPDATE official_questions SET explanation = ? WHERE id = ?",
                    (explanation, q_id)
                )
                conn_main.commit()
                
            print(f"Successfully generated explanation for Question {q_id}:")
            print(f"\"{explanation}\"")
            updated_count += 1
            time.sleep(12) # rate limiting (5 RPM = 1 per 12 seconds)
            
    conn_backup.close()
    if conn_main:
        conn_main.close()
        
    print(f"\n==================================================")
    print(f"Generation completed! Updated {updated_count} questions.")

if __name__ == "__main__":
    main()
