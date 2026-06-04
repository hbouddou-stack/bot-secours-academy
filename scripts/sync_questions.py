import os
import sys
import sqlite3
import asyncio
import logging
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Ensure parent directory is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DATABASE_PATH, MAIN_DATABASE_PATH, MAIN_CREDENTIALS_PATH, GOOGLE_SHEET_ID, GOOGLE_API_KEY
from database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("sync_questions")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_sheets_service():
    if os.path.exists(MAIN_CREDENTIALS_PATH):
        try:
            creds = service_account.Credentials.from_service_account_file(
                MAIN_CREDENTIALS_PATH, scopes=SCOPES)
            return build('sheets', 'v4', credentials=creds, cache_discovery=False)
        except Exception as e:
            logger.error(f"Error loading service account from credentials.json: {e}")
    return None

async def fetch_gsheet_questions():
    if not GOOGLE_SHEET_ID:
        logger.warning("GOOGLE_SHEET_ID missing in configuration. Skipping Google Sheets sync.")
        return []

    try:
        service = get_sheets_service()
        if not service and GOOGLE_API_KEY:
            service = build('sheets', 'v4', developerKey=GOOGLE_API_KEY, cache_discovery=False)
            
        if not service:
            logger.warning("No Google Sheets service could be initialized (missing credentials.json and API key).")
            return []
            
        spreadsheet = await asyncio.to_thread(
            service.spreadsheets().get(spreadsheetId=GOOGLE_SHEET_ID).execute
        )
        sheets_in_file = [s['properties']['title'] for s in spreadsheet.get('sheets', [])]
        
        mapping = {
            "fiqh":    ["fiqh", "الفقه", "فقه", "الفقيه"],
            "sira":    ["sira", "السيرة", "سيرة", "السيرة النبوية"],
            "nahw":    ["nahw", "النحو", "نحو", "قواعد"],
            "aqeeda":  ["aqeeda", "العقيدة", "عقيدة", "التوحيد", "التوحيد والعقيدة"]
        }
        
        all_questions = []
        for key, aliases in mapping.items():
            actual_sheet_name = next((s for s in sheets_in_file if s.strip().lower() in aliases or s.strip() in aliases), None)
            if not actual_sheet_name:
                continue
            range_name = f"{actual_sheet_name}!A2:L"
            try:
                result = await asyncio.to_thread(
                    service.spreadsheets().values().get(spreadsheetId=GOOGLE_SHEET_ID, range=range_name).execute
                )
                values = result.get('values', [])
                sheet_count = 0
                for row in values:
                    if len(row) < 9:
                        continue
                    try:
                        q = {
                            "subject": key.lower().strip(),
                            "course_number": int(row[8]) if len(row) > 8 and str(row[8]).strip().isdigit() else 0,
                            "course_name": str(row[7]).strip() if len(row) > 7 else "",
                            "question": str(row[6]).strip() if len(row) > 6 else "",
                            "choice_a": str(row[5]).strip() if len(row) > 5 else "",
                            "choice_b": str(row[4]).strip() if len(row) > 4 else "",
                            "choice_c": str(row[3]).strip() if len(row) > 3 else "",
                            "choice_d": str(row[2]).strip() if len(row) > 2 else "",
                            "correct_answer": str(row[1]).strip().upper() if len(row) > 1 else "A",
                            "explanation": str(row[0]).strip() if len(row) > 0 else "",
                            "theme": str(row[9]).strip() if len(row) > 9 else "",
                            "hijra_year": int(row[10]) if len(row) > 10 and str(row[10]).strip().isdigit() else None,
                            "source": "gsheet"
                        }
                        if q["subject"] == "sira" and q["hijra_year"] is None:
                            import re
                            m = re.search(r'السنة\s*(\d+)', q["course_name"])
                            if m:
                                q["hijra_year"] = int(m.group(1))
                        if q["question"]:
                            all_questions.append(q)
                            sheet_count += 1
                    except:
                        continue
                logger.info(f"Fetched {sheet_count} questions from Google Sheet tab '{actual_sheet_name}'.")
            except Exception as e:
                logger.error(f"Error fetching sheet tab {actual_sheet_name}: {e}")
                
        return all_questions
    except Exception as e:
        logger.error(f"Google Sheets API Error: {e}")
        return []

