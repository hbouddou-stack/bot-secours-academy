import sqlite3
import json

def check_sira_explanations():
    conn = sqlite3.connect('backup_bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, question, explanation FROM questions WHERE subject = 'sira'")
    rows = cursor.fetchall()
    
    missing_quotes = []
    missing_sources = []
    
    for row in rows:
        expl = row['explanation']
        if not expl:
            continue
            
        has_cit = "📖" in expl or "قول الشيخ" in expl
        has_src = "📍" in expl or "المصدر" in expl
        has_ped = "💡" in expl or "التفسير التربوي" in expl
        
        if not has_cit:
            missing_quotes.append({'id': row['id'], 'expl': expl[:100] + '...'})
        if not has_src:
            missing_sources.append({'id': row['id']})
            
    print(f"Total Sira Questions: {len(rows)}")
    print(f"Missing Quotes: {len(missing_quotes)}")
    print(f"Missing Sources: {len(missing_sources)}")
    
    if missing_quotes:
        print("\nSample of missing quotes explanations:")
        for q in missing_quotes[:5]:
            print(f"ID: {q['id']}")
            print(q['expl'])
            print("-" * 40)

if __name__ == '__main__':
    check_sira_explanations()
