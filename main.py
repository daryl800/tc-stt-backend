from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import base64
import json
import os
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException

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
        # Read and validate audio
        audio_bytes = await audio.read()
        if len(audio_bytes) == 0:
            raise HTTPException(400, "Empty audio file")

        # Convert to base64
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Dynamic voice format (e.g., "webm" or "wav")
        voice_format = audio.filename.split(".")[-1].lower()

        # Tencent client setup
        cred = Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        client = asr_client.AsrClient(cred, "ap-guangzhou")

        # Configure request
        req = models.SentenceRecognitionRequest()
        params = {
            "ProjectId": 0,
            "SubServiceType": 2,
            "EngSerViceType": "16k_zh-TW",  # Best for Cantonese
            "SourceType": 1,
            "VoiceFormat": voice_format,      # Dynamic (webm, wav, etc.)
            "UsrAudioKey": "cantonese-clip",
            "Data": audio_base64,
        }
        req.from_json_string(json.dumps(params))

        # Call API
        resp = client.SentenceRecognition(req)
        return {"transcription": resp.Result}

    except TencentCloudSDKException as e:
        raise HTTPException(500, f"Tencent Cloud Error: {e.message}")
    except Exception as e:
        raise HTTPException(500, f"Server Error: {str(e)}")