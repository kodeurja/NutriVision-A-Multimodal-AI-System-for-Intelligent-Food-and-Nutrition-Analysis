import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Available Models:")
try:
    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    with open('models_list.txt', 'w') as f:
        f.write("\n".join(models))
    print("Models written to models_list.txt")
except Exception as e:
    with open('models_list.txt', 'w') as f:
        f.write(f"Error: {e}")
