import os
import json
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException  # Fixed import
from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common import credential  # Fixed import
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

@app.post("/transcribe-cantonese")
async def transcribe_sync(audio: UploadFile = File(...)):
    try:
        # Read and validate audio
        audio_bytes = await audio.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Convert to base64
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Dynamic voice format
        voice_format = audio.filename.split(".")[-1].lower()

        # Initialize Tencent client (CORRECTED)
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")

        # Configure request
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

        req.from_json_string(json.dumps(params))

        # 🔍 Debug prints before sending the request
        print("📤 VoiceFormat:", voice_format)
        print("📤 EngSerViceType:", params["EngSerViceType"])
        print("📤 Audio Length (bytes):", len(audio_bytes))
        print("📤 Base64 Length (chars):", len(audio_base64))
        
        # Call API
        resp = client.SentenceRecognition(req)
        
        return {"transcription": resp.Result}

    except TencentCloudSDKException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Tencent Cloud Error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Server Error: {str(e)}"
        )