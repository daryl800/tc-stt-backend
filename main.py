import os
import json
import base64
from fastapi import FastAPI, UploadFile, File
from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common.credential import Credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tencent Cloud credentials
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

@app.get("/")
def read_root():
    return {"message": "TECENT SentenceRecognition Backend is running!"}

@app.post("/transcribe-cantonese")
async def transcribe(file: UploadFile = File(...)):
    try:
        # Read audio data
        audio_data = await file.read()
        print(f"Audio size: {len(audio_data)} bytes")

        # Save temporarily
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(audio_data)

        # Tencent client setup
        cred = Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")

        req = models.SentenceRecognitionRequest()
        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-cantonese",  # ✅ USE CANTONESE ENGINE
            "SourceType": 1,
            "VoiceFormat": "mp3",
            "UsrAudioKey": "memory-clip",
            "Data": base64.b64encode(audio_data).decode("utf-8"),
        }
        req.from_json_string(json.dumps(params))

        resp = client.SentenceRecognition(req)

        # Clean up temp file
        os.remove(file_location)

        return {"text": resp.Result}

    except TencentCloudSDKException as err:
        return {"error": str(err)}
