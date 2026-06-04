import os

transcripts_dir = os.path.abspath("../telegram-bot/lessons/transcripts/nahw")
if os.path.exists(transcripts_dir):
    for f_name in os.listdir(transcripts_dir):
        f_path = os.path.join(transcripts_dir, f_name)
        with open(f_path, "r", encoding="utf-8") as f:
            content = f.read()
            for line in content.splitlines():
                if "http" in line or "youtube" in line or "youtu.be" in line:
                    print(f"Found URL in {f_name}: {line}")
print("Done searching.")
