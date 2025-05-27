
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

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

@app.post("/transcribe-deepgram")
async def transcribe_deepgram(file: UploadFile = File(...)):
    audio = await file.read()
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/webm"
    }
    response = requests.post(
        "https://api.deepgram.com/v1/listen",
        headers=headers,
        data=audio
    )
    try:
        data = response.json()
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        return {"text": transcript}
    except Exception as e:
        return {"text": "", "error": str(e)}
