import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(dotenv_path='telegram-bot-backup/.env')
api_key = os.getenv("GOOGLE_API_KEY")
print("API KEY:", api_key[:10] if api_key else "None")
genai.configure(api_key=api_key)

print("Listing models:")
try:
    for m in genai.list_models():
        print(m.name, m.supported_generation_methods)
except Exception as e:
    print("Error listing:", e)
