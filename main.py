
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

from fastapi import FastAPI, File, UploadFile
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64

app = FastAPI()

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from Tencent backend"}


@app.post("/transcribe-tencent")
async def transcribe_tencent(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    audio_base64 = base64.b64encode(audio_bytes).decode()

    cred = credential.Credential("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY")  # Replace with your actual Tencent Cloud credentials
    client = asr_client.AsrClient(cred, "ap-hongkong")

    req = models.CreateRecTaskRequest()
    params = {
        "EngineModelType": "16k_zh",  # or 16k_en, 16k_ca for Cantonese
        "ChannelNum": 1,
        "ResTextFormat": 0,
        "SourceType": 1,
        "Data": audio_base64,
        "DataLen": len(audio_bytes)
    }
    req.from_json_string(json.dumps(params))

    resp = client.CreateRecTask(req)
    return {"task_id": resp.Data.TaskId}

