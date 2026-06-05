import sqlite3
import re

db = sqlite3.connect('backup_bot.db')
c = db.cursor()
c.execute("SELECT id, explanation, source FROM questions WHERE subject='tajweed'")
rows = c.fetchall()

updated_count = 0

for row in rows:
    qid, expl, source = row
    changed = False
    
    # Fix explanation
    if expl:
        m_expl = re.search(r'الدرس (\d+)', expl)
        if m_expl:
            old_num = int(m_expl.group(1))
            new_num = old_num - 1 if old_num < 20 else old_num - 2
            new_expl = re.sub(rf'الدرس {old_num}', f'الدرس {new_num}', expl)
            if new_expl != expl:
                expl = new_expl
                changed = True
                
    # Fix source
    if source:
        m_source = re.search(r'الدرس (\d+)', source)
        if m_source:
            old_num = int(m_source.group(1))
            new_num = old_num - 1 if old_num < 20 else old_num - 2
            new_source = re.sub(rf'الدرس {old_num}', f'الدرس {new_num}', source)
            if new_source != source:
                source = new_source
                changed = True
                
    if changed:
        c.execute("UPDATE questions SET explanation=?, source=? WHERE id=?", (expl, source, qid))
        updated_count += 1

db.commit()
print(f"Updated {updated_count} questions.")
db.close()
