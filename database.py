import aiosqlite
import logging
import re
from config import DATABASE_PATH, MAIN_DATABASE_PATH

logger = logging.getLogger(__name__)

import shutil
import os

async def init_db():
    """Initialize SQLite database and create all tables if they do not exist."""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    local_db = os.path.join(os.path.dirname(__file__), "backup_bot.db")
    if DATABASE_PATH != local_db and os.path.exists(local_db):
        should_copy = False
        if not os.path.exists(DATABASE_PATH):
            should_copy = True
        else:
            db_size = os.path.getsize(DATABASE_PATH)
            if db_size < 3000000:  # If less than 3MB (our seeded DB is 3.9MB)
                should_copy = True
            else:
                try:
                    import sqlite3
                    conn = sqlite3.connect(DATABASE_PATH)
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM questions")
                    cnt = c.fetchone()[0]
                    conn.close()
                    if cnt == 0:
                        should_copy = True
                except Exception:
                    should_copy = True
                    
        if should_copy:
            try:
                # Remove WAL/shm files if they exist to avoid corruption when replacing the main file
                for ext in ["-wal", "-shm"]:
                    extra_file = DATABASE_PATH + ext
                    if os.path.exists(extra_file):
                        try:
                            os.remove(extra_file)
                        except Exception:
                            pass
                shutil.copy2(local_db, DATABASE_PATH)
                logger.info(f"Forced copy of seeded database to {DATABASE_PATH}")
            except Exception as e:
                logger.error(f"Failed to copy seeded db: {e}")
            
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Enable WAL mode and busy timeout to avoid database locks and crashes
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=5000;")
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON;")
        
        # 1. users
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                gender TEXT,
                preferred_name TEXT,
                academic_year INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        
        # 2. questions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY,
                subject TEXT,
                course_number INTEGER,
                course_name TEXT,
                question TEXT,
                choice_a TEXT,
                choice_b TEXT,
                choice_c TEXT,
                choice_d TEXT,
                correct_answer TEXT,
                explanation TEXT,
                source TEXT,
                created_at TEXT,
                hijra_year INTEGER,
                theme TEXT,
                sub_theme TEXT
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_questions_course ON questions(course_number);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_questions_source ON questions(source);")
        
        # 3. user_favorites
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_id INTEGER,
                subject TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, question_id),
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
        """)
        
        # 4. user_errors
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_id INTEGER,
                subject TEXT,
                wrong_answer TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, question_id),
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
        """)

        # 4b. student_course_progress (Learning Path)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS student_course_progress (
                user_id INTEGER,
                subject TEXT,
                course_number INTEGER,
                resume_done INTEGER DEFAULT 0,
                mindmap_done INTEGER DEFAULT 0,
                flashcards_done INTEGER DEFAULT 0,
                quiz_done INTEGER DEFAULT 0,
                fiche_generated INTEGER DEFAULT 0,
                last_activity TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, subject, course_number),
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scp_user ON student_course_progress(user_id);")
        
        # 5. support_tickets
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                admin_message_id INTEGER PRIMARY KEY,
                student_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        
        # 5b. question_reports
        await db.execute("""
            CREATE TABLE IF NOT EXISTS question_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                report_type TEXT,
                question_id INTEGER DEFAULT 0,
                target TEXT DEFAULT 'official',
                notes TEXT DEFAULT '',
                urgency TEXT DEFAULT 'Moyen',
                status TEXT DEFAULT 'pending',
                admin_reply TEXT DEFAULT '',
                reviewed_at TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                source TEXT DEFAULT 'telegram',
                contact_info TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
        """)
        
        # 5c. question_proposals
        await db.execute("""
            CREATE TABLE IF NOT EXISTS question_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                subject TEXT,
                course_number INTEGER,
                question TEXT,
                choice_a TEXT,
                choice_b TEXT,
                choice_c TEXT,
                choice_d TEXT,
                correct_answer TEXT,
                explanation TEXT,
                status TEXT DEFAULT 'pending',
                admin_reply TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                source TEXT DEFAULT 'telegram',
                contact_info TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            );
        """)
        
        # 6. quiz_logs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quiz_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_id INTEGER,
                is_correct INTEGER,
                answered_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
        """)
        
        # 7. question_progress — tracks mastery per user per question
        await db.execute("""
            CREATE TABLE IF NOT EXISTS question_progress (
                user_id INTEGER,
                question_id INTEGER,
                status TEXT DEFAULT 'not_done',  -- 'not_done', 'wrong', 'correct'
                attempts INTEGER DEFAULT 0,
                last_answered_at TEXT,
                PRIMARY KEY (user_id, question_id),
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_progress_user ON question_progress(user_id);")
        
        # 8. settings — key-value store for configurations
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        
        # 9. admins — local admin cache for the backup bot
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                telegram_id  INTEGER PRIMARY KEY,
                role         TEXT NOT NULL
                             CHECK(role IN ('super_admin','backup_admin','support_admin','moderator','improvement_admin')),
                username     TEXT DEFAULT '',
                first_name   TEXT DEFAULT '',
                added_by     INTEGER,
                added_at     TEXT DEFAULT (datetime('now'))
            );
        """)
        
        # 10. lesson_resources
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lesson_resources (
                subject TEXT,
                course_number INTEGER,
                mind_map_file_id TEXT,
                summary_file_id TEXT,
                PRIMARY KEY (subject, course_number)
            );
        """)
        
        # 11. lesson_transcription_pages
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lesson_transcription_pages (
                subject TEXT,
                course_number INTEGER,
                page_number INTEGER,
                file_id TEXT,
                PRIMARY KEY (subject, course_number, page_number)
            );
        """)
        
        # 12. lesson_mind_map_pages
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lesson_mind_map_pages (
                subject TEXT,
                course_number INTEGER,
                page_number INTEGER,
                file_id TEXT,
                PRIMARY KEY (subject, course_number, page_number)
            );
        """)

        # 13. course_chapters — stores thematic paragraphs/chapters
        await db.execute("""
            CREATE TABLE IF NOT EXISTS course_chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                course_number INTEGER NOT NULL,
                chapter_index INTEGER NOT NULL, -- index of chapter within this course (1, 2, 3...)
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                youtube_link TEXT, -- optional link to video timestamp
                timestamp_seconds INTEGER, -- start timestamp in seconds
                vocabulary_spoilers TEXT, -- key vocabulary words/concepts hidden under spoiler
                UNIQUE(subject, course_number, chapter_index)
            );
        """)

        # 14. course_chapter_questions — QCM verification question per chapter
        await db.execute("""
            CREATE TABLE IF NOT EXISTS course_chapter_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                choice_a TEXT NOT NULL,
                choice_b TEXT NOT NULL,
                choice_c TEXT,
                choice_d TEXT,
                correct_answer TEXT NOT NULL, -- 'a', 'b', 'c', or 'd'
                explanation TEXT,
                hint TEXT,
                FOREIGN KEY(chapter_id) REFERENCES course_chapters(id) ON DELETE CASCADE,
                UNIQUE(chapter_id)
            );
        """)

        # 15. programs - Curriculum Mapping (Level 1)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                name TEXT
            );
        """)

        # 16. thematic_nodes - Curriculum Mapping (Levels 2-4)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS thematic_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                parent_id INTEGER,
                level INTEGER,
                title TEXT,
                order_index INTEGER,
                FOREIGN KEY(program_id) REFERENCES programs(id) ON DELETE CASCADE,
                FOREIGN KEY(parent_id) REFERENCES thematic_nodes(id) ON DELETE CASCADE
            );
        """)

        # Migration: copy existing mind_map_file_id into lesson_mind_map_pages (page 1) if not already there
        async with db.execute("SELECT subject, course_number, mind_map_file_id FROM lesson_resources WHERE mind_map_file_id IS NOT NULL") as cur:
            rows_to_migrate = await cur.fetchall()
        for (subj, cnum, fid) in rows_to_migrate:
            async with db.execute(
                "SELECT COUNT(*) FROM lesson_mind_map_pages WHERE subject = ? AND course_number = ?",
                (subj, cnum)
            ) as chk:
                count = (await chk.fetchone())[0]
            if count == 0:
                await db.execute(
                    "INSERT INTO lesson_mind_map_pages (subject, course_number, page_number, file_id) VALUES (?, ?, 1, ?)",
                    (subj, cnum, fid)
                )
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'preferred_name' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN preferred_name TEXT;")
        
        # Migration: Add claimed_by to question_reports table if missing
        async with db.execute("PRAGMA table_info(question_reports)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'claimed_by' not in columns:
                await db.execute("ALTER TABLE question_reports ADD COLUMN claimed_by TEXT DEFAULT '';")
            if 'student_read' not in columns:
                await db.execute("ALTER TABLE question_reports ADD COLUMN student_read INTEGER DEFAULT 1;")
                
        # Migration: Add is_active to questions if missing
        async with db.execute("PRAGMA table_info(questions)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'is_active' not in columns:
                await db.execute("ALTER TABLE questions ADD COLUMN is_active INTEGER DEFAULT 1;")
            if 'sub_theme' not in columns:
                await db.execute("ALTER TABLE questions ADD COLUMN sub_theme TEXT;")
            if 'thematic_node_id' not in columns:
                await db.execute("ALTER TABLE questions ADD COLUMN thematic_node_id INTEGER;")
                
        # Migration: Clean up Sira themes on remote persistent DB
        await db.execute("UPDATE questions SET theme='العبادات والمعاملات والتشريعات' WHERE theme='فرض زكاة الفطر وتعدد الآراء في زكاة المال'")
        await db.execute("UPDATE questions SET theme='بيت النبوة والحياة الشخصية' WHERE theme='أحداث أعقبت بدر: وفاة رقية، زواج فاطمة، وإسلام العباس'")
        await db.execute("UPDATE questions SET theme='العهود والوفود والعلاقات الخارجية' WHERE theme='الصد عن العمرة وبيعة الرضوان'")
        await db.execute("UPDATE questions SET source='official' WHERE subject='sira' AND hijra_year IS NOT NULL AND source='generated_by_gemini'")
        
        # Migration: Inject course_number into Sira source where it's missing
        await db.execute("UPDATE questions SET explanation = REPLACE(explanation, 'تفريغ الدرس (', 'تفريغ الدرس ' || course_number || ' (') WHERE subject='sira' AND explanation LIKE '%تفريغ الدرس (%'")
        
        # Migration: Fix Sira questions source bug (revert AI questions mistakenly marked as official)
        await db.execute(
            """
            UPDATE questions 
            SET source = 'generated_by_gemini' 
            WHERE subject = 'sira' 
              AND hijra_year IS NOT NULL 
              AND source = 'official'
            """
        )
        await db.commit()

        # Migration: Load course_chapters from sync file if present
        import json
        sync_files = [
            os.path.join(os.path.dirname(__file__), "course_chapters_sync.json"),
            os.path.join(os.path.dirname(__file__), "course_chapters_tajweed_sync.json")
        ]
        for sync_file in sync_files:
            if os.path.exists(sync_file):
                try:
                    with open(sync_file, 'r', encoding='utf-8') as f:
                        chapters = json.load(f)
                    for c in chapters:
                        await db.execute(
                            """
                            INSERT OR IGNORE INTO course_chapters 
                            (subject, course_number, chapter_index, title, content, youtube_link, timestamp_seconds, vocabulary_spoilers) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (c["subject"], c["course_number"], c["chapter_index"], c["title"], c["content"], c.get("youtube_link"), c.get("timestamp_seconds"), c.get("vocabulary_spoilers"))
                        )
                    logging.getLogger(__name__).info(f"Loaded {len(chapters)} course chapters from {os.path.basename(sync_file)}.")
                    os.rename(sync_file, sync_file + ".done")
                except Exception as e:
                    logging.getLogger(__name__).error(f"Failed to load course chapters sync file {os.path.basename(sync_file)}: {e}")
        
        # Migration: Add display_preference to admins table if missing
        async with db.execute("PRAGMA table_info(admins)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'display_preference' not in columns:
                await db.execute("ALTER TABLE admins ADD COLUMN display_preference TEXT DEFAULT 'grid';")
            if 'allowed_subjects' not in columns:
                await db.execute("ALTER TABLE admins ADD COLUMN allowed_subjects TEXT DEFAULT NULL;")
            if 'visible_sections' not in columns:
                await db.execute("ALTER TABLE admins ADD COLUMN visible_sections TEXT DEFAULT NULL;")
                
        # Migration: Add inbox_layout to users table if missing
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'inbox_layout' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN inbox_layout TEXT DEFAULT 'chat';")
            if 'settings_layout' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN settings_layout TEXT DEFAULT 'classic';")
            if 'favorite_subjects' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN favorite_subjects TEXT DEFAULT '';")
            if 'difficult_subjects' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN difficult_subjects TEXT DEFAULT '';")
            if 'is_banned' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0;")
            if 'preferred_subject' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN preferred_subject TEXT DEFAULT NULL;")
        
        # Migration: Add hint to course_chapter_questions if missing
        async with db.execute("PRAGMA table_info(course_chapter_questions)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'hint' not in columns:
                await db.execute("ALTER TABLE course_chapter_questions ADD COLUMN hint TEXT;")
                
        # Migration: Add vocabulary_spoilers to course_chapters if missing
        async with db.execute("PRAGMA table_info(course_chapters)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'vocabulary_spoilers' not in columns:
                await db.execute("ALTER TABLE course_chapters ADD COLUMN vocabulary_spoilers TEXT;")
            if 'poetry_verses' not in columns:
                await db.execute("ALTER TABLE course_chapters ADD COLUMN poetry_verses TEXT;")
                
        # Admin custom views — shared/private persistent views (Phase 3)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_custom_views (
                id          TEXT PRIMARY KEY,
                created_by  INTEGER,
                name        TEXT NOT NULL,
                icon        TEXT DEFAULT '📌',
                filters     TEXT DEFAULT '{}',
                visibility  TEXT DEFAULT 'private',
                target_ids  TEXT DEFAULT '[]',
                position    INTEGER DEFAULT 0,
                is_locked   INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)

        # Replicate main bot student report & proposal tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chapter_reports (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                subject TEXT,
                lesson_num INTEGER,
                chapter_idx INTEGER,
                report TEXT,
                status TEXT DEFAULT 'pending',
                admin_reply TEXT DEFAULT '',
                reviewed_at TEXT DEFAULT '',
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'telegram',
                contact_info TEXT DEFAULT ''
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions_proposees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                subject TEXT,
                topic TEXT,
                lesson TEXT,
                course_number INTEGER DEFAULT 0,
                question TEXT,
                choice_a TEXT,
                choice_b TEXT,
                choice_c TEXT,
                choice_d TEXT,
                correct_answer TEXT,
                explanation TEXT DEFAULT '',
                difficulty TEXT DEFAULT 'medium',
                tags TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                admin_feedback TEXT DEFAULT '',
                is_starred INTEGER DEFAULT 0,
                rejection_reason TEXT DEFAULT '',
                modified_question TEXT DEFAULT '',
                modified_choice_a TEXT DEFAULT '',
                modified_choice_b TEXT DEFAULT '',
                modified_choice_c TEXT DEFAULT '',
                modified_choice_d TEXT DEFAULT '',
                modified_correct_answer TEXT DEFAULT '',
                modified_explanation TEXT DEFAULT '',
                hijra_year INTEGER DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT DEFAULT '',
                source TEXT DEFAULT 'telegram',
                contact_info TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(telegram_id)
            );
        """)

        # Migration: Add admin_reply and reviewed_at to chapter_reports if missing
        async with db.execute("PRAGMA table_info(chapter_reports)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'admin_reply' not in columns:
                await db.execute("ALTER TABLE chapter_reports ADD COLUMN admin_reply TEXT DEFAULT '';")
            if 'reviewed_at' not in columns:
                await db.execute("ALTER TABLE chapter_reports ADD COLUMN reviewed_at TEXT DEFAULT '';")
        # Migration: Add admin_role to users if missing
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'academic_year' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN academic_year INTEGER;")
                
        # Migration: Add source and contact_info to omnichannel tables
        for table in ['question_reports', 'chapter_reports', 'questions_proposees']:
            async with db.execute(f"PRAGMA table_info({table})") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if 'source' not in columns:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN source TEXT DEFAULT 'telegram';")
                if 'contact_info' not in columns:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN contact_info TEXT DEFAULT '';")

        # Create canned_responses table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS canned_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                category TEXT,
                content TEXT
            );
        """)

        # Create ticket_chat_messages table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL, -- 'student' or 'admin'
                sender_name TEXT DEFAULT '',
                message TEXT NOT NULL,
                media_file_id TEXT DEFAULT NULL,
                media_type TEXT DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        
        # Migration: Add claimed_by to other support tables if missing
        for table in ['chapter_reports', 'questions_proposees']:
            async with db.execute(f"PRAGMA table_info({table})") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if 'claimed_by' not in columns:
                    await db.execute(f"ALTER TABLE {table} ADD COLUMN claimed_by TEXT DEFAULT '';")

        # Seed default templates if empty
        async with db.execute("SELECT COUNT(*) FROM canned_responses") as cur:
            row = await cur.fetchone()
            if row and row[0] == 0:
                default_templates = [
                    ("تم حل المشكلة التقنية", "tech", "السلام عليكم، لقد تم حل المشكلة التقنية التي أبلغت عنها. يرجى إعادة المحاولة الآن. شكراً لك!"),
                    ("ملاحظة مقبولة", "content", "السلام عليكم، شكراً لملاحظتك القيمة بخصوص المحتوى. لقد تم تعديل الدرس وتصحيح الخطأ بنجاح."),
                    ("اقتراح سؤال مقبول", "suggestion", "السلام عليكم، لقد تم قبول سؤالك المقترح وإضافته لقاعدة الأسئلة الرسمية. شكراً لمساهمتك!"),
                    ("اقتراح سؤال مرفوض", "suggestion", "السلام عليكم، شكراً لمقترحك. بعد المراجعة العلمية، تعذر قبول السؤال نظراً لـ..."),
                    ("استفسار عام", "other", "السلام عليكم، تم مراجعة طلبك. نسعد دائماً بخدمتك.")
                ]
                await db.executemany("INSERT INTO canned_responses (title, category, content) VALUES (?, ?, ?)", default_templates)

        # Create telegram_groups table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_groups (
                chat_id TEXT PRIMARY KEY,
                academic_year INTEGER NOT NULL,
                group_title TEXT
            );
        """)

        # Migration: Add new fields for support tickets in question_reports if missing
        async with db.execute("PRAGMA table_info(question_reports)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'category' not in columns:
                await db.execute("ALTER TABLE question_reports ADD COLUMN category TEXT DEFAULT '';")
            if 'assigned_admin_id' not in columns:
                await db.execute("ALTER TABLE question_reports ADD COLUMN assigned_admin_id INTEGER DEFAULT NULL;")
            if 'academic_year' not in columns:
                await db.execute("ALTER TABLE question_reports ADD COLUMN academic_year INTEGER DEFAULT NULL;")
            if 'gender' not in columns:
                await db.execute("ALTER TABLE question_reports ADD COLUMN gender TEXT DEFAULT 'indetermine';")

        # Migration: Add sub_theme to questions if missing
        async with db.execute("PRAGMA table_info(questions)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'sub_theme' not in columns:
                await db.execute("ALTER TABLE questions ADD COLUMN sub_theme TEXT DEFAULT '';")

        # Migration: seed official Fiqh lesson 25 questions idempotently.
        fiqh25_questions = [
            (
                "تجوز إمامته مع الكراهة:",
                "المجذوم خفيفُ الجُذام.",
                "الألكَن.",
                "الأغلَف.",
                "كلّ من ذُكر.",
                "c",
            ),
            (
                "تجوز إمامتُه بلا كراهة:",
                "العِنّين.",
                "الخَصيّ.",
                "العبد.",
                "",
                "a",
            ),
            (
                "صلّى الصبحَ خلف إمامه ركعتين تيقّن صحّتهما، وإذ بالإمام يقوم للثالثة. ماذا يصنع هذا المأموم؟",
                "يتابع إمامَه.",
                "ينبّه الإمام ويبقى جالسا.",
                "ينبّهه ثم يتابعه.",
                "يسلّم وحده.",
                "b",
            ),
            (
                "دخل المسجدَ فوجد إمامه راكعا، كيف يصنع ليدخُل في الصلاة؟",
                "يركع مباشرة.",
                "يكبّر مُحرما، ثم يركع.",
                "يكبّر تكبيرة الانتقال ويهوي راكعا.",
                "يكبّر مُحرما، ثم يكبّر تكبيرة الانتقال ويهوي راكعا.",
                "d",
            ),
            (
                "نقصد بالقضاء في الأقوال:",
                "أن يعدّ المسبوقُ ما أدركَ من الأقوال آخرَ صلاته وما فاته أوّلَها فيأتي به.",
                "أن يعدّ المسبوق ما أدركَ من الأقوال أوّلَ صلاته، ويأتي بالتتمّة وحده.",
                "أن يقضي المسبوق الأقوال في ركعة يزيدها بعد سلامه مع الإمام.",
                "",
                "a",
            ),
            (
                "أحوال يقارنُ فيها التكبيرُ قيامَ المسبوق بعد سلام إمامه في المشهور:",
                "إدراك الركعة الأخيرة من الصلاة",
                "إدراك السجدة الأخيرة من الصلاة.",
                "إدراك الركعة الثانية من الصلاة الرباعيّة.",
                "",
                "b",
            ),
        ]
        await db.execute(
            """
            DELETE FROM questions
            WHERE subject = 'fiqh'
              AND course_number = 25
              AND source = 'official'
              AND question LIKE '?%'
            """
        )
        async with db.execute("SELECT COALESCE(MAX(id), 0) FROM questions") as cursor:
            next_question_id = (await cursor.fetchone())[0]
        for question, choice_a, choice_b, choice_c, choice_d, correct_answer in fiqh25_questions:
            async with db.execute(
                """
                SELECT id FROM questions
                WHERE subject = 'fiqh'
                  AND course_number = 25
                  AND question = ?
                LIMIT 1
                """,
                (question,),
            ) as cursor:
                existing_question = await cursor.fetchone()
            values = (
                "fiqh",
                25,
                "الفقه - الدرس 25",
                question,
                choice_a,
                choice_b,
                choice_c,
                choice_d,
                correct_answer,
                "",
                "official",
                None,
                "",
                1,
                "",
            )
            if existing_question:
                await db.execute(
                    """
                    UPDATE questions
                    SET subject = ?, course_number = ?, course_name = ?, question = ?,
                        choice_a = ?, choice_b = ?, choice_c = ?, choice_d = ?,
                        correct_answer = ?, explanation = ?, source = ?,
                        hijra_year = ?, theme = ?, is_active = ?, sub_theme = ?
                    WHERE id = ?
                    """,
                    values + (existing_question[0],),
                )
            else:
                next_question_id += 1
                await db.execute(
                    """
                    INSERT INTO questions (
                        id, subject, course_number, course_name, question,
                        choice_a, choice_b, choice_c, choice_d, correct_answer,
                        explanation, source, created_at, hijra_year, theme, is_active, sub_theme
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)
                    """,
                    (next_question_id,) + values,
                )

        await db.commit()
    logger.info("Database initialized successfully.")


# --- Users Helpers ---

async def get_user(telegram_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_user(telegram_id: int, first_name: str, username: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, first_name, username) VALUES (?, ?, ?)",
            (telegram_id, first_name or "طالب", username)
        )
        await db.commit()

async def update_user_gender(telegram_id: int, gender: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET gender = ? WHERE telegram_id = ?",
            (gender, telegram_id)
        )
        await db.commit()

async def update_user_preferred_name(telegram_id: int, name: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET preferred_name = ? WHERE telegram_id = ?",
            (name, telegram_id)
        )
        await db.commit()

async def update_user_academic_year(telegram_id: int, year: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET academic_year = ? WHERE telegram_id = ?",
            (year, telegram_id)
        )
        await db.commit()

async def get_user_inbox_layout(telegram_id: int) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT inbox_layout FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return "chat"

async def set_user_inbox_layout(telegram_id: int, layout: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET inbox_layout = ? WHERE telegram_id = ?",
            (layout, telegram_id)
        )
        await db.commit()

async def get_user_settings_layout(telegram_id: int) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT settings_layout FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return "classic"

async def set_user_settings_layout(telegram_id: int, layout: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET settings_layout = ? WHERE telegram_id = ?",
            (layout, telegram_id)
        )
        await db.commit()

async def get_user_favorites_and_difficult_subjects(telegram_id: int) -> tuple[list[str], list[str]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT favorite_subjects, difficult_subjects FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                fav = [s.strip() for s in row[0].split(",") if s.strip()] if row[0] else []
                diff = [s.strip() for s in row[1].split(",") if s.strip()] if row[1] else []
                return fav, diff
            return [], []

async def update_user_favorite_subjects(telegram_id: int, subjects: list[str]) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        subjects_str = ",".join(subjects)
        await db.execute(
            "UPDATE users SET favorite_subjects = ? WHERE telegram_id = ?",
            (subjects_str, telegram_id)
        )
        await db.commit()

async def update_user_difficult_subjects(telegram_id: int, subjects: list[str]) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        subjects_str = ",".join(subjects)
        await db.execute(
            "UPDATE users SET difficult_subjects = ? WHERE telegram_id = ?",
            (subjects_str, telegram_id)
        )
        await db.commit()

async def get_user_contributions_count(telegram_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM question_reports WHERE user_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def delete_user_data(telegram_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await db.execute("DELETE FROM support_tickets WHERE student_id = ?", (telegram_id,))
        await db.commit()

async def get_user_preferred_subject(telegram_id: int) -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute("SELECT preferred_subject FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else None
        except aiosqlite.OperationalError as e:
            if "no such column: preferred_subject" in str(e):
                logger.warning("Column 'preferred_subject' missing in 'users' table. Migrating dynamically...")
                try:
                    await db.execute("ALTER TABLE users ADD COLUMN preferred_subject TEXT DEFAULT NULL;")
                    await db.commit()
                    # Retry query
                    async with db.execute("SELECT preferred_subject FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
                        row = await cursor.fetchone()
                        return row[0] if row and row[0] else None
                except Exception as ex:
                    logger.error(f"Failed to add column preferred_subject: {ex}")
            raise e

async def update_user_preferred_subject(telegram_id: int, subject: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "UPDATE users SET preferred_subject = ? WHERE telegram_id = ?",
                (subject, telegram_id)
            )
            await db.commit()
        except aiosqlite.OperationalError as e:
            if "no such column: preferred_subject" in str(e):
                logger.warning("Column 'preferred_subject' missing in 'users' table on update. Migrating dynamically...")
                try:
                    await db.execute("ALTER TABLE users ADD COLUMN preferred_subject TEXT DEFAULT NULL;")
                    await db.commit()
                    # Retry update
                    await db.execute(
                        "UPDATE users SET preferred_subject = ? WHERE telegram_id = ?",
                        (subject, telegram_id)
                    )
                    await db.commit()
                    return
                except Exception as ex:
                    logger.error(f"Failed to add column preferred_subject on update: {ex}")
            raise e

# --- Course Metadata ---

async def get_available_lessons(subject: str = None) -> list[int]:
    """Retrieve all unique course numbers that have questions in the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if subject:
            query = "SELECT DISTINCT course_number FROM questions WHERE subject = ? AND course_number > 0 ORDER BY course_number"
            params = (subject.lower().strip(),)
        else:
            query = "SELECT DISTINCT course_number FROM questions WHERE course_number > 0 ORDER BY course_number"
            params = ()
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# --- Questions Helpers ---

async def get_questions_for_courses(course_numbers: list[int], limit_per_course: int = 5) -> list[dict]:
    """Retrieve up to limit_per_course questions for each selected course, shuffled."""
    questions = []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        for cn in course_numbers:
            # Shuffle each course's questions individually to guarantee we pull exactly 5
            async with db.execute(
                "SELECT * FROM questions WHERE course_number = ? ORDER BY random() LIMIT ?",
                (cn, limit_per_course)
            ) as cursor:
                rows = await cursor.fetchall()
                questions.extend([dict(r) for r in rows])
    return questions

async def get_question_by_id(question_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

def get_correct_choice_letter(q: dict) -> str:
    """Helper to resolve the correct choice letter ('a', 'b', 'c', 'd') for a question dict."""
    if not q:
        return "a"
    correct_ans_db = q.get("correct_answer", "").strip()
    if not correct_ans_db:
        return "a"
    if correct_ans_db.lower() in ["a", "b", "c", "d"]:
        return correct_ans_db.lower()
    
    # Otherwise, it might be the actual text. Normalize and compare with choices.
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        t = text.strip().lower()
        if t.endswith('.'):
            t = t[:-1].strip()
        # Normalize Arabic characters
        t = t.replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        # Remove diacritics
        for d in ['\u064b', '\u064c', '\u064d', '\u064e', '\u064f', '\u0650', '\u0651', '\u0652']:
            t = t.replace(d, '')
        return t

    correct_norm = normalize_text(correct_ans_db)
    for letter in ["a", "b", "c", "d"]:
        choice_val = q.get(f"choice_{letter}")
        if choice_val and normalize_text(choice_val) == correct_norm:
            return letter
            
    # Fallback to simple containment or exact matches if normalization had issues
    for letter in ["a", "b", "c", "d"]:
        choice_val = q.get(f"choice_{letter}")
        if choice_val and (choice_val.strip() == correct_ans_db.strip()):
            return letter
            
    return "a"  # final fallback

# --- Favorites Helpers ---

async def is_favorite(user_id: int, question_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM user_favorites WHERE user_id = ? AND question_id = ?",
            (user_id, question_id)
        ) as cursor:
            return await cursor.fetchone() is not None

async def add_favorite(user_id: int, question_id: int, subject: str) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO user_favorites (user_id, question_id, subject) VALUES (?, ?, ?)",
                (user_id, question_id, subject)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding favorite: {e}")
        return False

async def remove_favorite(user_id: int, question_id: int) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "DELETE FROM user_favorites WHERE user_id = ? AND question_id = ?",
                (user_id, question_id)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error removing favorite: {e}")
        return False

async def get_user_favorites(user_id: int) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT question_id FROM user_favorites WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# --- Errors Helpers ---

async def add_error(user_id: int, question_id: int, subject: str, wrong_answer: str) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO user_errors (user_id, question_id, subject, wrong_answer) VALUES (?, ?, ?, ?)",
                (user_id, question_id, subject, wrong_answer)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding error: {e}")
        return False

async def remove_error(user_id: int, question_id: int) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "DELETE FROM user_errors WHERE user_id = ? AND question_id = ?",
                (user_id, question_id)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error removing error: {e}")
        return False

async def get_user_errors(user_id: int) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT question_id FROM user_errors WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_user_errors_by_subject_and_course(user_id: int) -> dict:
    """
    Returns a dictionary of error counts grouped by subject and course number.
    Format: {subject: {course_number: [question_ids]}}
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT ue.question_id, q.subject, q.course_number 
            FROM user_errors ue
            JOIN questions q ON ue.question_id = q.id
            WHERE ue.user_id = ?
            ORDER BY q.subject, q.course_number, ue.id DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            
            result = {}
            for row in rows:
                subj = row['subject'].lower().strip()
                cn = row['course_number']
                q_id = row['question_id']
                
                if subj not in result:
                    result[subj] = {}
                if cn not in result[subj]:
                    result[subj][cn] = []
                result[subj][cn].append(q_id)
            return result

# --- Support Tickets Mapping ---

async def register_support_ticket(admin_message_id: int, student_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO support_tickets (admin_message_id, student_id) VALUES (?, ?)",
            (admin_message_id, student_id)
        )
        await db.commit()

async def get_student_by_ticket(admin_message_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT student_id FROM support_tickets WHERE admin_message_id = ?",
            (admin_message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# --- Quiz Logs & Admin Statistics ---

async def log_quiz_answer(user_id: int, question_id: int, is_correct: bool) -> None:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO quiz_logs (user_id, question_id, is_correct) VALUES (?, ?, ?)",
                (user_id, question_id, 1 if is_correct else 0)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error logging quiz answer: {e}")

async def get_admin_stats() -> dict:
    stats = {}
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. Total users who answered at least one question
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM quiz_logs") as cursor:
            row = await cursor.fetchone()
            stats["active_total"] = row[0] if row else 0

        # 2. Total registered users
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            stats["users_total"] = row[0] if row else 0

        # 3. Active users in last 24h
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM quiz_logs WHERE answered_at > datetime('now', '-1 day')"
        ) as cursor:
            row = await cursor.fetchone()
            stats["active_24h"] = row[0] if row else 0

        # 4. Top 5 most-failed questions (by count of incorrect answers)
        async with db.execute("""
            SELECT q.id, q.question, q.subject, q.course_number, COUNT(*) as fail_count
            FROM quiz_logs l
            JOIN questions q ON l.question_id = q.id
            WHERE l.is_correct = 0
            GROUP BY q.id
            ORDER BY fail_count DESC
            LIMIT 5
        """) as cursor:
            rows = await cursor.fetchall()
            stats["most_failed"] = [dict(r) for r in rows]

        # 5. Most and least practiced lessons
        async with db.execute("""
            SELECT q.course_number, COUNT(*) as practice_count
            FROM quiz_logs l
            JOIN questions q ON l.question_id = q.id
            GROUP BY q.course_number
            ORDER BY practice_count DESC
        """) as cursor:
            rows = await cursor.fetchall()
            stats["lessons_practice"] = [dict(r) for r in rows]

        # 6. Most and least practiced subjects
        async with db.execute("""
            SELECT q.subject, COUNT(*) as practice_count
            FROM quiz_logs l
            JOIN questions q ON l.question_id = q.id
            GROUP BY q.subject
            ORDER BY practice_count DESC
        """) as cursor:
            rows = await cursor.fetchall()
            stats["subjects_practice"] = [dict(r) for r in rows]

    return stats

async def get_dashboard_stats() -> dict:
    stats = {}
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. Total users
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            stats["total_students"] = row[0] if row else 0
            
        # 2. Gender distribution
        async with db.execute("SELECT gender, COUNT(*) as count FROM users GROUP BY gender") as cursor:
            rows = await cursor.fetchall()
            stats["gender_distribution"] = {r["gender"] if r["gender"] else "unknown": r["count"] for r in rows}
            
        # 3. New users in last 24h
        async with db.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')") as cursor:
            row = await cursor.fetchone()
            stats["new_users_24h"] = row[0] if row else 0
            
        # Active users in last 24h (from quiz_logs)
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM quiz_logs WHERE answered_at >= datetime('now', '-1 day')") as cursor:
            row = await cursor.fetchone()
            stats["active_users_24h"] = row[0] if row else 0

        # 4. Success rate (overall)
        async with db.execute("SELECT is_correct, COUNT(*) as count FROM quiz_logs GROUP BY is_correct") as cursor:
            rows = await cursor.fetchall()
            correct = sum(r["count"] for r in rows if r["is_correct"] == 1)
            wrong = sum(r["count"] for r in rows if r["is_correct"] == 0)
            total = correct + wrong
            stats["success_rate"] = {"correct": correct, "wrong": wrong, "total": total}

        # 5. Top 5 active students (by number of answers)
        async with db.execute("""
            SELECT u.telegram_id, u.first_name, u.username, COUNT(l.id) as answer_count
            FROM users u
            JOIN quiz_logs l ON u.telegram_id = l.user_id
            GROUP BY u.telegram_id
            ORDER BY answer_count DESC
            LIMIT 5
        """) as cursor:
            rows = await cursor.fetchall()
            stats["top_students"] = [dict(r) for r in rows]

    return stats

async def get_all_user_ids(academic_year: int = None) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        query = "SELECT telegram_id FROM users"
        params = []
        if academic_year is not None:
            query += " WHERE academic_year = ?"
            params.append(academic_year)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_questions_by_course(course_number: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM questions WHERE course_number = ? ORDER BY id", (course_number,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_questions_by_subject(subject: str) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM questions WHERE subject = ? ORDER BY course_number, id", (subject.lower().strip(),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_ai_questions() -> list[dict]:
    """Retrieve all questions generated by Gemini (AI) from the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM questions WHERE source = 'generated_by_gemini' ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_questions_for_subjects(subjects: list[str], limit_per_subject: int = 5) -> list[dict]:
    questions = []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        for sub in subjects:
            async with db.execute(
                "SELECT * FROM questions WHERE subject = ? ORDER BY random() LIMIT ?",
                (sub.lower().strip(), limit_per_subject)
            ) as cursor:
                rows = await cursor.fetchall()
                questions.extend([dict(r) for r in rows])
    return questions

async def get_questions_for_subject_courses(subject: str, course_numbers: list[int]) -> list[dict]:
    """Retrieve all questions for a specific subject and list of course numbers."""
    if not course_numbers:
        return []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in course_numbers)
        query = f"SELECT * FROM questions WHERE subject = ? AND course_number IN ({placeholders}) ORDER BY course_number, id"
        params = [subject.lower().strip()] + list(course_numbers)
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_available_sira_years() -> list[int]:
    """Retrieve all unique Hijri years available for Sira questions."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT hijra_year FROM questions WHERE subject = 'sira' AND hijra_year IS NOT NULL ORDER BY hijra_year"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_available_sira_themes() -> list[str]:
    """Retrieve all unique themes available for Sira questions from the database."""
    themes = set()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
                rows = await cursor.fetchall()
                for r in rows:
                    themes.add(r[0].strip())
        except Exception as e:
            logger.error(f"Error fetching from course_chapters in get_available_sira_themes: {e}")
            
        try:
            # Fetch from questions
            async with db.execute("SELECT DISTINCT theme FROM questions WHERE subject = 'sira' AND theme IS NOT NULL AND theme != ''") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    themes.add(r[0].strip())
        except Exception as e:
            logger.error(f"Error fetching from questions in get_available_sira_themes: {e}")
            
    return sorted(list(themes))


async def get_questions_for_sira_years(years: list[int]) -> list[dict]:
    """Retrieve all Sira questions for specified Hijri years."""
    if not years:
        return []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in years)
        query = f"SELECT * FROM questions WHERE subject = 'sira' AND hijra_year IN ({placeholders}) ORDER BY hijra_year, id"
        async with db.execute(query, list(years)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_questions_for_sira_themes(themes: list[str]) -> list[dict]:
    """Retrieve all Sira questions for specified themes."""
    if not themes:
        return []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in themes)
        query = f"SELECT * FROM questions WHERE subject = 'sira' AND theme IN ({placeholders}) ORDER BY theme, id"
        async with db.execute(query, list(themes)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_available_fiqh_themes() -> list[str]:
    """Retrieve all unique themes available for Fiqh questions."""
    return [
        "فرائض الصلاة",
        "شروط الصلاة",
        "سنن الصلاة",
        "مندوبات الصلاة",
        "فرض عين/كفاية",
        "سجود السهو",
        "صلاة الجمعة",
        "شروط الإمام"
    ]

async def get_questions_for_fiqh_themes(themes: list[str]) -> list[dict]:
    """Retrieve all Fiqh questions for specified themes."""
    if not themes:
        return []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in themes)
        query = f"SELECT * FROM questions WHERE subject = 'fiqh' AND theme IN ({placeholders}) ORDER BY theme, id"
        async with db.execute(query, list(themes)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# --- Progress & Mastery ---

async def update_question_progress(user_id: int, question_id: int, is_correct: bool) -> None:
    """Update the mastery status for a user's question. Once correct, stays correct."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get current status
        async with db.execute(
            "SELECT status FROM question_progress WHERE user_id = ? AND question_id = ?",
            (user_id, question_id)
        ) as cursor:
            row = await cursor.fetchone()
        
        current_status = row[0] if row else 'not_done'
        
        # Mastery logic: once 'correct', never downgrade
        if current_status == 'correct':
            # Already mastered, just increment attempts
            new_status = 'correct'
        elif is_correct:
            new_status = 'correct'
        else:
            new_status = 'wrong'
        
        await db.execute("""
            INSERT INTO question_progress (user_id, question_id, status, attempts, last_answered_at)
            VALUES (?, ?, ?, 1, datetime('now'))
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                status = ?,
                attempts = attempts + 1,
                last_answered_at = datetime('now')
        """, (user_id, question_id, new_status, new_status))
        await db.commit()


async def get_progress_dashboard(user_id: int, subject: str = None) -> dict:
    """
    Returns progress stats per subject and course.
    Structure: {subject: {course_number: {'correct': N, 'wrong': N, 'not_done': N, 'total': N, 'official_correct': N, 'official_total': N, 'extra_correct': N, 'extra_total': N}}}
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        query = """
            SELECT 
                q.subject,
                q.course_number,
                SUM(CASE WHEN q.source != 'generated_by_gemini' AND COALESCE(p.status, 'not_done') = 'correct' THEN 1 ELSE 0 END) as official_correct,
                SUM(CASE WHEN q.source != 'generated_by_gemini' THEN 1 ELSE 0 END) as official_total,
                SUM(CASE WHEN q.source = 'generated_by_gemini' AND COALESCE(p.status, 'not_done') = 'correct' THEN 1 ELSE 0 END) as extra_correct,
                SUM(CASE WHEN q.source = 'generated_by_gemini' THEN 1 ELSE 0 END) as extra_total,
                SUM(CASE WHEN COALESCE(p.status, 'not_done') = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN COALESCE(p.status, 'not_done') = 'wrong' THEN 1 ELSE 0 END) as wrong,
                SUM(CASE WHEN COALESCE(p.status, 'not_done') = 'not_done' THEN 1 ELSE 0 END) as not_done,
                COUNT(q.id) as total
            FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
        """
        params = [user_id]
        if subject:
            query += " WHERE q.subject = ?"
            params.append(subject)
        query += " GROUP BY q.subject, q.course_number ORDER BY q.subject, q.course_number"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            
        dashboard = {}
        for row in rows:
            subj = row['subject']
            cn = row['course_number']
            if subj not in dashboard:
                dashboard[subj] = {}
            dashboard[subj][cn] = {
                'correct': row['correct'] or 0,
                'wrong': row['wrong'] or 0,
                'not_done': row['not_done'] or 0,
                'total': row['total'] or 0,
                'official_correct': row['official_correct'] or 0,
                'official_total': row['official_total'] or 0,
                'extra_correct': row['extra_correct'] or 0,
                'extra_total': row['extra_total'] or 0
            }
        return dashboard


async def get_not_done_questions(user_id: int, subject: str, course_numbers: list[int] = None) -> list[dict]:
    """Get questions the user hasn't answered yet (or got wrong), for 'continue from where you left off'."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # First try: questions not yet done
        query = """
            SELECT q.* FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
            WHERE q.subject = ?
            AND (p.status IS NULL OR p.status = 'not_done')
        """
        params = [user_id, subject]
        
        if course_numbers:
            placeholders = ",".join("?" for _ in course_numbers)
            query += f" AND q.course_number IN ({placeholders})"
            params.extend(course_numbers)
        
        query += " ORDER BY q.course_number, q.id"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            result = [dict(r) for r in rows]
        
        # If nothing left undone, get wrong ones
        if not result:
            query2 = """
                SELECT q.* FROM questions q
                JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
                WHERE q.subject = ? AND p.status = 'wrong'
            """
            params2 = [user_id, subject]
            if course_numbers:
                placeholders = ",".join("?" for _ in course_numbers)
                query2 += f" AND q.course_number IN ({placeholders})"
                params2.extend(course_numbers)
            query2 += " ORDER BY q.course_number, q.id"
            
            async with db.execute(query2, params2) as cursor:
                rows = await cursor.fetchall()
                result = [dict(r) for r in rows]
        
        return result


async def get_user_overall_stats(user_id: int) -> dict:
    """Get overall stats for a user across all subjects."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT 
                COUNT(*) as total_questions,
                SUM(CASE WHEN p.status = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN p.status = 'wrong' THEN 1 ELSE 0 END) as wrong,
                SUM(CASE WHEN p.status IS NULL OR p.status = 'not_done' THEN 1 ELSE 0 END) as not_done
            FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return {
                'total': row[0] or 0,
                'correct': row[1] or 0,
                'wrong': row[2] or 0,
                'not_done': row[3] or 0
            }


async def get_all_subjects_status_emojis(user_id: int) -> dict:
    """Calculate and return status emojis for each subject for the user using SQL aggregates."""
    subjects = ["fiqh", "sira", "nahw", "aqeeda"]
    emojis = {subj: "💤" for subj in subjects}
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT 
                q.subject,
                COUNT(q.id) as total,
                SUM(CASE WHEN COALESCE(p.status, 'not_done') = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN COALESCE(p.status, 'not_done') = 'wrong' THEN 1 ELSE 0 END) as wrong
            FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
            GROUP BY q.subject
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                subj = row[0].lower().strip()
                if subj not in emojis:
                    continue
                total = row[1]
                correct = row[2]
                wrong = row[3]
                
                if total == 0 or (correct == 0 and wrong == 0):
                    emojis[subj] = "💤"
                elif wrong > 0:
                    emojis[subj] = "⚠️"
                elif correct == total:
                    emojis[subj] = "✅"
                else:
                    emojis[subj] = "🔄"
    return emojis


async def get_remaining_questions_count_per_subject(user_id: int) -> dict:
    """Calculate and return the count of remaining (not_done + wrong) questions for each subject using SQL aggregation."""
    subjects = ["fiqh", "sira", "nahw", "aqeeda"]
    counts = {subj: 0 for subj in subjects}
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT q.subject, COUNT(q.id) as remaining
            FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
            WHERE COALESCE(p.status, 'not_done') != 'correct'
            GROUP BY q.subject
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                subj = row[0].lower().strip()
                if subj in counts:
                    counts[subj] = row[1]
    return counts


# --- Question Reports Helpers ---

async def add_question_report(user_id: int, username: str, first_name: str, q_id: int, r_type: str, notes: str, urgency: str = "Moyen", media_file_id: str = None, media_type: str = None, category: str = None) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Fetch student's current academic_year and gender if available
        gender = 'indetermine'
        academic_year = None
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT academic_year, gender FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                academic_year = row['academic_year']
                gender = row['gender'] or 'indetermine'
        
        ticket_category = category if category else r_type
        
        cursor = await db.execute("""
            INSERT INTO question_reports (user_id, username, first_name, question_id, report_type, notes, urgency, status, media_file_id, media_type, category, academic_year, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (user_id, username or "", first_name or "", q_id, r_type, notes, urgency, media_file_id, media_type, ticket_category, academic_year, gender))
        await db.commit()
        return cursor.lastrowid


async def add_broadcast_report(user_id: int, content: str) -> int:
    """Insert a broadcast message as a report in the student inbox so they see it as unread."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO question_reports (user_id, username, first_name, question_id, report_type, notes, admin_reply, status, student_read)
            VALUES (?, '', 'القسم', 0, 'إشعار عام', ?, 'رسالة من الإدارة العامة 📢', 'resolved', 0)
        """, (user_id, content))
        await db.commit()
        return cursor.lastrowid

async def get_user_reported_question_ids(user_id: int) -> set:
    """Retrieve all question IDs that have been reported by a specific user and are still pending."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT question_id FROM question_reports WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

async def update_question_report_status(report_id: int, status: str, admin_reply: str = "") -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE question_reports 
            SET status = ?, admin_reply = ?, reviewed_at = datetime('now'), student_read = 0
            WHERE id = ?
        """, (status, admin_reply, report_id))
        await db.commit()

async def add_ticket_chat_message(ticket_id: int, sender: str, sender_name: str, message: str, media_file_id: str = None, media_type: str = None) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO ticket_chat_messages (ticket_id, sender, sender_name, message, media_file_id, media_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, sender, sender_name or "", message, media_file_id, media_type))
        await db.commit()
        return cursor.lastrowid

async def get_ticket_chat_messages(ticket_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # First check if there are any chat messages in ticket_chat_messages table
        async with db.execute("SELECT * FROM ticket_chat_messages WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                return [dict(r) for r in rows]
        
        # If no chat messages are found, let's look up the ticket itself to construct the first chat entry (backward compatibility)
        async with db.execute("SELECT notes, admin_reply, created_at, media_file_id, media_type, first_name FROM question_reports WHERE id = ?", (ticket_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return []
                
            messages = []
            if row["notes"]:
                messages.append({
                    "id": 1,
                    "ticket_id": ticket_id,
                    "sender": "student",
                    "sender_name": row["first_name"] or "Student",
                    "message": row["notes"],
                    "media_file_id": row["media_file_id"] or None,
                    "media_type": row["media_type"] or None,
                    "created_at": row["created_at"]
                })
            if row["admin_reply"]:
                messages.append({
                    "id": 2,
                    "ticket_id": ticket_id,
                    "sender": "admin",
                    "sender_name": "Management",
                    "message": row["admin_reply"],
                    "media_file_id": None,
                    "media_type": None,
                    "created_at": row["created_at"] # use same timestamp or empty
                })
            return messages

async def claim_question_report(report_id: int, admin_name: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE question_reports 
            SET status = 'in_progress', claimed_by = ?, reviewed_at = datetime('now')
            WHERE id = ?
        """, (admin_name, report_id))
        await db.commit()

async def get_question_report_by_id(report_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT qr.*, q.subject, q.course_number, q.question, 
                   q.choice_a, q.choice_b, q.choice_c, q.choice_d, 
                   q.correct_answer, q.explanation
            FROM question_reports qr
            LEFT JOIN questions q ON qr.question_id = q.id
            WHERE qr.id = ?
        """, (report_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_reports(user_id: int) -> list[dict]:
    """Retrieve all reports/tickets submitted by a specific user, sorted by date descending."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT qr.*, q.subject, q.course_number, q.question
            FROM question_reports qr
            LEFT JOIN questions q ON qr.question_id = q.id
            WHERE qr.user_id = ?
            ORDER BY qr.created_at DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_reports_list(status: str = None) -> list[dict]:
    """Retrieve list of all reports (optionally filtered by status), sorted by date descending."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT qr.*, q.subject, q.course_number, q.question
            FROM question_reports qr
            LEFT JOIN questions q ON qr.question_id = q.id
        """
        params = []
        if status:
            if status == "resolved":
                query += " WHERE qr.status IN ('resolved', 'rejected')"
            else:
                query += " WHERE qr.status = ?"
                params.append(status)
        query += " ORDER BY qr.created_at DESC"
        
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_reports_count_by_status(status: str) -> int:
    """Get the total count of reports by status category (pending, in_progress, resolved)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if status == "resolved":
            async with db.execute("SELECT COUNT(*) FROM question_reports WHERE status IN ('resolved', 'rejected')") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        else:
            async with db.execute("SELECT COUNT(*) FROM question_reports WHERE status = ?", (status,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

async def get_pending_reports_count() -> int:
    """Get the total count of pending reports."""
    return await get_reports_count_by_status("pending")

async def get_setting(key: str, default: str = None) -> str:
    """Get a configuration setting from the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return default

async def set_setting(key: str, value: str) -> None:
    """Set or update a configuration setting in the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def update_question_in_db(question_id: int, question: str, choice_a: str, choice_b: str, choice_c: str, choice_d: str, correct_answer: str, theme: str = "", sub_theme: str = "", hijra_year: int = None) -> None:
    """Update a question's content, choices, correct answer, theme, sub_theme, and hijra_year in the database."""
    def clean_val(val):
        if not val or not isinstance(val, str):
            return val
        return val.replace("**", "")

    question = clean_val(question)
    choice_a = clean_val(choice_a)
    choice_b = clean_val(choice_b)
    choice_c = clean_val(choice_c)
    choice_d = clean_val(choice_d)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE questions 
            SET question = ?, choice_a = ?, choice_b = ?, choice_c = ?, choice_d = ?, correct_answer = ?, theme = ?, sub_theme = ?, hijra_year = ?
            WHERE id = ?
        """, (question, choice_a, choice_b, choice_c, choice_d, correct_answer, theme, sub_theme, hijra_year, question_id))
        await db.commit()

async def reopen_question_report(report_id: int, new_notes: str) -> None:
    """Reopen a question report by resetting status to pending, updating notes, and clearing admin reply."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE question_reports 
            SET status = 'pending', notes = ?, admin_reply = '', reviewed_at = '', student_read = 1
            WHERE id = ?
        """, (new_notes, report_id))
        await db.commit()

async def get_unread_reports_count(user_id: int) -> int:
    """Get the count of unread (student_read = 0) reports for a user."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM question_reports WHERE user_id = ? AND student_read = 0",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def mark_report_as_read(report_id: int) -> None:
    """Mark a report as read by the student."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE question_reports SET student_read = 1 WHERE id = ?",
            (report_id,)
        )
        await db.commit()


async def get_admin_role(telegram_id: int) -> str | None:
    """
    Get the admin role for a telegram_id.
    Attempts to read from the main bot database if it exists,
    then the local database, and otherwise falls back to TELEGRAM_ADMIN_IDS.
    """
    from config import MAIN_DATABASE_PATH, TELEGRAM_ADMIN_IDS
    import os
    
    # 1. Try to query the main database
    if MAIN_DATABASE_PATH and os.path.exists(MAIN_DATABASE_PATH):
        try:
            async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT role FROM admins WHERE telegram_id = ?", (telegram_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row["role"]
        except Exception as e:
            logger.error(f"Error reading admin role from main DB: {e}")
            
    # 2. Try to query the local database
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT role FROM admins WHERE telegram_id = ?", (telegram_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row["role"]
    except Exception as e:
        logger.error(f"Error reading admin role from local DB: {e}")
            
    # 3. Fallback to local config
    if telegram_id in TELEGRAM_ADMIN_IDS:
        return "super_admin"
        
    return None


async def add_admin_to_db(telegram_id: int, role: str, username: str = "", first_name: str = "", added_by: int = None) -> bool:
    """
    Insert a new admin into both the main database and local database.
    """
    from config import MAIN_DATABASE_PATH
    import os
    success = False
    
    # 1. Save to main DB if exists
    if MAIN_DATABASE_PATH and os.path.exists(MAIN_DATABASE_PATH):
        try:
            async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO admins (telegram_id, role, username, first_name, added_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (telegram_id, role, username or "", first_name or "", added_by))
                await db.commit()
                success = True
        except Exception as e:
            logger.error(f"Error adding admin to main DB: {e}")
            
    # 2. Save to local DB
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO admins (telegram_id, role, username, first_name, added_by)
                VALUES (?, ?, ?, ?, ?)
            """, (telegram_id, role, username or "", first_name or "", added_by))
            await db.commit()
            success = True
    except Exception as e:
        logger.error(f"Error adding admin to local DB: {e}")
        
    return success


async def remove_admin_from_db(telegram_id: int) -> bool:
    """
    Delete an admin from both the main database and local database.
    """
    from config import MAIN_DATABASE_PATH
    import os
    success = False
    
    # 1. Delete from main DB if exists
    if MAIN_DATABASE_PATH and os.path.exists(MAIN_DATABASE_PATH):
        try:
            async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
                await db.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
                await db.commit()
                success = True
        except Exception as e:
            logger.error(f"Error removing admin from main DB: {e}")
            
    # 2. Delete from local DB
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
            await db.commit()
            success = True
    except Exception as e:
        logger.error(f"Error removing admin from local DB: {e}")
        
    return success


async def get_all_admins() -> list[dict]:
    """
    Retrieve list of admins from the database.
    Checks main database first, then falls back to local database.
    """
    from config import MAIN_DATABASE_PATH
    import os
    
    # 1. Try main DB
    if MAIN_DATABASE_PATH and os.path.exists(MAIN_DATABASE_PATH):
        try:
            async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM admins ORDER BY added_at DESC") as cursor:
                    rows = await cursor.fetchall()
                    if rows:
                        return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching admins from main DB: {e}")
            
    # 2. Try local DB
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM admins ORDER BY added_at DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching admins from local DB: {e}")
        return []


async def get_matrix_counts() -> dict[str, dict[str, int]]:
    """
    Get the counts of tickets grouped by category and status.
    Categories: tech, question_error, expl_error, course_question, suggestion
    Statuses: pending, in_progress, resolved
    """
    categories = ["tech", "question_error", "expl_error", "course_question", "suggestion"]
    statuses = ["pending", "in_progress", "resolved"]
    counts = {cat: {stat: 0 for stat in statuses} for cat in categories}
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT report_type, status, COUNT(*) 
            FROM question_reports 
            GROUP BY report_type, status
        """) as cursor:
            rows = await cursor.fetchall()
            for r_type, status, count in rows:
                # Map r_type to category
                cat = "tech"
                if r_type in ["question_error", "content_error"]:
                    cat = "question_error"
                elif r_type == "expl_error":
                    cat = "expl_error"
                elif r_type == "course_question":
                    cat = "course_question"
                elif r_type in ["suggestion", "improvement", "review"]:
                    cat = "suggestion"
                elif r_type == "tech":
                    cat = "tech"
                else:
                    cat = "tech"
                    
                # Map status to dashboard columns
                stat = "pending"
                if status == "in_progress":
                    stat = "in_progress"
                elif status in ["resolved", "rejected"]:
                    stat = "resolved"
                else:
                    stat = "pending"
                    
                counts[cat][stat] += count
    return counts


async def get_reports_by_category_and_status(category: str, status: str) -> list[dict]:
    """
    Retrieve list of reports matching a specific category and status,
    sorted by date descending.
    """
    # Map status
    if status == "resolved":
        status_clause = "qr.status IN ('resolved', 'rejected')"
        status_params = []
    else:
        status_clause = "qr.status = ?"
        status_params = [status]

    if category == "tech":
        # Any type not belonging to the other categories
        other_types = ["question_error", "content_error", "expl_error", "course_question", "suggestion", "improvement", "review"]
        placeholders = ",".join(["?"] * len(other_types))
        query = f"""
            SELECT qr.*, q.subject, q.course_number, q.question
            FROM question_reports qr
            LEFT JOIN questions q ON qr.question_id = q.id
            WHERE {status_clause} AND (qr.report_type IS NULL OR qr.report_type NOT IN ({placeholders}))
            ORDER BY qr.created_at DESC
        """
        params = status_params + other_types
    else:
        # Map specific category to report_type list
        r_types = []
        if category == "question_error":
            r_types = ["question_error", "content_error"]
        elif category == "expl_error":
            r_types = ["expl_error"]
        elif category == "course_question":
            r_types = ["course_question"]
        elif category == "suggestion":
            r_types = ["suggestion", "improvement", "review"]
            
        r_type_placeholders = ",".join(["?"] * len(r_types))
        query = f"""
            SELECT qr.*, q.subject, q.course_number, q.question
            FROM question_reports qr
            LEFT JOIN questions q ON qr.question_id = q.id
            WHERE {status_clause} AND qr.report_type IN ({r_type_placeholders})
            ORDER BY qr.created_at DESC
        """
        params = status_params + r_types
        
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_admin_display_preference(telegram_id: int) -> str:
    """
    Get the display preference ('grid' or 'category_first') for an admin.
    """
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT display_preference FROM admins WHERE telegram_id = ?", (telegram_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row["display_preference"]:
                    return row["display_preference"]
    except Exception as e:
        logger.error(f"Error reading admin display preference: {e}")
    return "grid"  # Default


async def set_admin_display_preference(telegram_id: int, preference: str) -> bool:
    """
    Set the display preference ('grid' or 'category_first') for an admin.
    """
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Ensure the admin has a row in the database, defaulting role to 'super_admin'
            await db.execute(
                "INSERT OR IGNORE INTO admins (telegram_id, role, display_preference) VALUES (?, 'super_admin', ?)",
                (telegram_id, preference)
            )
            # Update the preference
            await db.execute("UPDATE admins SET display_preference = ? WHERE telegram_id = ?", (preference, telegram_id))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error setting admin display preference: {e}")
        return False


async def get_hidden_items(category: str) -> list:
    """Get a list of hidden items for a given category (e.g., 'buttons', 'lessons', 'subjects', 'themes')."""
    key = f"hidden_{category}"
    val = await get_setting(key, "")
    if not val:
        return []
    return [item.strip() for item in val.split(",") if item.strip()]


async def set_item_hidden(category: str, item_id: str, is_hidden: bool) -> bool:
    """Add or remove an item from the hidden list of a category."""
    try:
        current = await get_hidden_items(category)
        item_str = str(item_id).strip()
        if is_hidden:
            if item_str not in current:
                current.append(item_str)
        else:
            if item_str in current:
                current.remove(item_str)
        new_val = ",".join(current)
        await set_setting(f"hidden_{category}", new_val)
        return True
    except Exception as e:
        logger.error(f"Error setting hidden item for category {category}: {e}")
        return False


async def is_user_banned(telegram_id: int) -> bool:
    """Check if a user is currently banned."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return bool(row[0])
            return False

async def set_user_ban_status(telegram_id: int, is_banned: bool) -> None:
    """Ban or unban a user by updating their is_banned column."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = ? WHERE telegram_id = ?",
            (1 if is_banned else 0, telegram_id)
        )
        await db.commit()

async def get_all_users() -> list[dict]:
    """Retrieve all users registered in the database, ordered by creation date descending."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def add_question_to_db(q_data: dict) -> int:
    """Insert a new question into the questions table and return its generated ID."""
    def clean_val(val, is_expl=False):
        if not val or not isinstance(val, str):
            return val
        if is_expl:
            import re
            val = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", val)
            return val.replace("**", "")
        return val.replace("**", "")

    question_clean = clean_val(q_data.get("question"))
    choice_a_clean = clean_val(q_data.get("choice_a"))
    choice_b_clean = clean_val(q_data.get("choice_b"))
    choice_c_clean = clean_val(q_data.get("choice_c"))
    choice_d_clean = clean_val(q_data.get("choice_d"))
    explanation_clean = clean_val(q_data.get("explanation"), is_expl=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get maximum existing question ID to generate the next ID
        async with db.execute("SELECT MAX(id) FROM questions") as cursor:
            row = await cursor.fetchone()
            next_id = (row[0] + 1) if (row and row[0] is not None) else 1
            
        await db.execute(
            """
            INSERT INTO questions (
                id, subject, course_number, course_name, question, 
                choice_a, choice_b, choice_c, choice_d, correct_answer, 
                explanation, source, created_at, hijra_year, theme, sub_theme
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
            """,
            (
                next_id,
                q_data.get("subject"),
                q_data.get("course_number"),
                q_data.get("course_name", ""),
                question_clean,
                choice_a_clean,
                choice_b_clean,
                choice_c_clean,
                choice_d_clean,
                q_data.get("correct_answer"),
                explanation_clean,
                q_data.get("source", "added_by_admin"),
                q_data.get("hijra_year"),
                q_data.get("theme", ""),
                q_data.get("sub_theme", "")
            )
        )
        await db.commit()
        return next_id

async def delete_question_from_db(question_id: int) -> bool:
    """Delete a question by its database ID. Returns True if deleted successfully."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error deleting question {question_id} from DB: {e}")
        return False


async def get_lesson_resources(subject: str, course_number: int) -> dict | None:
    """Retrieve file_ids for mind map and summary PDF for a given subject and course number."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM lesson_resources WHERE subject = ? AND course_number = ?",
            (subject.lower().strip(), course_number)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_lesson_resources(subject: str, course_number: int, resource_type: str, file_id: str) -> None:
    """Save or update resource file_id (resource_type: 'mind_map' or 'summary')."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Ensure record exists
        await db.execute(
            "INSERT OR IGNORE INTO lesson_resources (subject, course_number) VALUES (?, ?)",
            (subject.lower().strip(), course_number)
        )
        # Update correct column
        column = "mind_map_file_id" if resource_type == "mind_map" else "summary_file_id"
        await db.execute(
            f"UPDATE lesson_resources SET {column} = ? WHERE subject = ? AND course_number = ?",
            (file_id, subject.lower().strip(), course_number)
        )
        await db.commit()


async def get_all_lessons_with_resources(subject: str) -> list[dict]:
    """
    Get a list of unique lessons for a subject and check if they have mind map, summary, and transcription pages.
    Returns: list of dicts: [{'course_number': int, 'has_mind_map': bool, 'has_summary': bool, 'has_transcription': bool}]
    """
    # Get list of unique lessons having questions in the database
    unique_lessons = await get_available_lessons(subject)
    
    resources = []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        for lesson in unique_lessons:
            # Check if lesson has transcription pages
            async with db.execute(
                "SELECT COUNT(*) FROM lesson_transcription_pages WHERE subject = ? AND course_number = ?",
                (subject.lower().strip(), lesson)
            ) as count_cursor:
                row_count = await count_cursor.fetchone()
                has_trans = bool(row_count and row_count[0] > 0)

            async with db.execute(
                "SELECT mind_map_file_id, summary_file_id FROM lesson_resources WHERE subject = ? AND course_number = ?",
                (subject.lower().strip(), lesson)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    resources.append({
                        'course_number': lesson,
                        'has_mind_map': bool(row['mind_map_file_id']),
                        'has_summary': bool(row['summary_file_id']),
                        'has_transcription': has_trans
                    })
                else:
                    resources.append({
                        'course_number': lesson,
                        'has_mind_map': False,
                        'has_summary': False,
                        'has_transcription': has_trans
                    })
    return resources


async def add_transcription_page(subject: str, course_number: int, page_number: int, file_id: str) -> None:
    """Insert or replace a specific transcription page for a lesson."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO lesson_transcription_pages (subject, course_number, page_number, file_id)
            VALUES (?, ?, ?, ?)
            """,
            (subject.lower().strip(), course_number, page_number, file_id)
        )
        await db.commit()


async def get_transcription_pages(subject: str, course_number: int) -> list[dict]:
    """Retrieve all transcription pages for a lesson, ordered by page_number ascending."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM lesson_transcription_pages
            WHERE subject = ? AND course_number = ?
            ORDER BY page_number ASC
            """,
            (subject.lower().strip(), course_number)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_transcription_page(subject: str, course_number: int, page_number: int) -> None:
    """Delete a specific transcription page for a lesson."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            DELETE FROM lesson_transcription_pages
            WHERE subject = ? AND course_number = ? AND page_number = ?
            """,
            (subject.lower().strip(), course_number, page_number)
        )
        await db.commit()


async def delete_all_transcription_pages(subject: str, course_number: int) -> None:
    """Delete all transcription pages for a lesson."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            DELETE FROM lesson_transcription_pages
            WHERE subject = ? AND course_number = ?
            """,
            (subject.lower().strip(), course_number)
        )
        await db.commit()


async def get_mind_map_pages(subject: str, course_number: int) -> list[dict]:

    """Retrieve all mind map pages for a lesson, ordered by page_number ascending."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM lesson_mind_map_pages
            WHERE subject = ? AND course_number = ?
            ORDER BY page_number ASC
            """,
            (subject.lower().strip(), course_number)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def add_mind_map_page(subject: str, course_number: int, page_number: int, file_id: str) -> None:
    """Insert or replace a specific mind map page for a lesson."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO lesson_mind_map_pages (subject, course_number, page_number, file_id)
            VALUES (?, ?, ?, ?)
            """,
            (subject.lower().strip(), course_number, page_number, file_id)
        )
        await db.commit()


async def delete_all_mind_map_pages(subject: str, course_number: int) -> None:
    """Delete all mind map pages for a lesson (used before replacing)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            DELETE FROM lesson_mind_map_pages
            WHERE subject = ? AND course_number = ?
            """,
            (subject.lower().strip(), course_number)
        )
        await db.commit()


# --- Course Chapters & Study Path Helpers ---

async def add_course_chapter(subject: str, course_number: int, chapter_index: int, title: str, content: str, youtube_link: str = None, timestamp_seconds: int = None, vocabulary_spoilers: str = None, poetry_verses: str = None) -> int:
    """Add or replace a chapter for active study in a course and return the row ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR REPLACE INTO course_chapters (subject, course_number, chapter_index, title, content, youtube_link, timestamp_seconds, vocabulary_spoilers, poetry_verses)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (subject.lower().strip(), course_number, chapter_index, title, content, youtube_link, timestamp_seconds, vocabulary_spoilers, poetry_verses)
        )
        await db.commit()
        return cursor.lastrowid


async def add_course_chapter_question(chapter_id: int, question: str, choice_a: str, choice_b: str, choice_c: str = None, choice_d: str = None, correct_answer: str = "a", explanation: str = None, hint: str = None) -> int:
    """Add or replace the verification question associated with a chapter."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR REPLACE INTO course_chapter_questions (chapter_id, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, hint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chapter_id, question, choice_a, choice_b, choice_c, choice_d, correct_answer.lower(), explanation, hint)
        )
        await db.commit()
        return cursor.lastrowid


async def get_course_chapters(subject: str, course_number: int) -> list[dict]:
    """Retrieve all chapters for a lesson ordered by their index."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM course_chapters 
            WHERE subject = ? AND course_number = ?
            ORDER BY chapter_index ASC
            """,
            (subject.lower().strip(), course_number)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_course_chapter_question(chapter_id: int) -> dict:
    """Retrieve the QCM question linked to a chapter."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM course_chapter_questions WHERE chapter_id = ?",
            (chapter_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def search_transcripts_local(keyword: str) -> list[dict]:
    import os
    from config import MAIN_DATABASE_PATH
    if not os.path.exists(MAIN_DATABASE_PATH):
        return []
    
    keyword_clean = keyword.strip()
    if not keyword_clean:
        return []
        
    words = keyword_clean.split()
    conditions = []
    params = []
    for w in words:
        conditions.append("content LIKE ?")
        params.append("%" + w + "%")
        
    sql = "SELECT subject, course_number, course_name, timestamp, seconds, content FROM transcript_segments WHERE " + " AND ".join(conditions) + " ORDER BY seconds ASC LIMIT 15"
    
    async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def search_chapters_fts(query: str, subject_filter: str = None) -> list[dict]:
    """
    Search chapters using SQLite FTS5 plein-texte search.
    Returns matched chapters with highlighted text snippets.
    """
    clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
    if not clean_query:
        return []

    # Format query for FTS5 (e.g. search for words)
    # E.g. "النية" -> "النية"
    # To support prefix matching: we can split by spaces and search
    words = [w for w in clean_query.split() if w]
    if not words:
        return []
    
    fts_query = " AND ".join(words)

    sql = """
        SELECT 
            f.chapter_id,
            f.subject,
            f.course_number,
            f.chapter_index,
            f.title,
            c.youtube_link,
            c.timestamp_seconds,
            snippet(course_chapters_fts, 5, '<b>', '</b>', '...', 15) as snippet
        FROM course_chapters_fts f
        JOIN course_chapters c ON c.id = f.chapter_id
        WHERE course_chapters_fts MATCH ?
    """
    params = [fts_query]

    if subject_filter:
        sql += " AND f.subject = ?"
        params.append(subject_filter.lower().strip())

    sql += " ORDER BY rank LIMIT 15"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# --- Question Proposals Helpers ---

async def get_lesson_youtube_link(subject: str, course_number: int) -> str:
    """Retrieve the first available youtube link for a given lesson from course_chapters."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT youtube_link FROM course_chapters WHERE subject = ? AND course_number = ? AND youtube_link IS NOT NULL LIMIT 1",
            (subject, course_number)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def create_question_proposal(user_id: int, username: str, first_name: str, subject: str, course_number: int, question: str, choice_a: str, choice_b: str, choice_c: str = None, choice_d: str = None, correct_answer: str = "a", explanation: str = None) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO question_proposals (user_id, username, first_name, subject, course_number, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username or "", first_name or "", subject.lower().strip(), course_number, question, choice_a, choice_b, choice_c, choice_d, correct_answer.lower(), explanation)
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_question_proposals(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM question_proposals WHERE user_id = ? ORDER BY id DESC", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_pending_proposals() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM question_proposals WHERE status = 'pending' ORDER BY id ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_proposal_by_id(proposal_id: int) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM question_proposals WHERE id = ?", (proposal_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def accept_proposal(proposal_id: int, custom_q: str = None, custom_a: str = None, custom_b: str = None, custom_c: str = None, custom_d: str = None, custom_correct: str = None, custom_expl: str = None) -> bool:
    prop = await get_proposal_by_id(proposal_id)
    if not prop:
        return False
        
    q_text = custom_q or prop["question"]
    a_text = custom_a or prop["choice_a"]
    b_text = custom_b or prop["choice_b"]
    c_text = custom_c if custom_c is not None else prop["choice_c"]
    d_text = custom_d if custom_d is not None else prop["choice_d"]
    correct = custom_correct or prop["correct_answer"]
    expl = custom_expl or prop["explanation"]
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 1. Insert into main questions table (with source='student_proposal')
        # Generate new question ID or let sqlite autoincrement (but wait, questions has PRIMARY KEY on id, but it's not AUTOINCREMENT. We should select MAX(id) + 1 to avoid conflicts)
        async with db.execute("SELECT COALESCE(MAX(id), 1000) + 1 FROM questions") as cur:
            new_id = (await cur.fetchone())[0]
            if new_id < 20000:
                new_id = 20000 + new_id  # reserve higher ID range for student proposals
                
        await db.execute(
            """
            INSERT INTO questions (id, subject, course_number, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'student_proposal')
            """,
            (new_id, prop["subject"], prop["course_number"], q_text, a_text, b_text, c_text, d_text, correct, expl)
        )
        # 2. Update status of proposal
        await db.execute(
            "UPDATE question_proposals SET status = 'accepted' WHERE id = ?",
            (proposal_id,)
        )
        await db.commit()
        return True


async def reject_proposal(proposal_id: int, admin_reply: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE question_proposals SET status = 'rejected', admin_reply = ? WHERE id = ?",
            (admin_reply, proposal_id)
        )
        await db.commit()
        return True


async def get_newly_added_lessons() -> list[dict]:
    """Retrieve courses that have questions added or generated in the last 7 days."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Since created_at might be null or text, we can also look at questions with higher IDs,
        # or compare created_at with date('-7 days'). Let's do a query comparing created_at if formatted.
        # Otherwise fallback to showing recently modified lessons.
        async with db.execute(
            """
            SELECT DISTINCT subject, course_number 
            FROM questions 
            WHERE created_at >= date('now', '-7 days')
               OR (source = 'generated_by_gemini' AND id IN (SELECT question_id FROM quiz_logs ORDER BY id DESC LIMIT 50))
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def search_similar_triage(query: str, use_ai: bool = False) -> list[dict]:
    """Search for similar resolved tickets using local keyword matching by default, with Gemini AI optional."""
    query = (query or "").strip()
    if not query:
        return []

    from config import DATABASE_PATH, GEMINI_API_KEY
    import google.generativeai as genai
    import json
    import logging
    logger = logging.getLogger(__name__)

    # Liste des mots vides (stop-words) en français et en arabe
    stop_words = {
        'le', 'la', 'les', 'de', 'des', 'un', 'une', 'du', 'en', 'et', 'ou', 'que', 'qui', 'dans', 'pour', 'par', 'ce', 'ces',
        'في', 'من', 'على', 'ان', 'أن', 'هو', 'هي', 'هل', 'ما', 'لا', 'يا', 'هذا', 'هذه', 'كيف', 'مع', 'أو', 'و', 'ثم', 'إلى', 'عن'
    }
    
    def get_clean_keywords(text):
        if not text:
            return set()
        clean = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
        return {w for w in clean.split() if w not in stop_words and len(w) > 1}

    try:
        # 1. Fetch resolved tickets
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("""
                SELECT id, report_type, notes, admin_reply 
                FROM question_reports 
                WHERE status = 'resolved' AND admin_reply IS NOT NULL AND admin_reply != ''
            """) as cur:
                rows = await cur.fetchall()

        if not rows:
            return []

        # 2. Local preprocessing and overlap calculation
        query_words = get_clean_keywords(query)
        if not query_words:
            # Fallback to simple split if query is all stop-words or punctuation
            query_words = set(query.lower().split())

        candidates = []
        for r in rows:
            notes_words = get_clean_keywords(r["notes"])
            if not notes_words:
                notes_words = set((r["notes"] or "").lower().split())
                
            overlap_words = query_words.intersection(notes_words)
            overlap = len(overlap_words)
            
            # Calcul du score local basé sur la taille des mots-clés de la requête
            score = overlap / max(len(query_words), 1)
            candidates.append({
                "id": r["id"],
                "notes": r["notes"],
                "admin_reply": r["admin_reply"],
                "overlap": overlap,
                "score": score
            })

        # Trier par nombre de mots en commun
        candidates.sort(key=lambda x: x["overlap"], reverse=True)
        top_candidates = [c for c in candidates if c["overlap"] > 0][:15]

        matches = []
        
        # 3. Call Gemini only if use_ai is explicitly requested and GEMINI_API_KEY is defined
        if use_ai and GEMINI_API_KEY and top_candidates:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.5-flash')

                candidates_str = ""
                for idx, c in enumerate(top_candidates):
                    candidates_str += f"Candidate {idx+1} [ID: {c['id']}]:\nQuestion: {c['notes']}\nAnswer: {c['admin_reply']}\n\n"

                prompt = f"""
You are an advanced support assistant for an online Islamic academy.
Your task is to check if the new student query matches any of the past resolved questions, and if the past answer can fully or partially answer the student.

New Student Query:
"{query}"

Past Resolved Candidates:
{candidates_str}

Evaluate semantic similarity. If a past question is a close match, return it.
You MUST respond ONLY with a valid JSON list in this format:
[
  {{"id": ID, "score": CONFIDENCE_SCORE_0_TO_1, "suggestion": "THE_PAST_ANSWER_TEXT"}}
]
Only return candidates with a confidence score of 0.65 or higher. If no candidates match, return an empty list [].
Do not include any markdown format like ```json ... ```, just the raw JSON.
"""
                response = await model.generate_content_async(prompt)
                resp_text = response.text.strip()
                if resp_text.startswith("```"):
                    parts = resp_text.split("```")
                    if len(parts) > 1:
                        resp_text = parts[1]
                    if resp_text.startswith("json"):
                        resp_text = resp_text[4:]
                resp_text = resp_text.strip()

                ai_matches = json.loads(resp_text)
                for m in ai_matches:
                    c_id = m.get("id")
                    score = m.get("score", 0.0)
                    suggestion = m.get("suggestion", "")

                    cand = next((c for c in top_candidates if c["id"] == c_id), None)
                    if cand:
                        matches.append({
                            "id": cand["id"],
                            "question": cand["notes"],
                            "answer": suggestion or cand["admin_reply"],
                            "score": score
                        })
            except Exception as gem_err:
                logger.error(f"Gemini database triage match error: {gem_err}")

        # 4. Fallback or Local Search Mode (when use_ai is False or AI fails)
        if not matches:
            # We return the top 3 best local matches
            for c in top_candidates[:3]:
                # Minimum score of 0.2 (20% keywords overlap) or at least 1 keyword overlap
                if c["score"] >= 0.15 or c["overlap"] >= 1:
                    matches.append({
                        "id": c["id"],
                        "question": c["notes"],
                        "answer": c["admin_reply"],
                        # We project the overlap score to 0-1 range
                        "score": min(0.4 + (0.5 * c["score"]), 0.95)
                    })
        return matches
    except Exception as e:
        logger.error(f"Error in search_similar_triage: {e}")
        return []


async def get_ai_coverage_stats() -> dict:
    """
    Returns a dictionary structured by subject and course number (14-24)
    with count of questions generated by AI (source = 'generated_by_gemini').
    """
    stats = {}
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            """
            SELECT subject, course_number, COUNT(*) 
            FROM questions 
            WHERE source = 'generated_by_gemini' 
            AND course_number BETWEEN 14 AND 24
            GROUP BY subject, course_number
            """
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                subj, cn, cnt = r[0], r[1], r[2]
                if subj not in stats:
                    stats[subj] = {}
                stats[subj][cn] = cnt
    return stats


async def get_transcript_availability() -> dict:
    """Returns a dict of subject -> set of lessons that have transcripts in DB."""
    avail = {}
    async with aiosqlite.connect(MAIN_DATABASE_PATH) as db:
        try:
            async with db.execute(
                "SELECT DISTINCT subject, course_number FROM transcript_segments WHERE course_number BETWEEN 14 AND 24"
            ) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    subj, cn = r[0], r[1]
                    if subj not in avail:
                        avail[subj] = set()
                    avail[subj].add(cn)
        except Exception:
            pass
    return avail


# --- Telegram Groups Helpers ---

async def register_telegram_group(chat_id: str, academic_year: int, group_title: str) -> None:
    """Insert or update a registered Telegram group and its associated academic year."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO telegram_groups (chat_id, academic_year, group_title)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                academic_year = excluded.academic_year,
                group_title = excluded.group_title
        """, (str(chat_id), academic_year, group_title))
        await db.commit()

async def get_telegram_group(chat_id: str) -> dict:
    """Retrieve details of a registered Telegram group by its chat ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM telegram_groups WHERE chat_id = ?", (str(chat_id),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_all_telegram_groups() -> list[dict]:
    """Retrieve all registered Telegram groups."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM telegram_groups") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_telegram_group_by_year(academic_year: int) -> list[dict]:
    """Retrieve all groups associated with a specific academic year."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM telegram_groups WHERE academic_year = ?", (academic_year,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user_correct_question_ids(user_id: int) -> set[int]:
    """Retrieve all question IDs that the user has answered correctly."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT question_id FROM question_progress WHERE user_id = ? AND status = 'correct'",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

async def get_available_sub_themes(subject: str, theme: str) -> list[str]:
    """Retrieve unique sub-themes for a selected theme dynamically from database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        subj_variants = [subject]
        if subject.lower() in ('aqeeda', 'aqida'):
            subj_variants = ['aqeeda', 'aqida']
            
        placeholders = ",".join("?" for _ in subj_variants)
        query = f"SELECT DISTINCT sub_theme FROM questions WHERE subject IN ({placeholders}) AND theme = ? AND sub_theme IS NOT NULL AND sub_theme != '' ORDER BY sub_theme"
        params = subj_variants + [theme]
            
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_available_tajweed_themes() -> list[str]:
    """Retrieve all unique themes available for Tajweed questions."""
    themes = set()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute("SELECT DISTINCT theme FROM questions WHERE subject = 'tajweed' AND theme IS NOT NULL AND theme != ''") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    themes.add(r[0].strip())
        except Exception as e:
            logger.error(f"Error fetching from questions in get_available_tajweed_themes: {e}")
    return sorted(list(themes))

async def get_available_aqeeda_themes() -> list[str]:
    """Retrieve all unique themes available for Aqeeda questions."""
    themes = set()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute("SELECT DISTINCT theme FROM questions WHERE subject IN ('aqeeda', 'aqida') AND theme IS NOT NULL AND theme != ''") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    themes.add(r[0].strip())
        except Exception as e:
            logger.error(f"Error fetching from questions in get_available_aqeeda_themes: {e}")
    return sorted(list(themes))

async def get_available_nahw_themes() -> list[str]:
    """Retrieve all unique themes available for Nahw questions."""
    themes = set()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            async with db.execute("SELECT DISTINCT theme FROM questions WHERE subject = 'nahw' AND theme IS NOT NULL AND theme != ''") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    themes.add(r[0].strip())
        except Exception as e:
            logger.error(f"Error fetching from questions in get_available_nahw_themes: {e}")
    return sorted(list(themes))

async def get_questions_for_themes(subject: str, themes: list[str]) -> list[dict]:
    """Retrieve all questions for specified subject and themes."""
    if not themes:
        return []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in themes)
        
        subj_variants = [subject]
        if subject.lower() in ('aqeeda', 'aqida'):
            subj_variants = ['aqeeda', 'aqida']
            
        subj_placeholders = ",".join("?" for _ in subj_variants)
        query = f"SELECT * FROM questions WHERE subject IN ({subj_placeholders}) AND theme IN ({placeholders}) ORDER BY theme, id"
        async with db.execute(query, subj_variants + list(themes)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_questions_for_tajweed_themes(themes: list[str]) -> list[dict]:
    """Retrieve all Tajweed questions for specified themes."""
    if not themes:
        return []
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in themes)
        query = f"SELECT * FROM questions WHERE subject = 'tajweed' AND theme IN ({placeholders}) ORDER BY theme, id"
        async with db.execute(query, list(themes)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_progress(user_id: int) -> list[dict]:
    """Return all progress rows for a user from student_course_progress."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM student_course_progress "
            "WHERE user_id=? ORDER BY subject, course_number",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_detailed_subject_progress(user_id: int, subject: str):
    """
    Returns:
      lessons_progress: list of dicts with keys (course_number, total, correct, errors, emoji)
      themes_progress: list of dicts with keys (theme, total, correct, errors, emoji)
      years_progress: list of dicts with keys (year, total, correct, errors, emoji) (only for sira)
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # We handle aqeeda/aqida variations if any
        subj_variants = [subject]
        if subject.lower() in ('aqeeda', 'aqida'):
            subj_variants = ['aqeeda', 'aqida']
            
        subj_placeholders = ",".join("?" for _ in subj_variants)
        
        # 1. Fetch all official questions for this subject along with their status for this user
        query_lessons = f"""
            SELECT q.id, q.course_number, COALESCE(p.status, 'not_done') as status
            FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
            WHERE q.subject IN ({subj_placeholders}) AND q.source != 'generated_by_gemini'
            ORDER BY q.course_number, q.id
        """
        async with db.execute(query_lessons, [user_id] + subj_variants) as cursor:
            rows_lessons = await cursor.fetchall()
            
        # Group by lesson
        lessons = {}
        for r in rows_lessons:
            c_num = r['course_number']
            if c_num not in lessons:
                lessons[c_num] = []
            lessons[c_num].append(r)
            
        lessons_progress = []
        for c_num in sorted(lessons.keys()):
            q_list = lessons[c_num]
            total = len(q_list)
            correct = sum(1 for r in q_list if r['status'] == 'correct')
            errors = sum(1 for r in q_list if r['status'] == 'wrong')
            
            # Emoji logic
            if correct == 0 and errors == 0:
                emoji = "⬜"
            elif errors > 0:
                emoji = "🟥"
            elif correct == total and errors == 0:
                emoji = "🟩"
            else:
                emoji = "🟡"
                
            lessons_progress.append({
                'course_number': c_num,
                'total': total,
                'correct': correct,
                'errors': errors,
                'emoji': emoji
            })
            
        # 2. Get allowed themes list matching the bot's themes grid
        allowed_themes = []
        if subject == 'fiqh':
            allowed_themes = await get_available_fiqh_themes()
        elif subject == 'sira':
            allowed_themes = await get_available_sira_themes()
        elif subject == 'tajweed':
            allowed_themes = await get_available_tajweed_themes()
        elif subject in ('aqeeda', 'aqida'):
            allowed_themes = await get_available_aqeeda_themes()
        elif subject == 'nahw':
            allowed_themes = await get_available_nahw_themes()
            
        # Fetch practice questions status for theme grouping
        query_themes = f"""
            SELECT q.id, q.theme, COALESCE(p.status, 'not_done') as status
            FROM questions q
            LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
            WHERE q.subject IN ({subj_placeholders}) AND q.source = 'generated_by_gemini'
        """
        async with db.execute(query_themes, [user_id] + subj_variants) as cursor:
            rows_themes = await cursor.fetchall()
            
        themes_map = {th: [] for th in allowed_themes}
        for r in rows_themes:
            th = r['theme']
            if th and th.strip() in themes_map:
                themes_map[th.strip()].append(r)
                
        themes_progress = []
        for theme in allowed_themes:
            q_list = themes_map[theme]
            total = len(q_list)
            correct = sum(1 for r in q_list if r['status'] == 'correct')
            errors = sum(1 for r in q_list if r['status'] == 'wrong')
            
            # Emoji logic
            if total == 0:
                emoji = "⬜"
            elif correct == 0 and errors == 0:
                emoji = "⬜"
            elif errors > 0:
                emoji = "🟥"
            elif correct == total and errors == 0:
                emoji = "🟩"
            else:
                emoji = "🟡"
                
            themes_progress.append({
                'theme': theme,
                'total': total,
                'correct': correct,
                'errors': errors,
                'emoji': emoji
            })
            
        # 3. Chronological progression by Hijri year (for Sira)
        years_progress = []
        if subject == 'sira':
            query_years = """
                SELECT q.id, q.hijra_year, COALESCE(p.status, 'not_done') as status
                FROM questions q
                LEFT JOIN question_progress p ON q.id = p.question_id AND p.user_id = ?
                WHERE q.subject = 'sira' AND q.hijra_year IS NOT NULL AND q.source != 'generated_by_gemini'
                ORDER BY q.hijra_year, q.id
            """
            async with db.execute(query_years, (user_id,)) as cursor:
                rows_years = await cursor.fetchall()
                
            years_map = {}
            for r in rows_years:
                y = r['hijra_year']
                if y not in years_map:
                    years_map[y] = []
                years_map[y].append(r)
                
            for y in sorted(years_map.keys()):
                q_list = years_map[y]
                total = len(q_list)
                correct = sum(1 for r in q_list if r['status'] == 'correct')
                errors = sum(1 for r in q_list if r['status'] == 'wrong')
                
                # Emoji logic
                if correct == 0 and errors == 0:
                    emoji = "⬜"
                elif errors > 0:
                    emoji = "🟥"
                elif correct == total and errors == 0:
                    emoji = "🟩"
                else:
                    emoji = "🟡"
                    
                years_progress.append({
                    'year': y,
                    'total': total,
                    'correct': correct,
                    'errors': errors,
                    'emoji': emoji
                })
        return lessons_progress, themes_progress, years_progress


async def get_student_course_progress(user_id: int, subject: str, course_number: int) -> dict:
    """Get or create progress record for a student on a specific course."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM student_course_progress WHERE user_id = ? AND subject = ? AND course_number = ?",
            (user_id, subject, course_number)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        
        # If not found, insert default row
        await db.execute(
            "INSERT OR IGNORE INTO student_course_progress (user_id, subject, course_number, resume_done, mindmap_done, flashcards_done, quiz_done) VALUES (?, ?, ?, 0, 0, 0, 0)",
            (user_id, subject, course_number)
        )
        await db.commit()
        
        async with db.execute(
            "SELECT * FROM student_course_progress WHERE user_id = ? AND subject = ? AND course_number = ?",
            (user_id, subject, course_number)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

async def update_student_course_progress(user_id: int, subject: str, course_number: int, **kwargs) -> None:
    """Update specific columns in the progress table."""
    if not kwargs:
        return
    allowed_cols = {"resume_done", "mindmap_done", "flashcards_done", "quiz_done", "fiche_generated", "current_chapter_index"}
    updates = []
    values = []
    for col, val in kwargs.items():
        if col in allowed_cols:
            updates.append(f"{col} = ?")
            values.append(val)
    if not updates:
        return
        
    # Ensure row exists first
    await get_student_course_progress(user_id, subject, course_number)
    
    values.extend([user_id, subject, course_number])
    query = f"UPDATE student_course_progress SET {', '.join(updates)}, last_activity = datetime('now') WHERE user_id = ? AND subject = ? AND course_number = ?"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(query, tuple(values))
        await db.commit()

async def get_questions_by_lesson_for_flashcards(subject: str, course_number: int) -> list[dict]:
    """Retrieve up to 3 questions from a lesson to use as flashcards."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM questions WHERE subject = ? AND course_number = ? AND is_active = 1 LIMIT 3",
            (subject, course_number)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]






async def get_available_themes(subject: str) -> list[dict]:
    """Retrieve all unique Level 2 themes available for a subject."""
    import aiosqlite
    from config import DATABASE_PATH
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT tn.id, tn.title 
            FROM thematic_nodes tn
            JOIN programs p ON tn.program_id = p.id
            WHERE p.alias = ? AND tn.level = 2
            ORDER BY tn.order_index
        """, (subject.lower().strip(),)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_questions_for_theme_nodes(theme_ids: list[int]) -> list[dict]:
    """Retrieve all questions for specified Level 2 themes and their sub-themes."""
    if not theme_ids:
        return []
    import aiosqlite
    from config import DATABASE_PATH
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        placeholders = ",".join("?" for _ in theme_ids)
        
        query_nodes = f"""
            SELECT id FROM thematic_nodes 
            WHERE id IN ({placeholders}) OR parent_id IN ({placeholders})
        """
        params_nodes = list(theme_ids) + list(theme_ids)
        async with db.execute(query_nodes, params_nodes) as cursor:
            nodes_rows = await cursor.fetchall()
            node_ids = [r['id'] for r in nodes_rows]
            
        if not node_ids:
            return []
            
        node_placeholders = ",".join("?" for _ in node_ids)
        query_questions = f"""
            SELECT * FROM questions 
            WHERE thematic_node_id IN ({node_placeholders}) AND is_active = 1
            ORDER BY thematic_node_id, id
        """
        async with db.execute(query_questions, node_ids) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
