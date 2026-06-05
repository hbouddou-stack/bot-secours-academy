import asyncio
import logging
import os
import json
import uuid
import re
import sys
import signal
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

import database as db
from config import TELEGRAM_BOT_TOKEN
from handlers.start import router as start_router
from handlers.quiz import router as quiz_router
from handlers.favorites_errors import router as fav_err_router
from handlers.support import router as support_router
from handlers.admin import router as admin_router
from handlers.revision import router as revision_router

# Configuration du logging double (console et fichier bot.log)
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log_file_path = os.path.join(os.path.dirname(__file__), "bot.log")
logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_file_path, encoding="utf-8")
    ]
)
logger = logging.getLogger("main")

# ─── INSTANCE LOCK (anti-fantôme) ──────────────────────────────────────────────
PID_FILE = os.path.join(os.path.dirname(__file__), ".bot.pid")

def _kill_existing_instance():
    """Tue toute instance précédente du bot avant de démarrer."""
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
        if old_pid == os.getpid():
            return
            
        if sys.platform == "win32":
            # Utilisation de taskkill sous Windows pour forcer l'arrêt de manière fiable
            import subprocess
            logger.warning(f"⚠️  Instance fantôme détectée (PID {old_pid}). Arrêt en cours...")
            subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
        else:
            # Vérifie si le processus tourne encore (Unix)
            os.kill(old_pid, 0)
            # Il tourne encore → on le tue
            logger.warning(f"⚠️  Instance fantôme détectée (PID {old_pid}). Arrêt en cours...")
            os.kill(old_pid, signal.SIGTERM)
            import time; time.sleep(1)
            try:
                os.kill(old_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            logger.info(f"✅ Instance précédente (PID {old_pid}) arrêtée.")
    except (ValueError, ProcessLookupError, OSError):
        pass  # PID invalide, processus déjà mort ou erreur OS (ex: WinError 87 sur Windows)
    except PermissionError:
        logger.warning("Permission refusée pour tuer l'ancienne instance.")

def _write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def _remove_pid():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass

_kill_existing_instance()
_write_pid()
import atexit
atexit.register(_remove_pid)
# ───────────────────────────────────────────────────────────────────────────────

# ─── AIOHTTP WEB SERVER & MINI-APP APIS ──────────────────────────────────────

DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard')

# ─── MIDDLEWARE CORS (pour GitHub Pages → API Serveo) ─────────────────────────
@web.middleware
async def cors_middleware(request, handler):
    """Autorise les requêtes cross-origin depuis GitHub Pages et autres origines."""
    # Répondre immédiatement aux preflight OPTIONS
    if request.method == 'OPTIONS':
        return web.Response(
            status=204,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '86400',
            }
        )
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response
# ──────────────────────────────────────────────────────────────────────────────

async def handle_index(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'index.html'))

async def handle_interactive(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'interactive.html'))

async def handle_admin(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'admin.html'))

async def handle_admin_bot(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'admin-bot.html'))

async def handle_admin_support(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'admin-support.html'))

async def handle_admin_css(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'admin.css'))

async def handle_admin_js(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'admin.js'))

async def handle_admin_late_js(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'admin-late.js'))

async def handle_logo_png(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'logo.png'))

async def handle_support(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'support.html'))

async def handle_search(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'search.html'))

async def handle_transcripts(request):
    transcripts_path = os.path.join(DASHBOARD_DIR, 'transcripts.json')
    if not os.path.exists(transcripts_path):
        transcripts_path = os.path.join(DASHBOARD_DIR, 'transcripts.json.bak')
    return web.FileResponse(transcripts_path)

async def handle_quran(request):
    return web.FileResponse(os.path.join(DASHBOARD_DIR, 'quran_db.json'))

async def check_admin(user_id):
    if not user_id:
        return False
    from config import TELEGRAM_ADMIN_IDS, DATABASE_PATH
    if int(user_id) in TELEGRAM_ADMIN_IDS:
        return True
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            async with db_conn.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (int(user_id),)) as cur:
                row = await cur.fetchone()
                if row:
                    return True
    except Exception as e:
        logger.error(f"Error checking admin status for {user_id}: {e}")
    return False

async def get_admin_role(user_id):
    if not user_id:
        return None
    from config import TELEGRAM_ADMIN_IDS, DATABASE_PATH
    if int(user_id) in TELEGRAM_ADMIN_IDS:
        return "super_admin"
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            async with db_conn.execute("SELECT role FROM admins WHERE telegram_id = ?", (int(user_id),)) as cur:
                row = await cur.fetchone()
                if row:
                    return row[0]
    except Exception as e:
        logger.error(f"Error getting admin role for {user_id}: {e}")
    return None

