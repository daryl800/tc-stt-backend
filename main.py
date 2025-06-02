from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64
import json
import os
import traceback  # for better error debugging

app = FastAPI()

# Enable CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust to your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tencent Cloud credentials from environment variables
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

if not TENCENT_SECRET_ID or not TENCENT_SECRET_KEY:
    print("[ERROR] Tencent Cloud credentials are not set in environment variables.")
else:
    print("[INFO] Tencent Cloud credentials loaded.")

@app.get("/")
def read_root():
    return {"message": "Tecent ASR sync version backend is running"}

@app.post("/transcribe-cantonese")
async def transcribe_sync(audio: UploadFile = File(...)):
    try:
        print(f"[INFO] Received file: {audio.filename}")

        # Read the audio file bytes and encode to base64
        audio_bytes = await audio.read()
        print(f"[INFO] Read {len(audio_bytes)} bytes from file.")

        audio_base64 = base64.b64encode(audio_bytes).decode()

        # Extract file extension (e.g., "webm" from "audio.webm")
        voice_format = audio.filename.split(".")[-1].lower()
        print(f"[INFO] Detected audio format: {voice_format}")

        # Create Tencent credential and client
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")

        # Prepare the synchronous recognition request
        req = models.SentenceRecognitionRequest()

        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_yue",  
            "SourceType": 1,
            "VoiceFormat": voice_format,
            "UsrAudioKey": "test-key",
            "Data": audio_base64,
        }

        print("[INFO] Sending transcription request to Tencent Cloud...")
        req.from_json_string(json.dumps(params))
        resp = client.SentenceRecognition(req)

        print(f"[INFO] Transcription result: {resp.Result}")
        return {"transcription": resp.Result}

    except Exception as e:
        print("[ERROR] Transcription failed:")
        traceback.print_exc()
        return {"error": str(e)}
