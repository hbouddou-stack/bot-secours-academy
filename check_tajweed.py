import sqlite3
import json
import re

db = sqlite3.connect('backup_bot.db')
c = db.cursor()
c.execute("SELECT id, course_number, explanation, source FROM questions WHERE subject='tajweed'")
rows = c.fetchall()

links_by_old_course = {}

for row in rows:
    qid, cnum, expl, source = row
    m = re.search(r'الدرس (\d+)', expl)
    link_m = re.search(r'href="([^"]+)"', expl)
    if m and link_m:
        old_num = int(m.group(1))
        link = link_m.group(1)
        base_link = link.split('&')[0]
        if old_num not in links_by_old_course:
            links_by_old_course[old_num] = set()
        links_by_old_course[old_num].add(base_link)

for k in links_by_old_course:
    links_by_old_course[k] = list(links_by_old_course[k])

with open('output.json', 'w', encoding='utf-8') as f:
    json.dump(links_by_old_course, f, ensure_ascii=False, indent=2)
