
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This will work in Railway without python-dotenv
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

# For local development, you could add this (optional):
if not deepgram_api_key and os.path.exists(".env"):
    from dotenv import load_dotenv  # Only import if needed
    load_dotenv()
    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

if deepgram_api_key:
    print("DEEPGRAM_API_KEY:", deepgram_api_key)
else:
    print("DEEPGRAM_API_KEY not found.")

@app.post("/transcribe-deepgram")
async def transcribe_deepgram(file: UploadFile = File(...)):
    audio = await file.read()
    print(f"Audio size: {len(audio)} bytes, Content-Type: {file.content_type}")

    headers = {
        "Authorization": f"Token {deepgram_api_key}",
        "Content-Type": file.content_type or "audio/webm"
    }

    # Minimal parameters for Cantonese
    params = {
        "language": "zh-HK",  # Use "zh-HK" for Cantonese
        "punctuate": "true",
        "model": "nova-2",  # Use "nova-2" for Cantonese
        "smart_format": "true",
        "interim_results": "false",  # Set to True if you want real-time results
    }

    response = requests.post(
        "https://api.deepgram.com/v1/listen",
        headers=headers,
        params=params,
        data=audio
    )
    
    data = response.json()
    print("Full Deepgram response:", data)

    if "results" not in data:
        return {
            "text": "",
            "error": "Deepgram returned no results",
            "full_response": data,
            "debug_info": {
                "audio_size": len(audio),
                "content_type": file.content_type,
                "params_used": params
            }
        }

    transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    return {"text": transcript}

