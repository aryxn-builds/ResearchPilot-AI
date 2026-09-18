import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ["GEMINI_API_KEY"]

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)
models = response.json().get("models", [])
for m in models:
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(m.get("name"))
