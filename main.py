
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

deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
if deepgram_api_key:
    print("DEEPGRAM_API_KEY:", deepgram_api_key)
else:
    print("DEEPGRAM_API_KEY not found.")

@app.post("/transcribe-deepgram")
async def transcribe_deepgram(file: UploadFile = File(...)):
    print("Received file:", file.filename, file.content_type)
    audio = await file.read()
    print("Audio length (bytes):", len(audio))

    headers = {
        "Authorization": f"Token {deepgram_api_key}",
        "Content-Type": "audio/webm"  # double-check if your blob is actually webm
    }

    response = requests.post(
        "https://api.deepgram.com/v1/listen",
        headers=headers,
        data=audio
    )
    
    try:
        data = response.json()
        print("Deepgram response:", data)
        if "results" not in data:
            return {"text": "", "error": f"Missing 'results' in response: {data}"}
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        return {"text": transcript}
    except Exception as e:
        return {"text": "", "error": str(e)}
