import google.generativeai as genai
from app.core.config import settings
import os

# Manually load env if needed, but app.core.config should handle it if .env is correct
# We'll assume settings loads correctly.

if not settings.GEMINI_API_KEY:
    print("GEMINI_API_KEY not set")
else:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    print("Listing models...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
    except Exception as e:
        print(f"Error: {e}")