async def get_admin_info(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not user_id:
            return web.json_response({"success": False, "error": "Missing userId"}, status=400)
            
        from config import DATABASE_PATH, TELEGRAM_ADMIN_IDS
        role = "moderator"
        first_name = "مشرف"
        username = "admin"
        
        if int(user_id) in TELEGRAM_ADMIN_IDS:
            role = "super_admin"
            first_name = "Super Admin"
            
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT role, first_name, username, allowed_subjects, visible_sections FROM admins WHERE telegram_id = ?", (int(user_id),)) as cur:
                row = await cur.fetchone()
                if row:
                    role = row["role"]
                    first_name = row["first_name"] or first_name
                    username = row["username"] or username
                    allowed_subjects_raw = row["allowed_subjects"]
                    visible_sections_raw = row["visible_sections"]
                else:
                    allowed_subjects_raw = None
                    visible_sections_raw = None
            
            # Fallback if first_name/username is still generic/missing/default
            if first_name in ["مشرف", "Super Admin"] or not first_name:
                async with db_conn.execute("SELECT first_name, username FROM users WHERE telegram_id = ?", (int(user_id),)) as cur:
                    r = await cur.fetchone()
                    if r and (r["first_name"] or r["username"]):
                        first_name = r["first_name"] or first_name
                        username = r["username"] or username
                        await db_conn.execute(
                            "UPDATE admins SET first_name = ?, username = ? WHERE telegram_id = ?",
                            (r["first_name"] or "", r["username"] or "", int(user_id))
                        )
            
            if first_name in ["مشرف", "Super Admin"] or not first_name:
                bot = request.app.get('bot')
                if bot:
                    try:
                        chat = await bot.get_chat(chat_id=int(user_id))
                        if chat:
                            first_name = chat.first_name or first_name
                            username = chat.username or username
                            await db_conn.execute(
                                "UPDATE admins SET first_name = ?, username = ? WHERE telegram_id = ?",
                                (chat.first_name or "", chat.username or "", int(user_id))
                            )
                    except Exception as tg_err:
                        logger.warning(f"Could not retrieve admin chat info from Telegram in get_admin_info: {tg_err}")
                    
        import json as _json
        if allowed_subjects_raw:
            try:
                allowed_subjects = _json.loads(allowed_subjects_raw)
            except Exception:
                allowed_subjects = [s.strip() for s in allowed_subjects_raw.split(",") if s.strip()]
        else:
            allowed_subjects = None
        visible_sections = _json.loads(visible_sections_raw) if visible_sections_raw else None

        return web.json_response({
            "success": True, 
            "info": {
                "role": role,
                "firstName": first_name,
                "username": username,
                "allowedSubjects": allowed_subjects,
                "visibleSections": visible_sections
            }
        })
    except Exception as e:
        logger.error(f"Error fetching admin info: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def get_admin_settings(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
            
        from config import DATABASE_PATH
        settings = {}
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT key, value FROM settings") as cur:
                async for row in cur:
                    settings[row["key"]] = row["value"]
                    
        # Provide default values if missing
        from config import ACADEMY_GROUP_ID
        settings.setdefault("academy_group_id", str(ACADEMY_GROUP_ID))
        settings.setdefault("test_group_id", "")
        settings.setdefault("restrict_to_academy_group", "True")
        settings.setdefault("disable_ai_for_students", "False")
        settings.setdefault("ticket_detail_level", "compact")
        settings.setdefault("maintenance_mode", "False")
        settings.setdefault("maintenance_message", "🚧 البوت في وضع الصيانة مؤقتاً. سيعود قريباً بإذن الله.")
        settings.setdefault("quiz_questions_per_session", "10")
        settings.setdefault("quiz_cooldown_minutes", "0")
        settings.setdefault("enable_revision_mode", "False")
        settings.setdefault("quiz_pass_threshold", "60")
        settings.setdefault("bot_welcome_message", "مرحباً بك في بوت أكاديمية النور! 🌟")
        settings.setdefault("notify_on_new_report", "True")
        settings.setdefault("quiz_reminder_enabled", "False")
        
        return web.json_response({"success": True, "settings": settings})
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def purge_old_tickets(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        days = int(data.get('days', 30))
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        
        from config import DATABASE_PATH
        cutoff = f"datetime('now', '-{days} days')"
        deleted_total = 0
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            # Purge resolved/rejected chapter reports
            async with db_conn.execute(f"""
                DELETE FROM chapter_reports
                WHERE status IN ('resolved','rejected')
                AND created_at < {cutoff}
            """) as cur:
                deleted_total += cur.rowcount
            # Purge resolved/rejected question reports
            async with db_conn.execute(f"""
                DELETE FROM question_reports
                WHERE status IN ('resolved','rejected')
                AND created_at < {cutoff}
            """) as cur:
                deleted_total += cur.rowcount
            await db_conn.commit()
        
        return web.json_response({"success": True, "deleted": deleted_total})
    except Exception as e:
        logger.error(f"Error purging tickets: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def update_admin_setting(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        key = data.get('key')
        value = data.get('value')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
            
        if not key:
            return web.json_response({"success": False, "error": "Missing setting key"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("""
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            """, (key, str(value)))
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_admin_students(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if user_id is not None:
            user_id = int(user_id)
            
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        students = []
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            # Fetch all students
            async with db_conn.execute("""
                SELECT telegram_id, username, first_name, gender, preferred_name, created_at 
                FROM users 
                ORDER BY created_at DESC
            """) as cur:
                async for r in cur:
                    student_id = r["telegram_id"]
                    
                    # Fetch counts
                    # 1. Quizzes taken
                    quiz_count = 0
                    async with db_conn.execute("SELECT COUNT(*) FROM quiz_logs WHERE user_id = ?", (student_id,)) as q_cur:
                        quiz_count = (await q_cur.fetchone())[0]
                        
                    # 2. Bug reports
                    report_count = 0
                    async with db_conn.execute("SELECT COUNT(*) FROM question_reports WHERE user_id = ?", (student_id,)) as rep_cur:
                        report_count = (await rep_cur.fetchone())[0]
                    try:
                        async with db_conn.execute("SELECT COUNT(*) FROM chapter_reports WHERE user_id = ?", (student_id,)) as ch_cur:
                            report_count += (await ch_cur.fetchone())[0]
                    except Exception:
                        pass

                    # 3. Question proposals
                    proposal_count = 0
                    async with db_conn.execute("SELECT COUNT(*) FROM question_proposals WHERE user_id = ?", (student_id,)) as prop_cur:
                        proposal_count = (await prop_cur.fetchone())[0]
                        
                    students.append({
                        "telegramId": student_id,
                        "username": r["username"] or "",
                        "firstName": r["first_name"] or "",
                        "gender": r["gender"] or "",
                        "preferredName": r["preferred_name"] or "",
                        "createdAt": r["created_at"],
                        "quizCount": quiz_count,
                        "reportCount": report_count,
                        "proposalCount": proposal_count
                    })
        return web.json_response({"success": True, "students": students})
    except Exception as e:
        logger.error(f"Error loading students: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_admin_student_details(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        student_id = data.get('studentId')
        if user_id is not None:
            user_id = int(user_id)
        if student_id is not None:
            student_id = int(student_id)
            
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        details = {
            "reports": [],
            "proposals": [],
            "quiz_logs": []
        }
        
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            # 1. Fetch both question reports and chapter reports
            reports = []
            
            # Fetch question reports
            try:
                async with db_conn.execute("""
                    SELECT id, question_id, report_type, notes, status, admin_reply, created_at 
                    FROM question_reports 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """, (student_id,)) as cur:
                    async for r in cur:
                        reports.append({
                            "id": r["id"],
                            "type": "question_report",
                            "questionId": r["question_id"],
                            "reportType": r["report_type"],
                            "report": r["notes"] or "",
                            "status": r["status"],
                            "adminReply": r["admin_reply"] or "",
                            "timestamp": r["created_at"]
                        })
            except Exception as e:
                logger.error(f"Error loading question reports in details: {e}")

            # Fetch chapter reports
            try:
                async with db_conn.execute("""
                    SELECT id, subject, lesson_num, chapter_idx, report, status, admin_reply, timestamp 
                    FROM chapter_reports 
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                """, (student_id,)) as cur:
                    async for r in cur:
                        reports.append({
                            "id": r["id"],
                            "type": "chapter_report",
                            "subject": r["subject"],
                            "lessonNum": r["lesson_num"],
                            "chapterIdx": r["chapter_idx"],
                            "report": r["report"] or "",
                            "status": r["status"],
                            "adminReply": r["admin_reply"] or "",
                            "timestamp": r["timestamp"]
                        })
            except Exception as e:
                logger.error(f"Error loading chapter reports in details: {e}")

            # Sort merged reports chronologically (descending)
            def parse_ts(val):
                try:
                    if isinstance(val, (int, float)):
                        return val
                    import datetime
                    dt_str = str(val).split('.')[0].replace('T', ' ')
                    dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                    return dt.timestamp()
                except Exception:
                    return 0

            reports.sort(key=lambda x: parse_ts(x["timestamp"]), reverse=True)
            details["reports"] = reports
                    
            # 2. Fetch proposals
            async with db_conn.execute("""
                SELECT id, subject, course_number, question, status, admin_reply, created_at 
                FROM question_proposals 
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (student_id,)) as cur:
                async for r in cur:
                    details["proposals"].append({
                        "id": r["id"],
                        "subject": r["subject"],
                        "courseNumber": r["course_number"],
                        "question": r["question"],
                        "status": r["status"],
                        "adminReply": r["admin_reply"] or "",
                        "createdAt": r["created_at"]
                    })

            # 3. Fetch quiz logs
            async with db_conn.execute("""
                SELECT ql.id, q.subject, ql.is_correct, ql.answered_at 
                FROM quiz_logs ql 
                JOIN questions q ON ql.question_id = q.id 
                WHERE ql.user_id = ? 
                ORDER BY ql.answered_at DESC 
                LIMIT 50
            """, (student_id,)) as cur:
                async for r in cur:
                    details["quiz_logs"].append({
                        "id": r["id"],
                        "subject": r["subject"],
                        "isCorrect": r["is_correct"],
                        "answeredAt": r["answered_at"]
                    })
                    
        return web.json_response({"success": True, "details": details})
    except Exception as e:
        logger.error(f"Error loading student details: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)




# Student API: Submit a content error report
async def report_chapter(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        username = data.get('username', '')
        first_name = data.get('firstName', '')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        chapter_idx = data.get('chapterIdx')
        report_text = data.get('report')
        
        if not user_id or not subject or lesson_num is None or chapter_idx is None or not report_text:
            return web.json_response({"success": False, "error": "Missing fields"}, status=400)
        
        from datetime import datetime
        from config import DATABASE_PATH
        
        report_id = str(uuid.uuid4())[:8]
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("""
                INSERT INTO chapter_reports (id, user_id, username, first_name, subject, lesson_num, chapter_idx, report, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (report_id, int(user_id), username, first_name, subject, int(lesson_num), int(chapter_idx), report_text, datetime.now().isoformat()))
            await db_conn.commit()
            
        # Send Telegram notification to backup bot admins
        try:
            from config import TELEGRAM_ADMIN_IDS
            admins = TELEGRAM_ADMIN_IDS
            if not admins:
                admins = [2045194295]
                
            subj_ar = subject
            if subject == 'fiqh': subj_ar = 'الفقه'
            elif subject == 'aqeeda': subj_ar = 'العقيدة'
            elif subject == 'sira': subj_ar = 'السيرة'
            elif subject == 'tajweed': subj_ar = 'التجويد'
            elif subject == 'nahw': subj_ar = 'النحو'
            
            chapter_title = f"المحور {chapter_idx + 1}"
            try:
                with open('dashboard/transcripts.json', 'r', encoding='utf-8') as f:
                    lessons = json.load(f)
                    lesson = next((l for l in lessons if l.get('subject') == subject and l.get('lessonNum') == lesson_num), None)
                    if lesson and 'thematic_blocks' in lesson and len(lesson['thematic_blocks']) > chapter_idx:
                        chapter_title = lesson['thematic_blocks'][chapter_idx].get('title', chapter_title)
            except Exception:
                pass
            
            notif_msg = (
                f"🚩 <b>[البوت البديل] بلاغ جديد عن خطأ في المحتوى</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 الطالب: <b>{first_name}</b> (@{username})\n"
                f"📍 المادة: <b>{subj_ar}</b> ← درس {lesson_num} ← <b>{chapter_title}</b>\n\n"
                f"📝 <b>ملاحظة الطالب:</b>\n"
                f"<i>\"{report_text}\"</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 يمكنك مراجعة البلاغ وتعديل المحتوى مباشرة من لوحة التحكم بالملف الشخصي في تطبيق الويب."
            )
            
            bot = request.app['bot']
            for adm in admins:
                try:
                    await bot.send_message(adm, notif_msg, parse_mode="HTML")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error sending telegram admin notification: {e}")
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return web.Response(status=500)

async def get_media(request):
    try:
        file_id = request.query.get('file_id')
        if not file_id:
            return web.json_response({"success": False, "error": "Missing file_id"}, status=400)
            
        bot = request.app.get('bot')
        if not bot:
            return web.json_response({"success": False, "error": "Bot instance not found"}, status=500)
            
        file_info = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_info.file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
            
        return web.Response(body=file_bytes.read(), content_type=mime_type)
    except Exception as e:
        logger.error(f"Error serving media: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: List pending content reports
async def get_admin_reports(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role in ["support_admin", "tech_admin"]:
            return web.json_response({"success": True, "reports": []})
            
        reports = []
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("""
                SELECT cr.id, cr.user_id, cr.username, cr.first_name, cr.subject, cr.lesson_num, 
                       cr.chapter_idx, cr.report, cr.status, cr.admin_reply, cr.timestamp,
                       u.academic_year, cr.source, cr.contact_info, cr.claimed_by, cr.tags, cr.media_file_id, cr.media_type
                FROM chapter_reports cr
                LEFT JOIN users u ON cr.user_id = u.telegram_id
                ORDER BY cr.timestamp DESC
            """) as cur:
                async for r in cur:
                    reports.append({
                        "id": r["id"],
                        "userId": r["user_id"],
                        "username": r["username"],
                        "firstName": r["first_name"],
                        "subject": r["subject"],
                        "lessonNum": r["lesson_num"],
                        "chapterIdx": r["chapter_idx"],
                        "report": r["report"],
                        "status": r["status"],
                        "adminReply": r["admin_reply"] or "",
                        "timestamp": r["timestamp"],
                        "academicYear": r["academic_year"],
                        "source": r["source"] or "telegram",
                        "contactInfo": r["contact_info"] or "",
                        "claimedBy": r["claimed_by"] or "",
                        "tags": json.loads(r["tags"] or "[]"),
                        "mediaFileId": r["media_file_id"] or "",
                        "mediaType": r["media_type"] or ""
                    })
        return web.json_response({"success": True, "reports": reports})
    except Exception as e:
        logger.error(f"Error loading reports: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_admin_dashboard_stats_api(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        import database as db
        stats = await db.get_dashboard_stats()
        return web.json_response({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Error loading dashboard stats: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Resolve a report
async def resolve_admin_report(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        report_id = data.get('reportId')
        admin_reply = data.get('adminReply', '')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            # Fetch report details to notify the student
            async with db_conn.execute("SELECT user_id, report, subject, lesson_num FROM chapter_reports WHERE id = ?", (report_id,)) as cur:
                report_row = await cur.fetchone()
                
            if not report_row:
                return web.json_response({"success": False, "error": "Report not found"}, status=404)
                
            await db_conn.execute(
                "UPDATE chapter_reports SET status = 'resolved', admin_reply = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (admin_reply, report_id)
            )
            await db_conn.commit()
            
            # Notify student on Telegram
            bot = request.app['bot']
            try:
                subj_map = {
                    "aqida": "العقيدة",
                    "fiqh": "الفقه",
                    "sira": "السيرة",
                    "hadith": "الحديث",
                    "tazkiyah": "التزكية"
                }
                subj_ar = subj_map.get(report_row['subject'].lower(), report_row['subject'])
                
                notif = (
                    f"🔔 <b>تحديث بخصوص بلاغك عن خطأ في المحتوى</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📍 المادة: <b>{subj_ar}</b> ← درس {report_row['lesson_num']}\n"
                    f"📝 بلاغك: <i>\"{report_row['report']}\"</i>\n\n"
                    f"✅ <b>رد الإدارة:</b>\n"
                    f"<i>\"{admin_reply}\"</i>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"شكراً لمساعدتك في بناء الأكاديمية!"
                )
                await bot.send_message(report_row['user_id'], notif, parse_mode="HTML")
            except Exception as notify_err:
                logger.error(f"Error notifying student for report resolution: {notify_err}")
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error resolving report: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Edit course transcription text
async def edit_course_chapter(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        chapter_idx = data.get('chapterIdx')
        new_title = data.get('newTitle')
        new_text = data.get('newText')
        new_video_url = data.get('newVideoUrl')
        new_poetry = data.get('newPoetry')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        transcripts_path = 'dashboard/transcripts.json'
        if os.path.exists(transcripts_path):
            with open(transcripts_path, 'r', encoding='utf-8') as f:
                lessons = json.load(f)
                
            lesson = next((l for l in lessons if l.get('subject') == subject and l.get('lessonNum') == lesson_num), None)
            if lesson and 'thematic_blocks' in lesson and len(lesson['thematic_blocks']) > chapter_idx:
                block = lesson['thematic_blocks'][chapter_idx]
                if new_title is not None:
                    block['title'] = new_title
                if new_text is not None:
                    block['explanation'] = new_text
                if new_video_url is not None:
                    block['video_link'] = new_video_url
                if new_poetry is not None:
                    block['poetry_verses'] = new_poetry
                
                with open(transcripts_path, 'w', encoding='utf-8') as f:
                    json.dump(lessons, f, ensure_ascii=False, indent=4)
                    
                # Sync with SQLite DB
                try:
                    import database as db
                    import re
                    timestamp_seconds = None
                    final_url = new_video_url if new_video_url is not None else block.get('video_link')
                    if final_url:
                        m = re.search(r'[?&]t=(\d+)s?', final_url)
                        if m:
                            timestamp_seconds = int(m.group(1))
                    
                    await db.add_course_chapter(
                        subject=subject,
                        course_number=int(lesson_num),
                        chapter_index=int(chapter_idx) + 1,
                        title=new_title if new_title is not None else block.get('title', ''),
                        content=new_text if new_text is not None else (block.get('explanation') or block.get('content') or block.get('search_text', '')),
                        youtube_link=final_url,
                        timestamp_seconds=timestamp_seconds,
                        poetry_verses=new_poetry if new_poetry is not None else block.get('poetry_verses')
                    )
                except Exception as db_err:
                    logger.error(f"Database sync failed in edit_course_chapter: {db_err}")
                    
                # Sync to prod folder if exists
                prod_transcripts = 'C:/Users/Houssam/Desktop/telegram-dashboard/transcripts.json'
                if os.path.exists(prod_transcripts):
                    with open(prod_transcripts, 'w', encoding='utf-8') as pf:
                        json.dump(lessons, pf, ensure_ascii=False, indent=4)
                        
                    # Optional Git auto push
                    try:
                        import subprocess
                        subprocess.run(["git", "add", "transcripts.json"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                        subprocess.run(["git", "commit", "-m", f"[Backup Bot] Admin edit {subject} course {lesson_num} chapter {chapter_idx}"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                    except Exception as git_err:
                        logger.error(f"Git auto-deploy failed: {git_err}")
                        
                return web.json_response({"success": True})
            else:
                return web.json_response({"success": False, "error": "Chapter not found"}, status=404)
        else:
            return web.json_response({"success": False, "error": "Transcripts file not found"}, status=500)
    except Exception as e:
        logger.error(f"Error in edit_course_chapter: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def save_lesson_axes(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        axes = data.get('thematicBlocks', [])
        
        if user_id is not None:
            user_id = int(user_id)
            
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        transcripts_path = 'dashboard/transcripts.json'
        if os.path.exists(transcripts_path):
            with open(transcripts_path, 'r', encoding='utf-8') as f:
                lessons = json.load(f)
                
            lesson = next((l for l in lessons if l.get('subject') == subject and l.get('lessonNum') == lesson_num), None)
            if lesson:
                # Update thematic blocks array in JSON
                new_blocks = []
                for ax in axes:
                    new_blocks.append({
                        "title": ax.get("title", ""),
                        "explanation": ax.get("explanation", ""),
                        "video_link": ax.get("video_link", ""),
                        "poetry_verses": ax.get("poetry_verses", ""),
                        "search_text": ax.get("search_text", "")
                    })
                lesson['thematic_blocks'] = new_blocks
                
                with open(transcripts_path, 'w', encoding='utf-8') as f:
                    json.dump(lessons, f, ensure_ascii=False, indent=4)
                    
                # Sync to database: DELETE existing and INSERT/REPLACE all
                try:
                    import database as db
                    import re
                    import aiosqlite
                    from config import DATABASE_PATH
                    
                    async with aiosqlite.connect(DATABASE_PATH) as conn:
                        await conn.execute("DELETE FROM course_chapters WHERE subject = ? AND course_number = ?", (subject.lower().strip(), int(lesson_num)))
                        await conn.commit()
                        
                    for idx, block in enumerate(new_blocks):
                        video_url = block.get('video_link')
                        timestamp_seconds = None
                        if video_url:
                            m = re.search(r'[?&]t=(\d+)s?', video_url)
                            if m:
                                timestamp_seconds = int(m.group(1))
                        
                        await db.add_course_chapter(
                            subject=subject,
                            course_number=int(lesson_num),
                            chapter_index=idx + 1,
                            title=block.get('title', ''),
                            content=block.get('search_text', ''),
                            youtube_link=video_url,
                            timestamp_seconds=timestamp_seconds,
                            poetry_verses=block.get('poetry_verses', '')
                        )
                except Exception as db_err:
                    logger.error(f"Database sync failed in save_lesson_axes: {db_err}")
                    
                # Sync to prod folder if exists
                prod_transcripts = 'C:/Users/Houssam/Desktop/telegram-dashboard/transcripts.json'
                if os.path.exists(prod_transcripts):
                    with open(prod_transcripts, 'w', encoding='utf-8') as pf:
                        json.dump(lessons, pf, ensure_ascii=False, indent=4)
                        
                    try:
                        import subprocess
                        subprocess.run(["git", "add", "transcripts.json"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                        subprocess.run(["git", "commit", "-m", f"[Backup Bot] Admin save thematic blocks {subject} course {lesson_num}"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                    except Exception as git_err:
                        logger.error(f"Git push failed in save_lesson_axes: {git_err}")
                        
                return web.json_response({"success": True})
            else:
                return web.json_response({"success": False, "error": "Lesson not found"}, status=404)
        else:
            return web.json_response({"success": False, "error": "Transcripts file not found"}, status=500)
    except Exception as e:
        logger.error(f"Error in save_lesson_axes: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Generate thematic questions with Gemini
async def generate_questions_ia(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject', '').strip()
        lesson_num = data.get('lessonNum')
        chapter_idx = data.get('chapterIdx', 0)
        theme = data.get('theme', '').strip()
        num_questions = int(data.get('numQuestions', 3))
        instructions = data.get('instructions', '').strip()
        model_name = data.get('model', 'gemini-flash-lite-latest')

        strategy = data.get('strategy', 'smart')
        specific_subtheme = data.get('specificSubtheme', '').strip()

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        if not subject or lesson_num is None:
            return web.json_response({"success": False, "error": "Paramètres manquants (matière ou numéro de leçon)"}, status=400)

        # Reload GEMINI_API_KEYS fresh from config (ensures .env was loaded)
        import importlib
        import config as cfg_module
        importlib.reload(cfg_module)
        api_keys = getattr(cfg_module, "GEMINI_API_KEYS", [])
        if not api_keys and getattr(cfg_module, "GEMINI_API_KEY", ""):
            api_keys = [cfg_module.GEMINI_API_KEY]
        if not api_keys:
            return web.json_response({"success": False, "error": "Clé API Gemini non configurée dans .env"}, status=500)

        # Find reference text from transcript JSON file
        transcripts_path = 'dashboard/transcripts.json'
        chapter_content = ""
        course_name = ""
        all_course_subthemes = []
        if os.path.exists(transcripts_path):
            with open(transcripts_path, 'r', encoding='utf-8') as f:
                lessons = json.load(f)
            # Normalize aqida <-> aqeeda
            subj_variants = [subject]
            if subject.lower() in ('aqida', 'aqeeda'):
                subj_variants = ['aqida', 'aqeeda']
            lesson_obj = next(
                (l for l in lessons
                 if l.get('subject') in subj_variants
                 and (l.get('lessonNum') == lesson_num or str(l.get('lessonNum')) == str(lesson_num))),
                None
            )
            if lesson_obj:
                course_name = lesson_obj.get('title', '')
                blocks = lesson_obj.get('thematic_blocks', [])
                all_course_subthemes = [b.get('title', '') for b in blocks if b.get('title')]
                if blocks:
                    if chapter_idx is not None and 0 <= int(chapter_idx) < len(blocks):
                        block = blocks[int(chapter_idx)]
                        chapter_content = block.get('explanation') or block.get('search_text') or ""
                        if not theme:
                            theme = block.get('title', '')
                    else:
                        # User selected "All lesson", concatenate all blocks
                        content_parts = []
                        for b in blocks:
                            text = b.get('explanation') or b.get('search_text') or ""
                            if text:
                                content_parts.append(f"--- {b.get('title', 'محور')} ---\n{text}")
                        chapter_content = "\n\n".join(content_parts)
                        if not theme:
                            theme = "الدرس كاملاً"

        # Construct specialized prompts based on subject
        subj_clean = subject.lower().strip()

        # Dynamic strategy instructions
        strategy_instr = ""
        if strategy == "specific" and specific_subtheme:
            strategy_instr = f"يجب أن تكون جميع الأسئلة المولدة مستهدفة بدقة للمحور الفرعي التالي حصراً: \"{specific_subtheme}\" ويجب تعيين قيمة الحقل sub_theme لكل سؤال إلى \"{specific_subtheme}\" تماماً."
        else:
            # Smart balanced strategy: prioritize axes with fewest existing questions
            if all_course_subthemes:
                try:
                    from config import DATABASE_PATH
                    import aiosqlite as _aio
                    subj_norm = subject.lower()
                    if subj_norm == 'aqeeda': subj_norm = 'aqida'
                    axe_counts = {}
                    async with _aio.connect(DATABASE_PATH) as _db:
                        async with _db.execute(
                            "SELECT sub_theme, COUNT(*) as cnt FROM questions WHERE LOWER(subject) IN (?, ?) AND course_number = ? GROUP BY sub_theme",
                            (subj_norm, 'aqeeda' if subj_norm == 'aqida' else subj_norm, int(lesson_num))
                        ) as _cur:
                            async for _row in _cur:
                                if _row[0]:
                                    axe_counts[_row[0]] = _row[1]
                    # Sort: axes with fewest questions first (0 = highest priority)
                    sorted_subthemes = sorted(all_course_subthemes, key=lambda st: axe_counts.get(st, 0))
                    counts_info = [f'"{st}" ({axe_counts.get(st, 0)} أسئلة)' for st in sorted_subthemes]
                    subthemes_list_str = "، ".join(counts_info)
                    strategy_instr = (
                        f"يجب توزيع الأسئلة الـ {num_questions} بشكل ذكي ومتوازن على المحاور الفرعية التالية لهذا الدرس، "
                        f"مع الأولوية للمحاور التي تمتلك أقل عدد من الأسئلة حالياً في قاعدة البيانات (تُذكر الأعداد الحالية للإرشاد فقط): "
                        f"[{subthemes_list_str}]. تأكد من تعيين sub_theme لكل سؤال بالمحور الفرعي المناسب له بالضبط."
                    )
                except Exception as _ex:
                    logger.warning(f"Could not fetch axe counts for smart distribution: {_ex}")
                    subthemes_list_str = "، ".join([f'"{st}"' for st in all_course_subthemes])
                    strategy_instr = f"يجب توزيع الأسئلة الـ {num_questions} بشكل متوازن لتغطية أكبر قدر ممكن من المحاور الفرعية التالية: [{subthemes_list_str}]. تأكد أن تعين لكل سؤال المحور الفرعي المناسب له من القائمة في حقل sub_theme."
            else:
                strategy_instr = "قم بتوزيع الأسئلة لتغطي جزئيات فرعية متنوعة ومختلفة من الدرس، وعيّن قيمة sub_theme بشكل معبر لكل سؤال."

        if subj_clean in ("fiqh", "الفقه"):
            prompt = f"""أنت خبير في الفقه الإسلامي (المذهب المالكي) ومصمم اختبارات تعليمية.
قم بتوليد {num_questions} أسئلة اختيار من متعدد (QCM) باللغة العربية الفصحى.

المادة: الفقه الإسلامي
رقم الدرس: {lesson_num}
اسم الدرس: {course_name or f'الدرس {lesson_num}'}
الموضوع/المحور النشط: {theme or 'عام'}
النص المرجعي للدرس:
{chapter_content or 'لا يوجد نص مرجعي - اعتمد على معرفتك العامة بالمادة'}

التعليمات الإضافية:
{instructions if instructions else 'لا توجد تعليمات خاصة'}

إستراتيجية التوزيع المستهدفة:
{strategy_instr}

شروط صارمة للتوليد:
1. كل سؤال يحتوي على 4 خيارات (أ ب ج د) باللغة العربية.
2. إجابة صحيحة واحدة فقط.
3. أضف شرحاً علمياً موجزاً ودقيقاً لكل سؤال يوضح سبب صحة الخيار المختار.
4. **حقل الـ theme (المحور العام للدرس)**: يجب أن يحدد بدقة أحد المحاور التسعة التالية حصراً ليكون متوافقاً مع المنصة (اختر الأكثر ملاءمة لموضوع السؤال):
[فرائض الصلاة، شروط الصلاة، سنن الصلاة، مندوبات الصلاة، مكروهات ومبطلات الصلاة، صلاة الجمعة، سجود السهو، فرض عين / فرض كفاية، شروط الإمام]
5. **حقل الـ sub_theme (الجزئية الدقيقة / العنوان الفرعي الخاص)**: يجب أن يحدد بدقة اسم الشرط أو الفرض أو الجزئية المحددة التي يدور حولها السؤال من النص المرجعي (مثال: "ستر العورة"، "استقبال القبلة"، "طهارة الحدث"، "النية"، "تكبيرة الإحرام"...). لا تتركه فارغاً ولا تكرره كاسم المحور العام نفسه.

أعد النتيجة كـ JSON فقط (مصفوفة) بالشكل التالي بدون أي نص إضافي:
[
  {{
    "question": "نص السؤال الفقهي الدقيق",
    "choice_a": "الخيار أ",
    "choice_b": "الخيار ب",
    "choice_c": "الخيار ج",
    "choice_d": "الخيار د",
    "correct_answer": "a",
    "explanation": "شرح الإجابة الفقهية بالتفصيل",
    "theme": "شروط الصلاة",
    "sub_theme": "ستر العورة"
  }}
]"""
        elif subj_clean in ("sira", "السيرة"):
            prompt = f"""أنت خبير في السيرة النبوية ومصمم اختبارات تعليمية.
قم بتوليد {num_questions} أسئلة اختيار من متعدد (QCM) باللغة العربية الفصحى.

المادة: السيرة النبوية
رقم الدرس: {lesson_num}
اسم الدرس: {course_name or f'الدرس {lesson_num}'}
الموضوع/المحور النشط: {theme or 'عام'}
النص المرجعي للدرس:
{chapter_content or 'لا يوجد نص مرجعي - اعتمد على معرفتك العامة بالمادة'}

التعليمات الإضافية:
{instructions if instructions else 'لا توجد تعليمات خاصة'}

إستراتيجية التوزيع المستهدفة:
{strategy_instr}

شروط صارمة للتوليد:
1. كل سؤال يحتوي على 4 خيارات (أ ب ج د) باللغة العربية.
2. إجابة صحيحة واحدة فقط.
3. أضف شرحاً علمياً موجزاً ودقيقاً لكل سؤال يوضح سبب صحة الخيار المختار.
4. **حقل الـ theme (المحور الرئيسي)**: يجب أن يحدد بدقة أحد المحاور الستة التالية حصراً ليكون متوافقاً مع المنصة:
[الغزوات والسرايا، بيت النبوة والحياة الشخصية، العبادات والمعاملات والتشريعات، الصحابة والمجتمع المدني، العهود والوفود والعلاقات الخارجية، الشمائل والأخلاق النبوية]
5. **حقل الـ sub_theme (الجزئية الدقيقة / العنوان الفرعي الخاص)**: يجب أن يحدد بدقة الحدث أو المفهوم الفرعي المحدد للسؤال من النص المرجعي (مثال: "غزوة بدر الكبرى"، "وفاة زينب بنت خزيمة"، "تحويل القبلة"...). لا تتركه فارغاً.
6. **حقل الـ hijra_year (السنة الهجرية)**: حدد السنة الهجرية التي وقع فيها هذا الحدث بدقة كعدد صحيح (إنتجر) (مثال: 2 لغزوة بدر، 3 لغزوة أحد، 9 لغزوة تبوك). إذا لم يكن للسؤال تاريخ هجري محدد ضع null.

أعد النتيجة كـ JSON فقط (مصفوفة) بالشكل التالي بدون أي نص إضافي:
[
  {{
    "question": "نص السؤال التاريخي الدقيق",
    "choice_a": "الخيار أ",
    "choice_b": "الخيار ب",
    "choice_c": "الخيار ج",
    "choice_d": "الخيار د",
    "correct_answer": "a",
    "explanation": "شرح الإجابة التاريخية بالتفصيل",
    "theme": "الغزوات والسرايا",
    "sub_theme": "غزوة بدر الكبرى",
    "hijra_year": 2
  }}
]"""
        elif subj_clean in ("nahw", "النحو"):
            calculated_theme = "باب المرفوعات"
            try:
                l_num = int(lesson_num)
                if l_num == 14:
                    calculated_theme = "باب النكرة والمعرفة"
                elif l_num == 21:
                    # Check active theme or block name
                    if theme and "المفعول" in theme:
                        calculated_theme = "باب المنصوبات"
                    else:
                        calculated_theme = "باب المرفوعات"
                elif l_num > 21:
                    calculated_theme = "باب المنصوبات"
            except:
                pass

            prompt = f"""أنت خبير في النحو العربي ومصمم اختبارات تعليمية.
قم بتوليد {num_questions} أسئلة اختيار من متعدد (QCM) باللغة العربية الفصحى.

المادة: النحو
رقم الدرس: {lesson_num}
اسم الدرس: {course_name or f'الدرس {lesson_num}'}
الموضوع/المحور النشط: {theme or 'عام'}
النص المرجعي للدرس:
{chapter_content or 'لا يوجد نص مرجعي - اعتمد على معرفتك العامة بالمادة'}

شروط صارمة للتوليد:
1. كل سؤال يحتوي على 4 خيارات (أ ب ج د) باللغة العربية.
2. إجابة صحيحة واحدة فقط.
3. أضف شرحاً علمياً موجزاً ودقيقاً لكل سؤال يوضح سبب صحة الخيار المختار.
4. **حقل الـ theme (المحور العام)**: يجب أن يحدد بدقة القيمة التالية ليكون متوافقاً مع المنصة:
"{calculated_theme}"
5. **حقل الـ sub_theme (الجزئية الدقيقة / العنوان الفرعي الخاص)**: يجب أن يطابق بدقة الجزئية الدقيقة النحوية التي يدور حولها السؤال من القائمة التالية بناءً على المحور العام:
- إذا كان المحور العام "باب النكرة والمعرفة"، اختر أحد الخيارين: ["الاسم الموصول وصلته"، "المعرّف بأداة"]
- إذا كان المحور العام "باب المرفوعات"، اختر أحد الخيارات النحوية التالية:
  ["الفاعل"، "المفعول الذي لم يسم فاعله"، "المبتدأ والخبر"، "العوامل - كان وأخواتها"، "العوامل - الحروف المشبهة بـ \"ليس\""، "العوامل - أفعال المقاربة"، "العوامل - إنّ وأخواتها"، "العوامل - لا النافية للجنس"، "العوامل - ظنّ وأخواتها"]
- إذا كان المحور العام "باب المنصوبات"، اختر: ["المفعول به"]

أعد النتيجة كـ JSON فقط (مصفوفة) بالشكل التالي بدون أي نص إضافي:
[
  {{
    "question": "نص السؤال النحوي الدقيق",
    "choice_a": "الخيار أ",
    "choice_b": "الخيار ب",
    "choice_c": "الخيار ج",
    "choice_d": "الخيار د",
    "correct_answer": "a",
    "explanation": "شرح الإجابة النحوية والقاعدة بالتفصيل",
    "theme": "{calculated_theme}",
    "sub_theme": "الفاعل"
  }}
]"""
        else:
            prompt = f"""أنت خبير في العلوم الإسلامية ومصمم اختبارات تعليمية.
قم بتوليد {num_questions} أسئلة اختيار من متعدد (QCM) باللغة العربية الفصحى.

المادة: {subject}
رقم الدرس: {lesson_num}
اسم الدرس: {course_name or f'الدرس {lesson_num}'}
الموضوع/المحور: {theme or 'عام'}
النص المرجعي للدرس:
{chapter_content or 'لا يوجد نص مرجعي'}

التعليمات الإضافية:
{instructions if instructions else 'لا توجد تعليمات خاصة'}

إستراتيجية التوزيع المستهدفة:
{strategy_instr}

شروط:
1. كل سؤال يحتوي على 4 خيارات (أ ب ج د).
2. إجابة صحيحة واحدة فقط.
3. أضف شرحاً علمياً موجزاً لكل سؤال.

أعد النتيجة كـ JSON فقط (مصفوفة) بالشكل التالي بدون أي نص إضافي:
[
  {{
    "question": "نص السؤال",
    "choice_a": "الخيار أ",
    "choice_b": "الخيار ب",
    "choice_c": "الخيار ج",
    "choice_d": "الخيار د",
    "correct_answer": "a",
    "explanation": "شرح الإجابة",
    "theme": "المحور العام",
    "sub_theme": "الجزئية العامة"
  }}
]"""
        # --- Use exact same SDK pattern as handlers/admin.py ---
        import google.generativeai as genai

        # Valid model names for old SDK
        valid_models = ['gemini-flash-lite-latest', 'gemini-1.5-flash', 'gemini-1.5-flash-latest',
                        'gemini-1.5-pro', 'gemini-2.0-flash', 'gemini-2.0-flash-lite',
                        'gemini-2.5-flash-preview-05-20', 'gemini-2.5-flash']
        if model_name not in valid_models:
            model_name = 'gemini-flash-lite-latest'

        response_text = None
        last_error = None
        for current_key in api_keys:
            try:
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(model_name)
                response = await model.generate_content_async(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                response_text = response.text.strip()
                if response_text:
                    # Clean markdown wrappers if present
                    if response_text.startswith("```"):
                        response_text = re.sub(r"^```json\s*", "", response_text)
                        response_text = re.sub(r"^```\s*", "", response_text)
                        response_text = re.sub(r"\s*```$", "", response_text)
                        response_text = response_text.strip()
                    break
            except Exception as ex:
                logger.warning(f"Failed generation with key {current_key[:10]}...: {ex}")
                last_error = ex
                continue

        if not response_text:
            raise last_error or Exception("Toutes les clés API ont échoué lors de la génération.")

        questions = json.loads(response_text)
        if isinstance(questions, dict) and "questions" in questions:
            questions = questions["questions"]

        return web.json_response({"success": True, "questions": questions})
    except Exception as e:
        logger.error(f"Error generating questions: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)



# Admin API: Bulk Save Questions
async def save_bulk_questions(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        questions = data.get('questions', [])

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        if not subject or lesson_num is None or not questions:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)

        # Get course name
        course_name = ""
        transcripts_path = 'dashboard/transcripts.json'
        if os.path.exists(transcripts_path):
            with open(transcripts_path, 'r', encoding='utf-8') as f:
                lessons = json.load(f)
            lesson = next((l for l in lessons if l.get('subject') == subject and l.get('lessonNum') == lesson_num), None)
            if lesson:
                course_name = lesson.get('title', '')

        import database as db
        inserted_count = 0
        for q in questions:
            # Parse hijra_year safely as integer or None
            hijra_val = q.get("hijra_year")
            try:
                hijra_year = int(hijra_val) if hijra_val is not None and str(hijra_val).strip() != "" else None
            except (ValueError, TypeError):
                hijra_year = None

            q_data = {
                "subject": subject,
                "course_number": int(lesson_num),
                "course_name": course_name,
                "question": q.get("question", "").strip(),
                "choice_a": q.get("choice_a", "").strip(),
                "choice_b": q.get("choice_b", "").strip(),
                "choice_c": q.get("choice_c", "").strip(),
                "choice_d": q.get("choice_d", "").strip(),
                "correct_answer": q.get("correct_answer", "a").strip().lower(),
                "explanation": q.get("explanation", "").strip(),
                "source": "ai_generated",
                "hijra_year": hijra_year,
                "theme": q.get("theme") or "",
                "sub_theme": q.get("sub_theme") or ""
            }
            if q_data["question"] and q_data["choice_a"]:
                await db.add_question_to_db(q_data)
                inserted_count += 1

        return web.json_response({"success": True, "inserted_count": inserted_count})
    except Exception as e:
        logger.error(f"Error saving bulk questions: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Save complete lesson segments
async def save_full_transcript(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        new_segments = data.get('segments')
        new_thematic_blocks = data.get('thematicBlocks')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        if not subject or lesson_num is None or new_segments is None:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)
            
        transcripts_path = 'dashboard/transcripts.json'
        if os.path.exists(transcripts_path):
            with open(transcripts_path, 'r', encoding='utf-8') as f:
                lessons = json.load(f)
                
            lesson = next((l for l in lessons if l.get('subject') == subject and l.get('lessonNum') == lesson_num), None)
            if lesson:
                lesson['segments'] = new_segments
                if new_thematic_blocks is not None:
                    lesson['thematic_blocks'] = new_thematic_blocks
                
                # Also rebuild full_text
                lesson['full_text'] = " ".join(seg.get('text', '') for seg in new_segments)
                
                with open(transcripts_path, 'w', encoding='utf-8') as f:
                    json.dump(lessons, f, ensure_ascii=False, indent=4)
                    
                # Sync all thematic blocks to SQLite DB
                try:
                    import database as db
                    from config import DATABASE_PATH
                    import aiosqlite
                    import re
                    async with aiosqlite.connect(DATABASE_PATH) as conn:
                        await conn.execute("DELETE FROM course_chapters WHERE subject = ? AND course_number = ?", (subject.lower().strip(), int(lesson_num)))
                        await conn.commit()
                    
                    if new_thematic_blocks:
                        for idx, block in enumerate(new_thematic_blocks):
                            new_video_url = block.get('video_link')
                            timestamp_seconds = None
                            if new_video_url:
                                m = re.search(r'[?&]t=(\d+)s?', new_video_url)
                                if m:
                                    timestamp_seconds = int(m.group(1))
                            
                            await db.add_course_chapter(
                                subject=subject,
                                course_number=int(lesson_num),
                                chapter_index=idx + 1,
                                title=block.get('title', ''),
                                content=block.get('explanation') or block.get('content') or block.get('search_text', ''),
                                youtube_link=new_video_url,
                                timestamp_seconds=timestamp_seconds,
                                poetry_verses=block.get('poetry_verses')
                            )
                except Exception as db_err:
                    logger.error(f"Database sync failed in save_full_transcript: {db_err}")
                    
                # Sync to prod folder if exists
                prod_transcripts = 'C:/Users/Houssam/Desktop/telegram-dashboard/transcripts.json'
                if os.path.exists(prod_transcripts):
                    with open(prod_transcripts, 'w', encoding='utf-8') as pf:
                        json.dump(lessons, pf, ensure_ascii=False, indent=4)
                        
                    # Optional Git auto push
                    try:
                        import subprocess
                        subprocess.run(["git", "add", "transcripts.json"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                        subprocess.run(["git", "commit", "-m", f"[Backup Bot] Admin edit full transcript {subject} course {lesson_num}"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                        subprocess.run(["git", "push", "origin", "main"], cwd="C:/Users/Houssam/Desktop/telegram-dashboard", check=True)
                    except Exception as git_err:
                        logger.error(f"Git auto-deploy failed: {git_err}")
                        
                return web.json_response({"success": True})
                
        return web.json_response({"success": False, "error": "Transcripts file not found"}, status=404)
    except Exception as e:
        logger.error(f"Error saving full transcript: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_admin_question(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        question_id = data.get('questionId')

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        if not question_id:
            return web.json_response({"success": False, "error": "Missing questionId"}, status=400)

        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT id, subject, course_number, course_name, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, source, created_at, hijra_year, theme, is_active, sub_theme FROM questions WHERE id = ?", (int(question_id),)) as cur:
                row = await cur.fetchone()

        if not row:
            return web.json_response({"success": False, "error": "Question not found"}, status=404)

        q_dict = dict(row)
        if q_dict.get("source") == "student_proposal":
            async with aiosqlite.connect(DATABASE_PATH) as db_conn:
                db_conn.row_factory = aiosqlite.Row
                async with db_conn.execute("SELECT first_name, username, user_id FROM questions_proposees WHERE question = ? OR (subject = ? AND course_number = ? AND question = ?) LIMIT 1", (q_dict["question"], q_dict["subject"], q_dict["course_number"], q_dict["question"])) as cur:
                    prop_row = await cur.fetchone()
                    if prop_row:
                        q_dict["proposed_by"] = {
                            "first_name": prop_row["first_name"],
                            "username": prop_row["username"],
                            "user_id": prop_row["user_id"]
                        }

        return web.json_response({"success": True, "question": q_dict})
    except Exception as e:
        logger.error(f"Error loading admin question: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def delete_admin_question(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        question_id = data.get('questionId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        if not question_id:
            return web.json_response({"success": False, "error": "Missing questionId"}, status=400)
            
        import database as db
        success = await db.delete_question_from_db(question_id)
        if success:
            return web.json_response({"success": True})
        else:
            return web.json_response({"success": False, "error": "Database deletion failed"}, status=500)
    except Exception as e:
        logger.error(f"Error deleting admin question: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def update_admin_question(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        question_id = data.get('questionId')
        question = (data.get('question') or '').strip()
        choice_a = (data.get('choiceA') or '').strip()
        choice_b = (data.get('choiceB') or '').strip()
        choice_c = (data.get('choiceC') or '').strip()
        choice_d = (data.get('choiceD') or '').strip()
        correct_answer = (data.get('correctAnswer') or '').strip().lower()
        explanation = (data.get('explanation') or '').strip()
        is_active = 1 if data.get('isActive', True) else 0
        theme = (data.get('theme') or '').strip()
        sub_theme = (data.get('subTheme') or '').strip()
        hijra_val = data.get('hijraYear')
        try:
            hijra_year = int(hijra_val) if hijra_val is not None and str(hijra_val).strip() != "" else None
        except (ValueError, TypeError):
            hijra_year = None

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        if not question_id:
            return web.json_response({"success": False, "error": "Missing questionId"}, status=400)
        if not question or not choice_a or not choice_b:
            return web.json_response({"success": False, "error": "Question and choices A/B are required"}, status=400)
        if correct_answer not in {"a", "b", "c", "d"}:
            return web.json_response({"success": False, "error": "correctAnswer must be a, b, c, or d"}, status=400)
        if correct_answer == "c" and not choice_c:
            return web.json_response({"success": False, "error": "Choice C is empty"}, status=400)
        if correct_answer == "d" and not choice_d:
            return web.json_response({"success": False, "error": "Choice D is empty"}, status=400)

        def clean_val(val, is_expl=False):
            if not val or not isinstance(val, str):
                return val
            if is_expl:
                import re
                val = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", val)
                return val.replace("**", "")
            return val.replace("**", "")

        question = clean_val(question)
        choice_a = clean_val(choice_a)
        choice_b = clean_val(choice_b)
        choice_c = clean_val(choice_c)
        choice_d = clean_val(choice_d)
        explanation = clean_val(explanation, is_expl=True)

        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("UPDATE questions SET question = ?, choice_a = ?, choice_b = ?, choice_c = ?, choice_d = ?, correct_answer = ?, explanation = ?, is_active = ?, theme = ?, sub_theme = ?, hijra_year = ? WHERE id = ?", (question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, is_active, theme, sub_theme, hijra_year, int(question_id)))
            await db_conn.commit()

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error updating admin question: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def toggle_question_active_api(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        question_id = data.get('questionId')
        is_active = 1 if data.get('isActive') else 0

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        if not question_id:
            return web.json_response({"success": False, "error": "Missing questionId"}, status=400)

        from config import DATABASE_PATH
        import aiosqlite
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("UPDATE questions SET is_active = ? WHERE id = ?", (is_active, int(question_id)))
            await db_conn.commit()

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error toggling question active status: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def update_admin_proposal(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        proposal_id = data.get('proposalId')
        question = (data.get('question') or '').strip()
        choice_a = (data.get('choiceA') or '').strip()
        choice_b = (data.get('choiceB') or '').strip()
        choice_c = (data.get('choiceC') or '').strip()
        choice_d = (data.get('choiceD') or '').strip()
        correct_answer = (data.get('correctAnswer') or '').strip().lower()
        explanation = (data.get('explanation') or '').strip()

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        if not proposal_id:
            return web.json_response({"success": False, "error": "Missing proposalId"}, status=400)
        if not question or not choice_a or not choice_b:
            return web.json_response({"success": False, "error": "Question and choices A/B are required"}, status=400)
        if correct_answer not in {"a", "b", "c", "d"}:
            return web.json_response({"success": False, "error": "correctAnswer must be a, b, c, or d"}, status=400)
        if correct_answer == "c" and not choice_c:
            return web.json_response({"success": False, "error": "Choice C is empty"}, status=400)
        if correct_answer == "d" and not choice_d:
            return web.json_response({"success": False, "error": "Choice D is empty"}, status=400)

        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("UPDATE questions_proposees SET question = ?, choice_a = ?, choice_b = ?, choice_c = ?, choice_d = ?, correct_answer = ?, explanation = ? WHERE id = ?", (question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, int(proposal_id)))
            await db_conn.commit()

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error updating admin proposal: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Admin API: List student question proposals
async def get_admin_proposals(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role in ["support_admin", "tech_admin"]:
            return web.json_response({"success": True, "proposals": []})
            
        proposals = []
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT qp.id, qp.user_id, qp.username, qp.first_name, qp.subject, qp.topic, qp.lesson, qp.question, qp.choice_a, qp.choice_b, qp.choice_c, qp.choice_d, qp.correct_answer, qp.explanation, qp.status, qp.admin_feedback, qp.created_at, u.academic_year, qp.source, qp.contact_info, qp.claimed_by, qp.tags, qp.media_file_id, qp.media_type FROM questions_proposees qp LEFT JOIN users u ON qp.user_id = u.telegram_id ORDER BY qp.created_at DESC") as cur:
                async for r in cur:
                    proposals.append({
                        "id": r["id"],
                        "userId": r["user_id"],
                        "username": r["username"],
                        "firstName": r["first_name"],
                        "subject": r["subject"],
                        "topic": r["topic"],
                        "lesson": r["lesson"],
                        "question": r["question"],
                        "choiceA": r["choice_a"],
                        "choiceB": r["choice_b"],
                        "choiceC": r["choice_c"],
                        "choiceD": r["choice_d"],
                        "correctAnswer": r["correct_answer"],
                        "explanation": r["explanation"],
                        "status": r["status"],
                        "adminReply": r["admin_feedback"] or "",
                        "createdAt": r["created_at"],
                        "academicYear": r["academic_year"],
                        "source": r["source"] or "telegram",
                        "contactInfo": r["contact_info"] or "",
                        "claimedBy": r["claimed_by"] or "",
                        "tags": json.loads(r["tags"] or "[]"),
                        "mediaFileId": r["media_file_id"] or "",
                        "mediaType": r["media_type"] or ""
                    })
        return web.json_response({"success": True, "proposals": proposals})
    except Exception as e:
        logger.error(f"Error loading proposals: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Resolve a proposal
async def resolve_admin_proposal(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        proposal_id = data.get('proposalId')
        action = data.get('action') # 'approved' or 'rejected'
        rejection_reason = data.get('rejectionReason', '')
        if not rejection_reason:
            rejection_reason = data.get('adminFeedback', '')
            
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            async with db_conn.execute("SELECT user_id, question FROM questions_proposees WHERE id = ?", (proposal_id,)) as cur:
                proposal = await cur.fetchone()
            
            if not proposal:
                return web.json_response({"success": False, "error": "Proposal not found"}, status=404)
                
            if action == 'approved':
                async with db_conn.execute("SELECT MAX(id) FROM questions") as cur:
                    row = await cur.fetchone()
                    next_id = (row[0] or 1000) + 1
                    
                async with db_conn.execute("SELECT * FROM questions_proposees WHERE id = ?", (proposal_id,)) as cur:
                    prop_details = await cur.fetchone()
                    
                await db_conn.execute("INSERT INTO questions (id, subject, course_number, course_name, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation, source, theme, sub_theme, hijra_year) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'student_proposal', ?, ?, ?)", (next_id, prop_details["subject"], prop_details["course_number"], prop_details["lesson"], prop_details["question"], prop_details["choice_a"], prop_details["choice_b"], prop_details["choice_c"], prop_details["choice_d"], prop_details["correct_answer"], prop_details["explanation"], prop_details["topic"] or "", prop_details["tags"] or "", prop_details["hijra_year"]))
                
                await db_conn.execute("UPDATE questions_proposees SET status = 'approved', admin_feedback = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (rejection_reason, proposal_id))
            else:
                await db_conn.execute("UPDATE questions_proposees SET status = 'rejected', rejection_reason = ?, admin_feedback = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (rejection_reason, rejection_reason, proposal_id))
                
            await db_conn.commit()
            
            # Notify student on Telegram
            bot = request.app['bot']
            try:
                status_label = "✅ تم قبول سؤالك المقترح وإضافته للأسئلة الرسمية بالأكاديمية!"
                if rejection_reason and action == 'approved':
                    status_label += f"\n💬 تعليق الإدارة: {rejection_reason}"
                elif action != 'approved':
                    status_label = f"❌ عذراً، تم رفض سؤالك المقترح.\n💬 السبب: {rejection_reason}"
                    
                notif = (
                    f"📣 <b>تحديث بخصوص مقترحك لأسئلة المراجعة (البوت البديل)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"السؤال: <i>\"{proposal['question']}\"</i>\n\n"
                    f"{status_label}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"شكراً لمساهمتك في بناء الأكاديمية!"
                )
                await bot.send_message(proposal['user_id'], notif, parse_mode="HTML")
            except Exception as notify_err:
                logger.error(f"Error notifying student for proposal resolution: {notify_err}")
                
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error resolving proposal: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: List tickets from question_reports (suggestions, tech, errors, etc.)
async def get_admin_tickets(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        role = await get_admin_role(user_id)

        tickets = []
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            query = "SELECT qr.id, qr.user_id, qr.username, qr.first_name, qr.report_type, qr.question_id, qr.target, qr.notes, qr.urgency, qr.status, qr.admin_reply, qr.reviewed_at, qr.created_at, qr.claimed_by, qr.student_read, qr.tags, qr.media_file_id, qr.media_type, q.subject AS question_subject, q.course_number AS question_course_number, u.academic_year, qr.source, qr.contact_info FROM question_reports qr LEFT JOIN questions q ON qr.question_id = q.id LEFT JOIN users u ON qr.user_id = u.telegram_id WHERE 1=1"
            
            if role in ["support_admin", "tech_admin"]:
                query += " AND qr.report_type = 'tech'"
            elif role in ["improvement_admin", "academie_admin"]:
                query += " AND qr.report_type = 'schooling'"
                
            query += " ORDER BY qr.created_at DESC"
            
            async with db_conn.execute(query) as cur:
                async for r in cur:
                    tickets.append({
                        "id": r["id"],
                        "userId": r["user_id"],
                        "username": r["username"],
                        "firstName": r["first_name"],
                        "reportType": r["report_type"],
                        "questionId": r["question_id"],
                        "target": r["target"],
                        "notes": r["notes"],
                        "urgency": r["urgency"],
                        "status": r["status"],
                        "adminReply": r["admin_reply"] or "",
                        "reviewedAt": r["reviewed_at"] or "",
                        "createdAt": r["created_at"],
                        "claimedBy": r["claimed_by"] or "",
                        "studentRead": r["student_read"],
                        "subject": r["question_subject"] or "",
                        "courseNumber": r["question_course_number"],
                        "academicYear": r["academic_year"],
                        "source": r["source"] or "telegram",
                        "contactInfo": r["contact_info"] or "",
                        "tags": json.loads(r["tags"] or "[]"),
                        "mediaFileId": r["media_file_id"] or "",
                        "mediaType": r["media_type"] or ""
                    })
        return web.json_response({"success": True, "tickets": tickets})
    except Exception as e:
        logger.error(f"Error loading tickets: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Omnichannel API: Receive tickets from external platforms (WhatsApp, Web, Gmail)
async def receive_external_ticket(request):
    try:
        data = await request.json()
        source = data.get('source') # 'whatsapp', 'gmail', 'platform'
        contact_info = data.get('contactInfo', '')
        notes = data.get('notes', '')
        report_type = data.get('reportType', 'other')
        first_name = data.get('firstName', 'Utilisateur Externe')
        telegram_id = data.get('telegramId', 0)
        username = data.get('username', f"ext_{source}")
        
        if not source or not notes:
            return web.json_response({"success": False, "error": "Missing source or notes"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            cursor = await db_conn.execute("INSERT INTO question_reports (user_id, username, first_name, report_type, notes, urgency, source, contact_info) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (telegram_id, username, first_name, report_type, notes, "Moyen", source, contact_info))
            await db_conn.commit()
            ticket_id = cursor.lastrowid
            
        return web.json_response({"success": True, "ticketId": ticket_id})
    except Exception as e:
        logger.error(f"Error receiving external ticket: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# AI Triage & Similarity API: find matching resolved tickets
async def handle_triage_match(request):
    try:
        data = await request.json()
        query = data.get('query', '').strip()
        use_ai = data.get('use_ai', False)
        if not query:
            return web.json_response({"success": True, "matches": []})
            
        import database as db
        matches = await db.search_similar_triage(query, use_ai=use_ai)
        return web.json_response({"success": True, "matches": matches})
    except Exception as e:
        logger.error(f"Error in handle_triage_match: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Student/Admin API: List student's own tickets (Mini App support)
async def get_student_tickets(request):
    try:
        telegram_id = request.query.get('telegram_id')
        if not telegram_id:
            try:
                data = await request.json()
                telegram_id = data.get('telegram_id')
            except Exception:
                pass
        if not telegram_id:
            return web.json_response({"success": False, "error": "Missing telegram_id"}, status=400)
            
        from config import DATABASE_PATH
        tickets = []
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT id, report_type, notes, urgency, status, admin_reply, created_at, media_file_id, media_type FROM question_reports WHERE user_id = ? ORDER BY created_at DESC", (int(telegram_id),)) as cur:
                async for r in cur:
                    tickets.append({
                        "id": r["id"],
                        "reportType": r["report_type"],
                        "notes": r["notes"],
                        "urgency": r["urgency"],
                        "status": r["status"],
                        "adminReply": r["admin_reply"] or "",
                        "createdAt": r["created_at"],
                        "mediaFileId": r["media_file_id"] or "",
                        "mediaType": r["media_type"] or ""
                    })
        return web.json_response({"success": True, "tickets": tickets})
    except Exception as e:
        logger.error(f"Error loading student tickets: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Student/Admin API: Get ticket chat messages history
async def get_ticket_messages_api(request):
    try:
        ticket_id = request.match_info.get('ticket_id')
        if not ticket_id:
            return web.json_response({"success": False, "error": "Missing ticket_id"}, status=400)
            
        import database as db
        messages = await db.get_ticket_chat_messages(int(ticket_id))
        return web.json_response({"success": True, "messages": messages})
    except Exception as e:
        logger.error(f"Error getting ticket messages: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Student/Admin API: Reply to a ticket (append to chat history)
async def reply_ticket_message_api(request):
    try:
        ticket_id = request.match_info.get('ticket_id')
        data = await request.json()
        sender = data.get('sender') # 'student' or 'admin'
        sender_name = data.get('sender_name')
        message = data.get('message', '').strip()
        media_file_id = data.get('mediaFileId')
        media_type = data.get('mediaType')
        
        if not ticket_id or not sender or not message:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)
            
        import database as db
        
        # Insert message into chat history
        msg_id = await db.add_ticket_chat_message(
            ticket_id=int(ticket_id),
            sender=sender,
            sender_name=sender_name,
            message=message,
            media_file_id=media_file_id,
            media_type=media_type
        )
        
        # Also update the main ticket's admin_reply or status if needed
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            if sender == 'admin':
                await db_conn.execute(
                    "UPDATE question_reports SET admin_reply = ?, reviewed_at = datetime('now') WHERE id = ?",
                    (message, int(ticket_id))
                )
            else:
                # If student replies, set status back to pending/in_progress so admins see it
                async with db_conn.execute("SELECT status FROM question_reports WHERE id = ?", (int(ticket_id),)) as cur:
                    row = await cur.fetchone()
                    if row and row[0] in ['resolved', 'rejected']:
                        await db_conn.execute("UPDATE question_reports SET status = 'pending' WHERE id = ?", (int(ticket_id),))
            await db_conn.commit()
            
        # Send Telegram notification if admin is replying
        if sender == 'admin':
            bot = request.app.get('bot')
            if bot:
                async with aiosqlite.connect(DATABASE_PATH) as db_conn:
                    db_conn.row_factory = aiosqlite.Row
                    async with db_conn.execute("SELECT user_id, report_type FROM question_reports WHERE id = ?", (int(ticket_id),)) as cur:
                        row = await cur.fetchone()
                if row:
                    try:
                        type_labels = {
                            'suggestion': '💡 اقتراحك',
                            'question_error': '🚩 بلاغ الخطأ',
                            'tech': '🔧 مشكلتك التقنية',
                            'other': '📩 رسالتك'
                        }
                        label = type_labels.get(row["report_type"], "📩 رسالتك")
                        
                        host = request.host
                        webapp_url = f"https://{host}/support.html?view=chat&ticket_id={ticket_id}"
                        
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
                        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 فتح المحادثة (Mini App)", web_app=WebAppInfo(url=webapp_url))]
                        ])
                        
                        await bot.send_message(
                            chat_id=row["user_id"],
                            text=f"📬 <b>رد جديد من الإدارة على {label} :</b>\n\n<i>\"{message}\"</i>",
                            reply_markup=reply_markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify student via Telegram: {e}")
                        
        else:
            # Notify admin group or the claimer
            from config import TELEGRAM_SUPPORT_GROUP_ID
            if TELEGRAM_SUPPORT_GROUP_ID:
                bot = request.app.get('bot')
                if bot:
                    try:
                        await bot.send_message(
                            chat_id=int(TELEGRAM_SUPPORT_GROUP_ID),
                            text=f"💬 <b>رد جديد من الطالب على التذكرة #{ticket_id} :</b>\n\n<i>\"{message}\"</i>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify admin group: {e}")
                        
        return web.json_response({"success": True, "messageId": msg_id})
    except Exception as e:
        logger.error(f"Error replying to ticket: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Broadcast Message
async def admin_broadcast(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        message_text = data.get('message', '').strip()
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
            
        if not message_text:
            return web.json_response({"success": False, "error": "Message is empty"}, status=400)
            
        bot = request.app.get('bot')
        if not bot:
            return web.json_response({"success": False, "error": "Bot instance not found"}, status=500)
            
        academic_year = data.get('academicYear')
        if academic_year:
            try:
                academic_year = int(academic_year)
            except ValueError:
                academic_year = None
                
        from database import get_all_user_ids
        users = await get_all_user_ids(academic_year=academic_year)
        
        import asyncio
        async def send_to_all():
            success_count = 0
            for uid in users:
                try:
                    await bot.send_message(chat_id=uid, text=message_text, parse_mode="HTML")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Broadcast failed for {uid}: {e}")
                await asyncio.sleep(0.05)
            logger.info(f"Broadcast finished. Sent to {success_count}/{len(users)} users.")
            
        asyncio.create_task(send_to_all())
            
        return web.json_response({"success": True, "total_users": len(users)})
        
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: List Questions (Question Bank)
async def admin_questions_list(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 50))
        subject = data.get('subject', '')
        lesson_num = data.get('lessonNum', '')
        source = data.get('source', '')
        search = data.get('search', '')
        chapter_idx = data.get('chapterIdx', '')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        from config import DATABASE_PATH
        import math
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            # If chapter_idx is selected, we filter by chapter index in memory using the same heuristic as stats
            if chapter_idx and subject and lesson_num:
                subj_clean = subject.lower().strip()
                if subj_clean == 'aqeeda':
                    subj_clean = 'aqida'
                
                async with db_conn.execute(
                    "SELECT id, subject, course_number, chapter_index, title, content FROM course_chapters WHERE LOWER(TRIM(subject)) IN (?, ?) AND course_number = ?", 
                    (subj_clean, 'aqeeda' if subj_clean == 'aqida' else subj_clean, int(lesson_num))
                ) as cur:
                    ch_rows = await cur.fetchall()
                c_chaps = [dict(ch) for ch in ch_rows]
                c_chaps.sort(key=lambda x: x["chapter_index"])
                
                # Fetch all questions matching subject, lesson, source, and search (without LIMIT/OFFSET)
                base_query = "SELECT * FROM questions WHERE 1=1"
                params = []
                
                base_query += " AND 1=1"
                # Normalize aqida/aqeeda — DB may use either spelling
                subj_variants = [subject]
                if subject.lower() in ('aqida', 'aqeeda'):
                    subj_variants = ['aqida', 'aqeeda']
                placeholders = ','.join('?' * len(subj_variants))
                base_query += f" AND LOWER(subject) IN ({placeholders})"
                params.extend([s.lower() for s in subj_variants])
                
                base_query += " AND course_number = ?"
                params.append(int(lesson_num))
                
                if source:
                    if source == 'official':
                        base_query += " AND (source IS NULL OR source = '' OR source = 'official' OR source NOT IN ('student_proposal', 'ai_generated', 'generated_by_gemini'))"
                    elif source == 'student_proposal':
                        base_query += " AND source = 'student_proposal'"
                    elif source == 'ai_generated':
                        base_query += " AND source IN ('ai_generated', 'generated_by_gemini')"
                    else:
                        base_query += " AND source = ?"
                        params.append(source)
                        
                if search:
                    base_query += " AND question LIKE ?"
                    params.append(f"%{search}%")
                    
                base_query += " ORDER BY id"
                
                async with db_conn.execute(base_query, params) as cur:
                    q_rows = await cur.fetchall()
                all_matching_questions = [dict(r) for r in q_rows]
                
                # Heuristic cleaner
                def clean_words(text):
                    if not text:
                        return set()
                    stop_words = {'le', 'la', 'de', 'en', 'et', 'في', 'من', 'على', 'ان', 'أن', 'هو', 'هي', 'هل'}
                    words = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower()).split()
                    return {w for w in words if w not in stop_words and len(w) > 2}
                
                if c_chaps:
                    for ch in c_chaps:
                        ch["clean_words"] = clean_words((ch["title"] or "") + " " + (ch.get("content") or ""))

                filtered_questions = []
                target_idx = int(chapter_idx)
                for q in all_matching_questions:
                    matched_idx = None
                    if c_chaps:
                        q_words = clean_words((q["question"] or "") + " " + (q["theme"] or ""))
                        best_ch_idx = None
                        best_score = -1
                        for ch in c_chaps:
                            score = len(q_words.intersection(ch["clean_words"]))
                            if score > best_score:
                                best_score = score
                                best_ch_idx = ch["chapter_index"]
                        
                        if best_ch_idx is not None and best_score > 0:
                            matched_idx = best_ch_idx
                        else:
                            matched_idx = c_chaps[0]["chapter_index"]
                            
                    if matched_idx == target_idx:
                        filtered_questions.append(q)
                
                # Fetch proposers for student proposals in this subset
                for q in filtered_questions:
                    if q.get("source") == "student_proposal":
                        async with db_conn.execute("""
                            SELECT first_name, username, user_id FROM questions_proposees 
                            WHERE question = ? OR (subject = ? AND course_number = ? AND question = ?)
                            LIMIT 1
                        """, (q["question"], q["subject"], q["course_number"], q["question"])) as cur:
                            prop_row = await cur.fetchone()
                            if prop_row:
                                q["proposed_by"] = {
                                    "first_name": prop_row["first_name"],
                                    "username": prop_row["username"],
                                    "user_id": prop_row["user_id"]
                                }
                                
                total_count = len(filtered_questions)
                total_pages = math.ceil(total_count / per_page) if per_page else 1
                
                start_offset = (page - 1) * per_page
                paginated_questions = filtered_questions[start_offset:start_offset + per_page]
                
                return web.json_response({
                    "success": True, 
                    "questions": paginated_questions,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total_count": total_count,
                        "total_pages": total_pages
                    }
                })
            
            # Default behavior (no chapter filter)
            query = "SELECT * FROM questions WHERE 1=1"
            count_query = "SELECT COUNT(*) FROM questions WHERE 1=1"
            params = []
            
            if subject:
                # Normalize aqida/aqeeda — DB may use either spelling
                subj_variants = [subject]
                if subject.lower() in ('aqida', 'aqeeda'):
                    subj_variants = ['aqida', 'aqeeda']
                placeholders = ','.join('?' * len(subj_variants))
                subj_clause = f" AND LOWER(subject) IN ({placeholders})"
                query += subj_clause
                count_query += subj_clause
                params.extend([s.lower() for s in subj_variants])
                
            if lesson_num:
                try:
                    query += " AND course_number = ?"
                    count_query += " AND course_number = ?"
                    params.append(int(lesson_num))
                except ValueError:
                    pass

            if source:
                if source == 'official':
                    src_clause = " AND (source IS NULL OR source = '' OR source = 'official' OR source NOT IN ('student_proposal', 'ai_generated', 'generated_by_gemini'))"
                    query += src_clause
                    count_query += src_clause
                elif source == 'student_proposal':
                    query += " AND source = 'student_proposal'"
                    count_query += " AND source = 'student_proposal'"
                elif source == 'ai_generated':
                    query += " AND source IN ('ai_generated', 'generated_by_gemini')"
                    count_query += " AND source IN ('ai_generated', 'generated_by_gemini')"
                else:
                    query += " AND source = ?"
                    count_query += " AND source = ?"
                    params.append(source)
                
            if search:
                query += " AND question LIKE ?"
                count_query += " AND question LIKE ?"
                params.append(f"%{search}%")
                
            query += " ORDER BY subject, course_number, id LIMIT ? OFFSET ?"
            
            async with db_conn.execute(count_query, params) as cur:
                total_count = (await cur.fetchone())[0]
                
            params.extend([per_page, (page - 1) * per_page])
            
            async with db_conn.execute(query, params) as cur:
                rows = await cur.fetchall()
                
            questions = [dict(r) for r in rows]
            
            # Fetch proposers for student proposals in this page
            for q in questions:
                if q.get("source") == "student_proposal":
                    async with db_conn.execute("""
                        SELECT first_name, username, user_id FROM questions_proposees 
                        WHERE question = ? OR (subject = ? AND course_number = ? AND question = ?)
                        LIMIT 1
                    """, (q["question"], q["subject"], q["course_number"], q["question"])) as cur:
                        prop_row = await cur.fetchone()
                        if prop_row:
                            q["proposed_by"] = {
                                "first_name": prop_row["first_name"],
                                "username": prop_row["username"],
                                "user_id": prop_row["user_id"]
                            }
                            
            total_pages = math.ceil(total_count / per_page) if per_page else 1
            
        return web.json_response({
            "success": True, 
            "questions": questions,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_count": total_count,
                "total_pages": total_pages
            }
        })
    except Exception as e:
        logger.error(f"Error in admin_questions_list: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_questions_stats_api(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        from config import DATABASE_PATH
        import aiosqlite
        
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT id, subject, course_number, source, question, theme FROM questions") as cur:
                questions_rows = await cur.fetchall()
            
            async with db_conn.execute("SELECT id, subject, course_number, chapter_index, title, content FROM course_chapters") as cur:
                chapters_rows = await cur.fetchall()
                
        questions = [dict(r) for r in questions_rows]
        chapters = [dict(r) for r in chapters_rows]
        
        stats = {}
        for s in ['aqida', 'fiqh', 'sira', 'nahw', 'tajweed']:
            stats[s] = {}
            
        chapters_by_course = {}
        for ch in chapters:
            subj = ch["subject"].lower().strip()
            if subj == 'aqeeda':
                subj = 'aqida'
            if subj not in stats:
                continue
            c_num = ch["course_number"]
            key = (subj, c_num)
            if key not in chapters_by_course:
                chapters_by_course[key] = []
            chapters_by_course[key].append(ch)
            
        def clean_words(text):
            if not text:
                return set()
            stop_words = {'le', 'la', 'de', 'en', 'et', 'في', 'من', 'على', 'ان', 'أن', 'هو', 'هي', 'هل'}
            words = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower()).split()
            return {w for w in words if w not in stop_words and len(w) > 2}

        # Pre-compute chapter words to speed up heuristic
        for ch in chapters:
            ch["clean_words"] = clean_words((ch["title"] or "") + " " + (ch.get("content") or ""))

        all_courses = set()
        for q in questions:
            subj = q["subject"].lower().strip()
            if subj == 'aqeeda':
                subj = 'aqida'
            if subj not in stats:
                continue
            all_courses.add((subj, q["course_number"]))
            
        for ch in chapters:
            subj = ch["subject"].lower().strip()
            if subj == 'aqeeda':
                subj = 'aqida'
            if subj not in stats:
                continue
            all_courses.add((subj, ch["course_number"]))
            
        for subj, c_num in all_courses:
            c_chaps = chapters_by_course.get((subj, c_num), [])
            c_chaps.sort(key=lambda x: x["chapter_index"])
            
            stats[subj][c_num] = {
                "course_number": c_num,
                "total": 0,
                "official": 0,
                "student_proposal": 0,
                "ai_generated": 0,
                "chapters": [
                    {
                        "chapter_index": ch["chapter_index"],
                        "title": ch["title"],
                        "count": 0,
                        "official": 0,
                        "student_proposal": 0,
                        "ai_generated": 0
                    } for ch in c_chaps
                ]
            }

        for q in questions:
            subj = q["subject"].lower().strip()
            if subj == 'aqeeda':
                subj = 'aqida'
            if subj not in stats:
                continue
            c_num = q["course_number"]
            
            course_data = stats[subj][c_num]
            course_data["total"] += 1
            
            src = q["source"] or ""
            if src == "student_proposal":
                course_data["student_proposal"] += 1
            elif src in ["ai_generated", "generated_by_gemini"]:
                course_data["ai_generated"] += 1
            else:
                course_data["official"] += 1
                
            c_chaps = chapters_by_course.get((subj, c_num), [])
            if c_chaps:
                q_words = clean_words((q["question"] or "") + " " + (q["theme"] or ""))
                best_ch_idx = None
                best_score = -1
                for ch in c_chaps:
                    score = len(q_words.intersection(ch["clean_words"]))
                    if score > best_score:
                        best_score = score
                        best_ch_idx = ch["chapter_index"]
                
                if best_ch_idx is not None and best_score > 0:
                    for ch_stat in course_data["chapters"]:
                        if ch_stat["chapter_index"] == best_ch_idx:
                            ch_stat["count"] += 1
                            if src == "student_proposal":
                                ch_stat["student_proposal"] += 1
                            elif src in ["ai_generated", "generated_by_gemini"]:
                                ch_stat["ai_generated"] += 1
                            else:
                                ch_stat["official"] += 1
                            break
                else:
                    if course_data["chapters"]:
                        course_data["chapters"][0]["count"] += 1
                        if src == "student_proposal":
                            course_data["chapters"][0]["student_proposal"] += 1
                        elif src in ["ai_generated", "generated_by_gemini"]:
                            course_data["chapters"][0]["ai_generated"] += 1
                        else:
                            course_data["chapters"][0]["official"] += 1

        return web.json_response({"success": True, "stats": stats})
    except Exception as e:
        logger.error(f"Error in get_questions_stats_api: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Test Telegram Group ID
async def test_telegram_group(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        group_id_str = data.get('groupId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        bot = request.app.get('bot')
        if not bot:
            return web.json_response({"success": False, "error": "Bot instance not found"}, status=500)
            
        try:
            group_id = int(group_id_str)
            chat = await bot.get_chat(chat_id=group_id)
            return web.json_response({"success": True, "chat_title": chat.title, "chat_type": chat.type})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)})
            
    except Exception as e:
        logger.error(f"Error testing group: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Resolve a ticket from question_reports
async def resolve_admin_ticket(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        ticket_id = data.get('ticketId')
        admin_reply = data.get('adminReply', '')
        new_status = data.get('status', 'resolved')

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        from config import DATABASE_PATH
        import database as db
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            # Get student user_id to notify them
            async with db_conn.execute(
                "SELECT user_id, first_name, report_type FROM question_reports WHERE id = ?", (ticket_id,)
            ) as cur:
                row = await cur.fetchone()

            await db_conn.execute(
                "UPDATE question_reports SET status = ?, admin_reply = ?, reviewed_at = datetime('now') WHERE id = ?",
                (new_status, admin_reply, ticket_id)
            )
            await db_conn.commit()

            # Insert message into ticket_chat_messages
            if admin_reply:
                admin_name = "الإدارة"
                async with db_conn.execute("SELECT first_name, username FROM admins WHERE telegram_id = ?", (int(user_id),)) as cur:
                    r = await cur.fetchone()
                    if r:
                        admin_name = r["first_name"] or r["username"] or admin_name
                await db.add_ticket_chat_message(
                    ticket_id=int(ticket_id),
                    sender='admin',
                    sender_name=admin_name,
                    message=admin_reply
                )

            # Notify the student via Telegram if reply provided
            if row and admin_reply:
                bot = request.app.get('bot')
                if bot:
                    try:
                        type_labels = {
                            'suggestion': '💡 اقتراحك',
                            'question_error': '🚩 بلاغ الخطأ',
                            'tech': '🔧 مشكلتك التقنية',
                            'other': '📩 رسالتك'
                        }
                        label = type_labels.get(row["report_type"] or "other", "📩 رسالتك")
                        
                        # Force https for WebApp compatibility on Telegram
                        host = request.host
                        webapp_url = f"https://{host}/support.html?view=chat&ticket_id={ticket_id}"
                        
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
                        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 فتح المحادثة (Mini App)", web_app=WebAppInfo(url=webapp_url))]
                        ])
                        
                        await bot.send_message(
                            chat_id=row["user_id"],
                            text=f"📬 رد الإدارة على {label}:\n\n<i>\"{admin_reply}\"</i>",
                            reply_markup=reply_markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify student: {e}")

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error resolving ticket: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Update ticket report type (Triage)
async def update_ticket_type(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        ticket_id = data.get('ticketId')
        new_type = data.get('reportType')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        if not ticket_id or not new_type:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute(
                "UPDATE question_reports SET report_type = ? WHERE id = ?",
                (new_type, int(ticket_id))
            )
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error updating ticket type: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Update ticket tags
async def update_ticket_tags(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        item_id = data.get('itemId')
        item_type = data.get('itemType')
        tags = data.get('tags', [])
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        if not item_id or not item_type:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)
            
        table_map = {
            'report': 'chapter_reports',
            'proposal': 'questions_proposees',
            'ticket': 'question_reports'
        }
        
        table_name = table_map.get(item_type)
        if not table_name:
            return web.json_response({"success": False, "error": "Invalid itemType"}, status=400)
            
        from config import DATABASE_PATH
        import json
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute(
                f"UPDATE {table_name} SET tags = ? WHERE id = ?",
                (json.dumps(tags), item_id)
            )
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error updating ticket tags: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Get all canned responses (templates)
async def get_canned_responses(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        templates = []
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT id, title, category, content FROM canned_responses ORDER BY title ASC") as cur:
                async for r in cur:
                    templates.append({
                        "id": r["id"],
                        "title": r["title"],
                        "category": r["category"],
                        "content": r["content"]
                    })
        return web.json_response({"success": True, "templates": templates})
    except Exception as e:
        logger.error(f"Error loading templates: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Save (Create/Update) canned response
async def save_canned_response(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        template_id = data.get('id')
        title = (data.get('title') or '').strip()
        category = data.get('category', 'other')
        content = (data.get('content') or '').strip()
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        if not title or not content:
            return web.json_response({"success": False, "error": "Missing title or content"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            if template_id:
                await db_conn.execute("""
                    UPDATE canned_responses SET title = ?, category = ?, content = ? WHERE id = ?
                """, (title, category, content, int(template_id)))
            else:
                await db_conn.execute("""
                    INSERT INTO canned_responses (title, category, content) VALUES (?, ?, ?)
                """, (title, category, content))
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Delete canned response
async def delete_canned_response(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        template_id = data.get('id')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        if not template_id:
            return web.json_response({"success": False, "error": "Missing template id"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("DELETE FROM canned_responses WHERE id = ?", (int(template_id),))
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Claim a ticket/report/proposal
async def claim_admin_ticket(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        ticket_id = data.get('ticketId')
        item_type = data.get('itemType', 'ticket')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        if not ticket_id:
            return web.json_response({"success": False, "error": "Missing ticketId"}, status=400)
            
        table_map = {
            'ticket': 'question_reports',
            'report': 'chapter_reports',
            'proposal': 'questions_proposees'
        }
        table_name = table_map.get(item_type, 'question_reports')
        
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            admin_name = "مشرف"
            db_conn.row_factory = aiosqlite.Row
            # 1. Try checking admins table first
            async with db_conn.execute("SELECT first_name, username FROM admins WHERE telegram_id = ?", (int(user_id),)) as cur:
                r = await cur.fetchone()
                if r and (r["first_name"] or r["username"]):
                    admin_name = r["first_name"] or r["username"]
            
            # 2. Try checking users table if still generic
            if admin_name == "مشرف" or not admin_name:
                async with db_conn.execute("SELECT first_name, username FROM users WHERE telegram_id = ?", (int(user_id),)) as cur:
                    r = await cur.fetchone()
                    if r and (r["first_name"] or r["username"]):
                        admin_name = r["first_name"] or r["username"]
                        await db_conn.execute(
                            "UPDATE admins SET first_name = ?, username = ? WHERE telegram_id = ?",
                            (r["first_name"] or "", r["username"] or "", int(user_id))
                        )
            
            # 3. Try checking Telegram Bot API if still generic
            if admin_name == "مشرف" or not admin_name:
                bot = request.app.get('bot')
                if bot:
                    try:
                        chat = await bot.get_chat(chat_id=int(user_id))
                        if chat:
                            admin_name = chat.first_name or chat.username or admin_name
                            await db_conn.execute(
                                "UPDATE admins SET first_name = ?, username = ? WHERE telegram_id = ?",
                                (chat.first_name or "", chat.username or "", int(user_id))
                            )
                    except Exception as tg_err:
                        logger.warning(f"Could not retrieve admin chat info from Telegram in claim_admin_ticket: {tg_err}")
            
            from config import TELEGRAM_ADMIN_IDS
            if admin_name == "مشرف" and (int(user_id) in TELEGRAM_ADMIN_IDS or int(user_id) in [2045194295]):
                admin_name = "Super Admin"
                
            db_id = int(ticket_id) if item_type != 'report' else ticket_id
            if table_name == 'question_reports':
                await db_conn.execute(f"""
                    UPDATE {table_name} SET claimed_by = ?, status = 'in_progress', assigned_admin_id = ? WHERE id = ?
                """, (admin_name, int(user_id), db_id))
            else:
                await db_conn.execute(f"""
                    UPDATE {table_name} SET claimed_by = ?, status = 'in_progress' WHERE id = ?
                """, (admin_name, db_id))
            await db_conn.commit()
            
        return web.json_response({"success": True, "claimedBy": admin_name})
    except Exception as e:
        logger.error(f"Error claiming ticket: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: List all admins
async def get_admins_list(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
            
        admins = []
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT telegram_id AS user_id, role, username, first_name, added_by, added_at, allowed_subjects, visible_sections FROM admins ORDER BY added_at DESC") as cur:
                async for r in cur:
                    admins.append(dict(r))

                    
        return web.json_response({"success": True, "admins": admins})
    except Exception as e:
        logger.error(f"Error listing admins: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Add or Update Admin
async def add_admin_user(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        target_id = data.get('targetId')
        target_role = data.get('role', 'moderator')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
            
        if not target_id:
            return web.json_response({"success": False, "error": "Missing targetId"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute(
                "INSERT INTO admins (telegram_id, role, added_by) VALUES (?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET role = excluded.role",
                (int(target_id), target_role, int(user_id))
            )
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Remove Admin
async def remove_admin_user(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        target_id = data.get('targetId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
            
        if not target_id or int(target_id) == int(user_id):
            return web.json_response({"success": False, "error": "Cannot remove yourself or missing targetId"}, status=400)
            
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("DELETE FROM admins WHERE telegram_id = ?", (int(target_id),))
            await db_conn.commit()
            
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Update admin permissions (subjects + sections)
async def update_admin_permissions(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        target_id = data.get('targetId')
        allowed_subjects = data.get('allowedSubjects')  # None or list like ["aqeeda","fiqh"]
        visible_sections = data.get('visibleSections')  # None or list like ["inbox","questions"]

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
        role = await get_admin_role(user_id)
        if role != "super_admin":
            return web.json_response({"success": False, "error": "Require super_admin role"}, status=403)
        if not target_id:
            return web.json_response({"success": False, "error": "Missing targetId"}, status=400)

        import json as _json
        subjects_json = _json.dumps(allowed_subjects) if allowed_subjects is not None else None
        sections_json = _json.dumps(visible_sections) if visible_sections is not None else None

        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute(
                "UPDATE admins SET allowed_subjects = ?, visible_sections = ? WHERE telegram_id = ?",
                (subjects_json, sections_json, int(target_id))
            )
            await db_conn.commit()
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error updating admin permissions: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Admin API: Custom Views — List accessible views for this admin
async def list_custom_views(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        import json as _json
        uid = int(user_id)
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute(
                """SELECT * FROM admin_custom_views ORDER BY position ASC, created_at ASC"""
            ) as cur:
                rows = await cur.fetchall()

        views = []
        for r in rows:
            vis = r['visibility']
            targets = _json.loads(r['target_ids'] or '[]')
            # Include if: private (own), shared (all), targeted (uid in targets)
            if vis == 'private' and r['created_by'] != uid:
                continue
            if vis == 'targeted' and uid not in targets:
                # super_admin sees all targeted
                role = await get_admin_role(user_id)
                if role != 'super_admin':
                    continue
            views.append({
                'id': r['id'],
                'createdBy': r['created_by'],
                'name': r['name'],
                'icon': r['icon'],
                'filters': _json.loads(r['filters'] or '{}'),
                'visibility': vis,
                'targetIds': targets,
                'position': r['position'],
                'isLocked': bool(r['is_locked']),
                'createdAt': r['created_at'],
            })
        return web.json_response({"success": True, "views": views})
    except Exception as e:
        logger.error(f"Error listing custom views: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Admin API: Custom Views — Save (create or update)
async def save_custom_view(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        role = await get_admin_role(user_id)
        view_id = data.get('id')  # None = create new
        name = data.get('name', 'Vue')
        icon = data.get('icon', '📌')
        filters_obj = data.get('filters', {})
        visibility = data.get('visibility', 'private')
        target_ids = data.get('targetIds', [])
        is_locked = int(data.get('isLocked', False))

        # Only super_admin can create shared/targeted views
        if visibility in ('shared', 'targeted') and role != 'super_admin':
            visibility = 'private'

        import json as _json, uuid as _uuid
        if not view_id:
            view_id = str(_uuid.uuid4())

        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            await db_conn.execute("""
                INSERT INTO admin_custom_views (id, created_by, name, icon, filters, visibility, target_ids, is_locked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    icon = excluded.icon,
                    filters = excluded.filters,
                    visibility = excluded.visibility,
                    target_ids = excluded.target_ids,
                    is_locked = excluded.is_locked
            """, (
                view_id, int(user_id), name, icon,
                _json.dumps(filters_obj),
                visibility,
                _json.dumps(target_ids),
                is_locked
            ))
            await db_conn.commit()
        return web.json_response({"success": True, "id": view_id})
    except Exception as e:
        logger.error(f"Error saving custom view: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Admin API: Custom Views — Delete
async def delete_custom_view(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        view_id = data.get('id')
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        role = await get_admin_role(user_id)
        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute("SELECT * FROM admin_custom_views WHERE id = ?", (view_id,)) as cur:
                view = await cur.fetchone()
            if not view:
                return web.json_response({"success": False, "error": "View not found"}, status=404)
            # Only owner or super_admin can delete; locked views need super_admin
            if view['is_locked'] and role != 'super_admin':
                return web.json_response({"success": False, "error": "Vue verrouillée"}, status=403)
            if view['created_by'] != int(user_id) and role != 'super_admin':
                return web.json_response({"success": False, "error": "Non autorisé"}, status=403)
            await db_conn.execute("DELETE FROM admin_custom_views WHERE id = ?", (view_id,))
            await db_conn.commit()
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error deleting custom view: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Admin API: Custom Views — Reorder
async def reorder_custom_views(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        ordered_ids = data.get('orderedIds', [])  # list of view IDs in desired order
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        from config import DATABASE_PATH
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            for pos, vid in enumerate(ordered_ids):
                await db_conn.execute(
                    "UPDATE admin_custom_views SET position = ? WHERE id = ?", (pos, vid)
                )
            await db_conn.commit()
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error reordering custom views: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# Admin API: Get lesson resources (PDF/Mindmap)
async def get_lesson_resources_api(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        import database as db
        resources = await db.get_lesson_resources(subject, int(lesson_num))
        return web.json_response({
            "success": True, 
            "resources": resources or {"subject": subject, "course_number": int(lesson_num), "mind_map_file_id": None, "summary_file_id": None}
        })
    except Exception as e:
        logger.error(f"Error fetching lesson resources: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Save lesson resources
async def save_lesson_resources_api(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        lesson_num = data.get('lessonNum')
        resource_type = data.get('resourceType') # 'mind_map' or 'summary'
        file_id = data.get('fileId')
        
        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)
            
        import database as db
        await db.save_lesson_resources(subject, int(lesson_num), resource_type, file_id)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error saving lesson resources: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# Admin API: Get media stats for all subjects/lessons
async def get_media_stats_api(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject', 'aqeeda')

        if not await check_admin(user_id):
            return web.json_response({"success": False, "error": "Access denied"}, status=403)

        import database as db
        import json as _json
        import os

        # Normalize subject key for transcripts.json
        subject_normalized = subject.lower().strip()

        # Load transcripts.json to get lesson titles
        transcripts_path = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'transcripts.json')
        lessons_by_num = {}
        if os.path.exists(transcripts_path):
            try:
                with open(transcripts_path, 'r', encoding='utf-8') as f:
                    transcripts = _json.load(f)
                for item in transcripts:
                    item_subject = (item.get('subject') or '').lower().strip()
                    # Normalize: aqeeda = aqeeda, aqida = aqeeda
                    if item_subject in (subject_normalized, subject_normalized.replace('aqida', 'aqeeda')):
                        ln = item.get('lessonNum') or item.get('lesson_num')
                        if ln is not None:
                            lessons_by_num[int(ln)] = item.get('title') or item.get('lesson') or f"درس {ln}"
            except Exception as e:
                logger.warning(f"Could not read transcripts.json: {e}")

        # Get all lessons that have resources in DB for this subject
        resources = await db.get_all_lessons_with_resources(subject_normalized)

        # Merge with transcripts lesson list
        all_lesson_nums = set(lessons_by_num.keys())
        for r in resources:
            all_lesson_nums.add(r['course_number'])

        # Build full detail (include file_ids for display)
        from config import DATABASE_PATH
        import aiosqlite
        lesson_resources_map = {}
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            async with db_conn.execute(
                "SELECT course_number, mind_map_file_id, summary_file_id FROM lesson_resources WHERE subject = ?",
                (subject_normalized,)
            ) as cur:
                rows = await cur.fetchall()
                for row in rows:
                    lesson_resources_map[row['course_number']] = {
                        'mind_map_file_id': row['mind_map_file_id'],
                        'summary_file_id': row['summary_file_id']
                    }

        # Build final sorted list
        lessons_list = []
        for ln in sorted(all_lesson_nums):
            res = lesson_resources_map.get(ln, {})
            lessons_list.append({
                'course_number': ln,
                'title': lessons_by_num.get(ln, f"درس {ln}"),
                'mind_map_file_id': res.get('mind_map_file_id') or '',
                'summary_file_id': res.get('summary_file_id') or '',
                'has_mind_map': bool(res.get('mind_map_file_id')),
                'has_summary': bool(res.get('summary_file_id')),
            })

        # Stats
        mindmaps_ok = sum(1 for l in lessons_list if l['has_mind_map'])
        summaries_ok = sum(1 for l in lessons_list if l['has_summary'])
        mindmaps_missing = len(lessons_list) - mindmaps_ok
        summaries_missing = len(lessons_list) - summaries_ok

        return web.json_response({
            "success": True,
            "lessons": lessons_list,
            "stats": {
                "mindmaps_ok": mindmaps_ok,
                "mindmaps_missing": mindmaps_missing,
                "summaries_ok": summaries_ok,
                "summaries_missing": summaries_missing,
                "total": len(lessons_list)
            }
        })
    except Exception as e:
        logger.error(f"Error in get_media_stats_api: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


# ─── Student Practice & Quiz API Endpoints ───

async def get_student_stats(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        if not user_id:
            return web.json_response({"success": False, "error": "Missing userId"}, status=400)
            
        import database as db
        overall = await db.get_user_overall_stats(int(user_id))
        rems = await db.get_remaining_questions_count_per_subject(int(user_id))
        emojis = await db.get_all_subjects_status_emojis(int(user_id))
        
        # Calculate progression data
        course_progress = []
        detailed_progress = {}
        try:
            course_progress = await db.get_all_progress(int(user_id))
            for sub in ['sira', 'fiqh', 'aqeeda', 'nahw', 'tajweed']:
                lessons_p, themes_p, years_p = await db.get_detailed_subject_progress(int(user_id), sub)
                detailed_progress[sub] = {
                    'lessons': lessons_p,
                    'themes': themes_p,
                    'years': years_p
                }
        except Exception as prog_err:
            logger.error(f"Error calculating progression stats: {prog_err}")

        # Calculate daily streak or default
        user_info = await db.get_user(int(user_id))
        streak = 0
        if user_info:
            from config import DATABASE_PATH
            import aiosqlite
            async with aiosqlite.connect(DATABASE_PATH) as db_conn:
                async with db_conn.execute("""
                    SELECT COUNT(DISTINCT date(answered_at)) FROM quiz_logs WHERE user_id = ?
                """, (int(user_id),)) as cur:
                    row = await cur.fetchone()
                    streak = row[0] if row else 0

        return web.json_response({
            "success": True,
            "overall": overall,
            "remaining": rems,
            "emojis": emojis,
            "streak": streak,
            "preferredName": user_info.get("preferred_name") or user_info.get("first_name") or "طالب" if user_info else "طالب",
            "courseProgress": course_progress,
            "detailedProgress": detailed_progress
        })
    except Exception as e:
        logger.error(f"Error in get_student_stats: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_student_quiz_questions(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        subject = data.get('subject')
        course_numbers = data.get('courseNumbers', [])
        source = data.get('source', 'all') # 'all', 'favorites', 'errors'
        limit = int(data.get('limit', 10))
        
        if not user_id:
            return web.json_response({"success": False, "error": "Missing userId"}, status=400)
            
        import database as db
        from config import DATABASE_PATH
        import aiosqlite
        
        questions = []
        async with aiosqlite.connect(DATABASE_PATH) as db_conn:
            db_conn.row_factory = aiosqlite.Row
            
            if source == 'favorites':
                query = """
                    SELECT q.* FROM user_favorites f
                    JOIN questions q ON f.question_id = q.id
                    WHERE f.user_id = ?
                """
                params = [int(user_id)]
                if subject:
                    query += " AND q.subject = ?"
                    params.append(subject.lower().strip())
                if course_numbers:
                    placeholders = ",".join("?" for _ in course_numbers)
                    query += f" AND q.course_number IN ({placeholders})"
                    params.extend(course_numbers)
                
                query += " ORDER BY random() LIMIT ?"
                params.append(limit)
                async with db_conn.execute(query, params) as cur:
                    rows = await cur.fetchall()
                    questions = [dict(r) for r in rows]
                    
            elif source == 'errors':
                query = """
                    SELECT q.* FROM user_errors e
                    JOIN questions q ON e.question_id = q.id
                    WHERE e.user_id = ?
                """
                params = [int(user_id)]
                if subject:
                    query += " AND q.subject = ?"
                    params.append(subject.lower().strip())
                if course_numbers:
                    placeholders = ",".join("?" for _ in course_numbers)
                    query += f" AND q.course_number IN ({placeholders})"
                    params.extend(course_numbers)
                
                query += " ORDER BY random() LIMIT ?"
                params.append(limit)
                async with db_conn.execute(query, params) as cur:
                    rows = await cur.fetchall()
                    questions = [dict(r) for r in rows]
                    
            else:
                query = "SELECT * FROM questions WHERE 1=1"
                params = []
                if subject:
                    query += " AND subject = ?"
                    params.append(subject.lower().strip())
                if course_numbers:
                    placeholders = ",".join("?" for _ in course_numbers)
                    query += f" AND course_number IN ({placeholders})"
                    params.extend(course_numbers)
                
                # Exclude AI generated if settings say so
                async with db_conn.execute("SELECT value FROM settings WHERE key='disable_ai_for_students'") as cur:
                    row = await cur.fetchone()
                    if row and row[0].lower() == 'true':
                        query += " AND source != 'generated_by_gemini'"
                
                query += " ORDER BY random() LIMIT ?"
                params.append(limit)
                async with db_conn.execute(query, params) as cur:
                    rows = await cur.fetchall()
                    questions = [dict(r) for r in rows]

        favorites_list = await db.get_user_favorites(int(user_id))
        for q in questions:
            q['correct_choice'] = db.get_correct_choice_letter(q)
            q['is_favorite'] = q['id'] in favorites_list

        return web.json_response({"success": True, "questions": questions})
    except Exception as e:
        logger.error(f"Error in get_student_quiz_questions: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def submit_student_quiz_answer(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        question_id = data.get('questionId')
        is_correct = bool(data.get('isCorrect'))
        wrong_answer = data.get('wrongAnswer', '')
        
        if not user_id or not question_id:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)
            
        import database as db
        
        await db.log_quiz_answer(int(user_id), int(question_id), is_correct)
        await db.update_question_progress(int(user_id), int(question_id), is_correct)
        
        q = await db.get_question_by_id(int(question_id))
        if q:
            subject = q.get('subject', 'fiqh')
            if is_correct:
                await db.remove_error(int(user_id), int(question_id))
            else:
                await db.add_error(int(user_id), int(question_id), subject, wrong_answer)
                
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in submit_student_quiz_answer: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def toggle_student_favorite(request):
    try:
        data = await request.json()
        user_id = data.get('userId')
        question_id = data.get('questionId')
        is_fav = bool(data.get('isFavorite'))
        
        if not user_id or not question_id:
            return web.json_response({"success": False, "error": "Missing parameters"}, status=400)
            
        import database as db
        q = await db.get_question_by_id(int(question_id))
        if not q:
            return web.json_response({"success": False, "error": "Question not found"}, status=404)
            
        subject = q.get('subject', 'fiqh')
        if is_fav:
            success = await db.add_favorite(int(user_id), int(question_id), subject)
        else:
            success = await db.remove_favorite(int(user_id), int(question_id))
            
        return web.json_response({"success": success})
    except Exception as e:
        logger.error(f"Error in toggle_student_favorite: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def start_web_server(bot: Bot):
    app = web.Application(middlewares=[cors_middleware])
    app['bot'] = bot
    
    app.router.add_get('/', handle_index)
    app.router.add_get('/interactive.html', handle_interactive)
    app.router.add_get('/admin', handle_admin)
    app.router.add_get('/admin.html', handle_admin)
    app.router.add_get('/admin-bot', handle_admin_bot)
    app.router.add_get('/admin-bot.html', handle_admin_bot)
    app.router.add_get('/admin-support', handle_admin_support)
    app.router.add_get('/admin-support.html', handle_admin_support)
    app.router.add_get('/admin.css', handle_admin_css)
    app.router.add_get('/admin.js', handle_admin_js)
    app.router.add_get('/admin-late.js', handle_admin_late_js)
    app.router.add_get('/logo.png', handle_logo_png)
    app.router.add_get('/search', handle_search)
    app.router.add_get('/search.html', handle_search)
    app.router.add_get('/transcripts.json', handle_transcripts)
    app.router.add_get('/quran_db.json', handle_quran)
    app.router.add_get('/support', handle_support)
    app.router.add_get('/support.html', handle_support)
    app.router.add_get('/api/tickets/student', get_student_tickets)
    app.router.add_post('/api/tickets/student', get_student_tickets)
    app.router.add_get('/api/tickets/{ticket_id}/messages', get_ticket_messages_api)
    app.router.add_post('/api/tickets/{ticket_id}/reply', reply_ticket_message_api)
    app.router.add_get('/api/triage/match', handle_triage_match)
    app.router.add_post('/api/triage/match', handle_triage_match)
    app.router.add_post('/report-chapter', report_chapter)
    # Student Practice & Quiz API routes
    app.router.add_post('/api/student/stats', get_student_stats)
    app.router.add_post('/api/student/quiz/setup', get_student_quiz_questions)
    app.router.add_post('/api/student/quiz/submit', submit_student_quiz_answer)
    app.router.add_post('/api/student/favorites/toggle', toggle_student_favorite)
    app.router.add_post('/admin/reports', get_admin_reports)
    app.router.add_post('/admin/dashboard-stats', get_admin_dashboard_stats_api)
    app.router.add_post('/admin/resolve-report', resolve_admin_report)
    app.router.add_post('/admin/edit-chapter', edit_course_chapter)
    app.router.add_post('/admin/save-thematic-blocks', save_lesson_axes)
    app.router.add_post('/admin/question', get_admin_question)
    app.router.add_post('/admin/update-question', update_admin_question)
    app.router.add_post('/admin/delete-question', delete_admin_question)
    app.router.add_post('/admin/toggle-question-active', toggle_question_active_api)
    app.router.add_post('/admin/proposals', get_admin_proposals)
    app.router.add_post('/admin/resolve-proposal', resolve_admin_proposal)
    app.router.add_post('/admin/update-proposal', update_admin_proposal)
    app.router.add_post('/admin/tickets', get_admin_tickets)
    app.router.add_post('/admin/resolve-ticket', resolve_admin_ticket)
    app.router.add_post('/admin/test-group', test_telegram_group)
    app.router.add_post('/admin/broadcast', admin_broadcast)
    app.router.add_post('/admin/questions-list', admin_questions_list)
    app.router.add_post('/admin/questions/stats', get_questions_stats_api)
    app.router.add_post('/admin/info', get_admin_info)
    app.router.add_post('/admin/settings', get_admin_settings)
    app.router.add_post('/admin/update-setting', update_admin_setting)
    app.router.add_post('/admin/purge-old-tickets', purge_old_tickets)
    app.router.add_post('/admin/students', get_admin_students)
    app.router.add_post('/admin/student-details', get_admin_student_details)
    app.router.add_post('/api/tickets/external', receive_external_ticket)
    app.router.add_post('/admin/list-admins', get_admins_list)
    app.router.add_post('/admin/add-admin', add_admin_user)
    app.router.add_post('/admin/remove-admin', remove_admin_user)
    app.router.add_post('/admin/update-ticket-type', update_ticket_type)
    app.router.add_post('/admin/update-ticket-tags', update_ticket_tags)
    app.router.add_post('/admin/canned-responses', get_canned_responses)
    app.router.add_get('/api/media', get_media)
    app.router.add_post('/admin/canned-responses/save', save_canned_response)
    app.router.add_post('/admin/canned-responses/delete', delete_canned_response)
    app.router.add_post('/admin/tickets/claim', claim_admin_ticket)
    app.router.add_post('/admin/save-full-transcript', save_full_transcript)
    app.router.add_post('/admin/questions/generate-ia', generate_questions_ia)
    app.router.add_post('/admin/questions/save-bulk', save_bulk_questions)
    app.router.add_post('/admin/lesson-resources', get_lesson_resources_api)
    app.router.add_post('/admin/save-lesson-resources', save_lesson_resources_api)
    app.router.add_post('/admin/media/stats', get_media_stats_api)
    # Phase 2 — Admin permissions by subject/section
    app.router.add_post('/admin/update-permissions', update_admin_permissions)
    # Phase 3 — Shared custom views (DB-backed)
    app.router.add_post('/admin/custom-views/list', list_custom_views)
    app.router.add_post('/admin/custom-views/save', save_custom_view)
    app.router.add_post('/admin/custom-views/delete', delete_custom_view)
    app.router.add_post('/admin/custom-views/reorder', reorder_custom_views)

    # Expose web server on PORT environment variable, or fallback to 8082 (to avoid 8080 conflicts)
    port = int(os.environ.get("PORT", 8082))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    logger.info(f"🌐 [Backup Web Server] launched on port {port}")
    await site.start()
    
    while True:
        await asyncio.sleep(3600)

async def on_startup(bot: Bot):
    logger.info("Initializing database on startup...")
    await db.init_db()
    logger.info("Database initialized.")
    
    # Set bot description (shown before starting the bot)
    welcome_description = (
        "مرحباً بك في البوت البديل لأكاديمية الباجي! 🎓\n\n"
        "هذا البوت مخصص لمساعدتك في اختبار معلوماتك الشرعية ومراجعة الدروس "
        "وتتبع تقدمك الدراسي بطريقة تفاعلية وميسرة.\n\n"
        "اضغط على زر البدء (Start) للبدء في رحلتك التعليمية!"
    )
    welcome_short_description = (
        "البوت البديل لأكاديمية الباجي للأسئلة المنهجية واختبار المعلومات الشرعية. 🎓"
    )
    try:
        await bot.set_my_description(welcome_description)
        await bot.set_my_description(welcome_description, language_code="ar")
        await bot.set_my_description(welcome_description, language_code="fr")
        
        await bot.set_my_short_description(welcome_short_description)
        await bot.set_my_short_description(welcome_short_description, language_code="ar")
        await bot.set_my_short_description(welcome_short_description, language_code="fr")
        logger.info("Bot descriptions updated for default, 'ar' and 'fr' language codes.")
    except Exception as e:
        logger.warning(f"Could not set bot description: {e}")

class AccessCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            
        if user_id:
            from handlers.admin import is_admin
            is_adm = is_admin(user_id)
            
            # Check Maintenance Mode
            maint_active = await db.get_setting("maintenance_mode", "False")
            if maint_active == "True" and not is_adm:
                maint_msg = await db.get_setting("maintenance_message", "🚧 البوت في وضع الصيانة مؤقتاً. سيعود قريباً بإذن الله.")
                if isinstance(event, Message):
                    await event.answer(maint_msg, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer(maint_msg, show_alert=True)
                return
                
            # Check Ban
            is_banned = await db.is_user_banned(user_id)
            if is_banned and not is_adm:
                ban_text = "🚫 <b>تمت بنجاح معالجة حسابك. هذا الحساب محظور حالياً من استخدام البوت. يرجى التواصل مع الإدارة للمساعدة.</b>"
                if isinstance(event, Message):
                    await event.answer(ban_text, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer(ban_text, show_alert=True)
                return
                
        return await handler(event, data)

async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is missing! Exiting...")
        return

    # Initialize bot and dispatcher
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Start Web Server in concurrent background task
    asyncio.create_task(start_web_server(bot))
    
    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares
    dp.message.outer_middleware(AccessCheckMiddleware())
    dp.callback_query.outer_middleware(AccessCheckMiddleware())

    # Include handlers
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(fav_err_router)
    dp.include_router(support_router)
    dp.include_router(admin_router)
    dp.include_router(revision_router)

    # Register startup hook
    dp.startup.register(on_startup)

    # ─── RAILWAY ZERO-DOWNTIME CONFLICT RESOLUTION ───
    INSTANCE_ID = str(uuid.uuid4())
    logger.info(f"Démarrage de l'instance courante avec ID: {INSTANCE_ID}")
    
    async def watch_for_new_instance():
        while True:
            await asyncio.sleep(5)
            try:
                from config import DATABASE_PATH
                if not os.path.exists(DATABASE_PATH):
                    continue
                async with aiosqlite.connect(DATABASE_PATH) as db_conn:
                    async with db_conn.execute("SELECT value FROM settings WHERE key = 'current_instance_id'") as cur:
                        row = await cur.fetchone()
                        if row and row[0] and row[0] != INSTANCE_ID:
                            logger.warning(f"🚨 NOUVELLE INSTANCE DÉTECTÉE ({row[0]}). Arrêt du polling pour éviter les conflits Telegram !")
                            await dp.stop_polling()
                            break
            except Exception:
                pass

    try:
        from config import DATABASE_PATH
        if os.path.exists(DATABASE_PATH):
            async with aiosqlite.connect(DATABASE_PATH) as db_conn:
                await db_conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('current_instance_id', INSTANCE_ID))
                await db_conn.commit()
    except Exception as e:
        logger.error(f"Failed to register instance ID: {e}")
        
    asyncio.create_task(watch_for_new_instance())
    # ──────────────────────────────────────────────────

    logger.info("Starting Telegram Backup Bot polling...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
