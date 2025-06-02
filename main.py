from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models
import base64
import json
import asyncio
import os

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Add your frontend URL here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Tencent credentials from environment or .env
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

@app.post("/transcribe-tencent")
async def transcribe_tencent(audio: UploadFile = File(...)):
    # Step 1: Read and encode audio
    audio_bytes = await audio.read()
    audio_base64 = base64.b64encode(audio_bytes).decode()

    # Step 2: Create Tencent client
    cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
    client = asr_client.AsrClient(cred, "ap-hongkong")

    # Step 3: Create transcription task
    req = models.CreateRecTaskRequest()
    params = {
        "EngineModelType": "16k_zh-PY", # Use "16k_zh-PY" for Cantonese
        "ChannelNum": 1,
        "ResTextFormat": 0,
        "SourceType": 1,
        "Data": audio_base64,
        "DataLen": len(audio_bytes),
    }
    req.from_json_string(json.dumps(params))
    resp = client.CreateRecTask(req)
    task_id = resp.Data.TaskId

    # Step 4: Polling until transcription is done (max 20s)
    result = None
    for _ in range(20):  # ~20 seconds max
        await asyncio.sleep(1)
        status_req = models.DescribeTaskStatusRequest()
        status_req.TaskId = task_id
        status_resp = client.DescribeTaskStatus(status_req)

        if status_resp.Data.StatusStr == "success":
            result = status_resp.Data.Result
            break
        elif status_resp.Data.StatusStr == "failed":
            return {"error": "Tencent transcription failed."}

    if result:
        return {"transcription": result}
    else:
        return {"error": "Timeout: transcription not ready after 20s."}
