import asyncio
import aiosqlite

DATABASE_PATH = r"c:\Users\Houssam\Desktop\Telegram-Bot-Assets\telegram-bot-backup\backup_bot.db"

async def inject_sira_14():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Delete old
        await db.execute("DELETE FROM course_chapters WHERE subject='sira' AND course_number=14")
        
        # We need to delete old questions too, but we need chapter IDs for that.
        # It's fine, they will just be orphaned or we can clean them up.
        
        chapters_data = [
            (
                "sira", 14, 1,
                "Contexte historique et sortie de Médine",
                "L'an **2 de l'Hégire** marque un tournant. Après des années de persécutions à La Mecque et la confiscation de leurs biens, les musulmans sont enfin autorisés à se défendre.\n\nLe Prophète (ﷺ) apprend qu'une grande caravane de Quraysh, dirigée par ||Abou Soufyan||, revient de Syrie. Cette caravane représente une grande partie de l'économie mecquoise, financée en partie par les biens volés aux émigrés (Mouhajiroun).",
                "Quand la Bataille de Badr a-t-elle eu lieu ?",
                "En l'an 1 de l'Hégire",
                "En l'an 2 de l'Hégire",
                "En l'an 3 de l'Hégire",
                "En l'an 4 de l'Hégire",
                "b",
                "La bataille s'est déroulée pendant le mois de Ramadan de l'an 2 de l'Hégire."
            ),
            (
                "sira", 14, 2,
                "Le changement de plan divin",
                "L'objectif initial était uniquement d'intercepter la caravane. Cependant, ||Abou Soufyan|| a appris l'arrivée des musulmans et a envoyé un messager à La Mecque pour demander des renforts.\n\nL'armée mecquoise, dirigée par **Abou Jahl**, décide de marcher vers Badr, non seulement pour protéger la caravane (qui a réussi à s'enfuir par la côte), mais pour **écraser définitivement** les musulmans et montrer leur force à toute l'Arabie.",
                "Quel était l'objectif initial de l'armée mecquoise en sortant de La Mecque ?",
                "Aller prier à Jérusalem",
                "Protéger la caravane d'Abou Soufyan et détruire les musulmans",
                "Faire du commerce avec l'Égypte",
                "Signer un traité de paix",
                "b",
                "L'armée mecquoise voulait protéger la caravane mais Abou Jahl a insisté pour aller à Badr et intimider toute l'Arabie."
            ),
            (
                "sira", 14, 3,
                "La consultation des compagnons (Choura)",
                "Lorsque le Prophète (ﷺ) a appris que l'armée de Quraysh approchait, il a réuni ses compagnons pour faire la **Choura** (consultation). \n\nIl était crucial d'avoir leur avis car le pacte d'Al-Aqaba engageait les Ansars à le défendre *uniquement* à l'intérieur de ||Médine||.\n\nLe Prophète (ﷺ) attendait surtout la réponse des **Ansars**, car ils représentaient la majorité de l'armée.",
                "Pourquoi le Prophète (ﷺ) insistait-il pour entendre l'avis des Ansars avant Badr ?",
                "Parce qu'ils étaient les plus riches.",
                "Parce que le pacte d'Al-Aqaba ne les engageait à combattre qu'à l'intérieur de Médine.",
                "Parce qu'il doutait de leur foi.",
                "Parce qu'ils connaissaient mieux le terrain de Badr.",
                "b",
                "Les Ansars s'étaient engagés à le protéger comme leurs propres familles, mais seulement au sein de leur ville. Partir en guerre offensive nécessitait un nouvel accord."
            ),
            (
                "sira", 14, 4,
                "La stratégie militaire de Hubab ibn al-Moundhir",
                "Arrivés à Badr, le Prophète (ﷺ) choisit un campement. Le compagnon **Hubab ibn al-Moundhir** demanda : *\"Ô Messager d'Allah, cet endroit t'a-t-il été inspiré par Allah ou est-ce une stratégie de guerre ?\"*\n\nLe Prophète répondit que c'était une stratégie. Hubab suggéra alors de se placer près du puits le plus proche de l'ennemi et de ||boucher les autres puits||, afin de priver l'armée mecquoise d'eau. Le Prophète (ﷺ) accepta immédiatement cette brillante idée.",
                "Quelle fut la stratégie suggérée par Hubab ibn al-Moundhir ?",
                "Attaquer la nuit",
                "Se cacher dans les montagnes",
                "S'installer près du puits principal et boucher les autres",
                "Se rendre sans combattre",
                "c",
                "Le contrôle de l'eau (les puits de Badr) fut un avantage stratégique déterminant pour les musulmans."
            )
        ]
        
        for ch in chapters_data:
            subj, c_num, ch_idx, title, content, q_text, ca, cb, cc, cd, correct, expl = ch
            
            cursor = await db.execute(
                "INSERT INTO course_chapters (subject, course_number, chapter_index, title, content, vocabulary_spoilers) VALUES (?, ?, ?, ?, ?, ?)",
                (subj, c_num, ch_idx, title, content, "")
            )
            ch_id = cursor.lastrowid
            
            await db.execute(
                "INSERT INTO course_chapter_questions (chapter_id, question, choice_a, choice_b, choice_c, choice_d, correct_answer, explanation) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ch_id, q_text, ca, cb, cc, cd, correct, expl)
            )
            
        await db.commit()

if __name__ == '__main__':
    asyncio.run(inject_sira_14())
    print("Simulation data injected.")