async def sync_from_local_db():
    logger.info(f"Syncing questions from local main DB: {MAIN_DATABASE_PATH}")
    if not os.path.exists(MAIN_DATABASE_PATH):
        logger.error(f"Main database file not found at: {MAIN_DATABASE_PATH}")
        return False
        
    try:
        src_conn = sqlite3.connect(MAIN_DATABASE_PATH)
        src_conn.row_factory = sqlite3.Row
        src_cursor = src_conn.cursor()
        
        src_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='official_questions'")
        if not src_cursor.fetchone():
            logger.error("official_questions table not found in main DB!")
            src_conn.close()
            return False
            
        src_cursor.execute("PRAGMA table_info(official_questions)")
        src_cols = [c[1] for c in src_cursor.fetchall()]
        has_hijra = "hijra_year" in src_cols
        has_theme = "theme" in src_cols
        
        select_fields = [
            "id", "subject", "course_number", "course_name", "question", 
            "choice_a", "choice_b", "choice_c", "choice_d", "correct_answer", 
            "explanation", "source", "created_at"
        ]
        if has_hijra:
            select_fields.append("hijra_year")
        if has_theme:
            select_fields.append("theme")
            
        fields_str = ", ".join(select_fields)
        src_cursor.execute(f"SELECT {fields_str} FROM official_questions WHERE subject IN ('sira', 'fiqh', 'nahw', 'aqeeda')")
        rows = src_cursor.fetchall()
        logger.info(f"Found {len(rows)} official questions in main DB.")
        
        official_ids = [r['id'] for r in rows]
        
        dest_conn = sqlite3.connect(DATABASE_PATH)
        dest_cursor = dest_conn.cursor()
        dest_cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Cleanup non-official questions in backup DB
        if official_ids:
            placeholders = ",".join("?" for _ in official_ids)
            dest_cursor.execute(f"DELETE FROM questions WHERE id NOT IN ({placeholders})", tuple(official_ids))
            dest_conn.commit()
        
        dest_cursor.execute("PRAGMA table_info(questions)")
        dest_cols = [c[1] for c in dest_cursor.fetchall()]
        
        insert_fields = [
            "id", "subject", "course_number", "course_name", "question", 
            "choice_a", "choice_b", "choice_c", "choice_d", "correct_answer", 
            "explanation", "source", "created_at"
        ]
        if "hijra_year" in dest_cols and has_hijra:
            insert_fields.append("hijra_year")
        if "theme" in dest_cols and has_theme:
            insert_fields.append("theme")
            
        insert_fields_str = ", ".join(insert_fields)
        placeholders_query = ", ".join("?" for _ in insert_fields)
        insert_query = f"INSERT OR REPLACE INTO questions ({insert_fields_str}) VALUES ({placeholders_query})"
        
        inserted_count = 0
        for r in rows:
            params = [
                r['id'], r['subject'], r['course_number'], r['course_name'], r['question'],
                r['choice_a'], r['choice_b'], r['choice_c'], r['choice_d'], r['correct_answer'],
                r['explanation'], r['source'] or 'official', r['created_at']
            ]
            if "hijra_year" in dest_cols and has_hijra:
                params.append(r['hijra_year'])
            if "theme" in dest_cols and has_theme:
                params.append(r['theme'])
                
            dest_cursor.execute(insert_query, tuple(params))
            inserted_count += 1
            
        dest_conn.commit()
        dest_conn.close()
        src_conn.close()
        
        logger.info(f"Successfully synced {inserted_count} official questions from main DB.")
        return True
    except Exception as e:
        logger.error(f"Error during local DB sync: {e}", exc_info=True)
        return False

async def main():
    logger.info("Initializing backup database schema...")
    await init_db()
    
    # 1. Sync from local DB only (restricted to official questions)
    db_success = await sync_from_local_db()
    
    logger.info("Synchronization process completed.")

if __name__ == "__main__":
    asyncio.run(main())
