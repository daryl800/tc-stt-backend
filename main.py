from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64
import json
import os

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

@app.post("/transcribe-cantonese")
async def transcribe_sync(audio: UploadFile = File(...)):
    try:
        # Read the audio file bytes and encode to base64
        audio_bytes = await audio.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()

        # Create Tencent credential and client
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")  # region

        # Prepare the synchronous recognition request
        req = models.SentenceRecognitionRequest()

        # Extract file extension (e.g., "webm" from "audio.webm")
        voice_format = audio.filename.split(".")[-1].lower()

        params = {
            "ProjectId": "0",
            "SubServiceType": 2,
            "EngSerViceType": "16k_yue",  
            "SourceType": 1,  # 1 = data in base64
            "VoiceFormat": voice_format,  # match your audio format
            "UsrAudioKey": "test-key",
            "Data": audio_base64,
        }

        req.from_json_string(json.dumps(params))

        # Call the synchronous recognition API
        resp = client.SentenceRecognition(req)
        return {"transcription": resp.Result}

    except Exception as e:
        return {"error": str(e)}
